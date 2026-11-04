"""On-demand, Python import graph derived from indexed repository source files."""
from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import networkx as nx


@dataclass(frozen=True)
class SourceFile:
    path: str
    content: str


def _module_for_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    if not normalized.endswith(".py"):
        return None
    parts = list(PurePosixPath(normalized).with_suffix("").parts)
    if not parts:
        return None
    if parts and parts[0] in {"backend", "src"}:
        parts.pop(0)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or None


def _resolve_module(module: str, modules: dict[str, str]) -> str | None:
    candidates = (module, f"{module}.__init__")
    for candidate in candidates:
        if candidate in modules:
            return modules[candidate]
    # A from-package import may name a sibling module or an exported symbol.
    parent = module.rpartition(".")[0]
    if parent and parent in modules:
        return modules[parent]
    return None


def extract_import_graph(files: list[SourceFile], *, node_limit: int = 250, edge_limit: int = 800, query: str | None = None) -> dict[str, Any]:
    """Resolve statically discoverable Python imports into a bounded directed graph."""
    # Prefer stable lexical ordering when duplicate module paths exist; this makes
    # source-to-module resolution and seeded layout reproducible.
    modules: dict[str, str] = {}
    for item in sorted(files, key=lambda source: source.path):
        module = _module_for_path(item.path)
        if module:
            modules.setdefault(module, item.path)
    contents = {item.path: item.content for item in files}
    graph = nx.DiGraph()
    parse_errors = 0
    for path in sorted(modules.values()):
        graph.add_node(path)
        try:
            tree = ast.parse(contents[path], filename=path)
        except (SyntaxError, ValueError, TypeError):
            parse_errors += 1
            continue
        current_module = _module_for_path(path) or ""
        package = current_module if path.endswith("/__init__.py") or path == "__init__.py" else current_module.rpartition(".")[0]
        for node in ast.walk(tree):
            imported: list[tuple[str, int]] = []
            if isinstance(node, ast.Import):
                imported.extend((alias.name, node.lineno) for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    package_parts = package.split(".") if package else []
                    keep = max(0, len(package_parts) - node.level + 1)
                    base = ".".join(package_parts[:keep] + ([base] if base else []))
                # `from . import sibling` names a sibling module, while
                # `from .models import Symbol` depends on the models module.
                if base and node.module:
                    imported.append((base, node.lineno))
                for alias in node.names:
                    imported.append((f"{base}.{alias.name}" if base else alias.name, node.lineno))
            for module, line in imported:
                target = _resolve_module(module, modules)
                if target is None and isinstance(node, ast.ImportFrom) and node.module:
                    target = _resolve_module(node.module, modules)
                if target and target != path:
                    graph.add_edge(path, target, lines=sorted(set(graph.get_edge_data(path, target, {}).get("lines", []) + [line])))

    all_nodes = sorted(graph.nodes)
    all_edges = sorted(graph.edges(data=True))
    if query:
        needle = query.casefold()
        matching = [path for path in all_nodes if needle in path.casefold() or needle in os.path.basename(path).casefold()]
        # Search prioritizes exact path matches and keeps a one-hop neighborhood
        # so users can inspect actual relationships around the matching file.
        keep_nodes = set(matching[:node_limit])
        for path in matching[:node_limit]:
            neighbors = sorted(set(graph.successors(path)) | set(graph.predecessors(path)))
            for neighbor in neighbors:
                if len(keep_nodes) >= node_limit:
                    break
                keep_nodes.add(neighbor)
    else:
        keep_nodes = set(all_nodes[:node_limit])
    truncated = len(all_nodes) > len(keep_nodes) or len(all_edges) > edge_limit
    edges = [(source, target, data) for source, target, data in all_edges
             if source in keep_nodes and target in keep_nodes][:edge_limit]
    visible = nx.DiGraph()
    visible.add_nodes_from(sorted(keep_nodes))
    visible.add_edges_from((s, t, d) for s, t, d in edges)
    positions = nx.spring_layout(visible, seed=42, iterations=30) if visible else {}
    degrees = dict(visible.degree())
    nodes = [{"id": f"file:{path}", "type": "file", "label": os.path.basename(path),
              "path": path, "language": "python", "degree": degrees.get(path, 0),
              "x": round(float(positions[path][0]), 6), "y": round(float(positions[path][1]), 6)}
             for path in sorted(visible.nodes)]
    edge_items = [{"source": f"file:{source}", "target": f"file:{target}", "type": "imports",
                   "source_lines": data.get("lines", [])} for source, target, data in edges]
    return {"nodes": nodes, "edges": edge_items, "files_analyzed": len(files),
            "python_files": len(modules), "resolved_relationships": len(all_edges),
            "parse_errors": parse_errors, "truncated": truncated,
            "coverage": {"languages": ["python"] if modules else [],
                         "relationship_types": ["imports"] if all_edges else [], "partial": True}}


def node_details(graph_data: dict[str, Any], node_id: str, *, depth: int = 1) -> dict[str, Any] | None:
    graph = nx.DiGraph()
    path_by_id = {node["id"]: node["path"] for node in graph_data["nodes"]}
    graph.add_nodes_from(path_by_id.values())
    for edge in graph_data["edges"]:
        if edge["source"] in path_by_id and edge["target"] in path_by_id:
            graph.add_edge(path_by_id[edge["source"]], path_by_id[edge["target"]])
    path = path_by_id.get(node_id)
    if path is None:
        return None
    dependencies = set(nx.single_source_shortest_path_length(graph, path, cutoff=depth)) - {path}
    reverse = graph.reverse(copy=False)
    dependents = set(nx.single_source_shortest_path_length(reverse, path, cutoff=depth)) - {path}
    return {"node": next(node for node in graph_data["nodes"] if node["id"] == node_id),
            "direct_dependencies": sorted(graph.successors(path)),
            "direct_dependents": sorted(graph.predecessors(path)),
            "dependencies": sorted(dependencies), "dependents": sorted(dependents),
            "dependency_count": graph.out_degree(path), "dependent_count": graph.in_degree(path)}
