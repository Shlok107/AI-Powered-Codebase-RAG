import pytest

from app.services.dependency_graph import SourceFile, extract_import_graph, node_details


pytestmark = pytest.mark.unit


def test_graph_resolves_internal_absolute_and_relative_python_imports_only() -> None:
    files = [
        SourceFile("src/pkg/__init__.py", ""),
        SourceFile("src/pkg/api.py", "from . import service\nfrom pkg.models import Item\nimport json\n"),
        SourceFile("src/pkg/service.py", "from .models import Item\n"),
        SourceFile("src/pkg/models.py", "class Item: pass\n"),
        SourceFile("src/web/client.ts", "import { api } from './api'\n"),
    ]

    result = extract_import_graph(files)
    edges = {(edge["source"], edge["target"]) for edge in result["edges"]}

    assert ("file:src/pkg/api.py", "file:src/pkg/service.py") in edges
    assert ("file:src/pkg/api.py", "file:src/pkg/models.py") in edges
    assert ("file:src/pkg/service.py", "file:src/pkg/models.py") in edges
    assert all("client.ts" not in source and "client.ts" not in target for source, target in edges)
    assert result["python_files"] == 4
    assert result["files_analyzed"] == 5
    assert result["coverage"] == {"languages": ["python"], "relationship_types": ["imports"], "partial": True}


def test_graph_ignores_external_unresolved_and_self_imports() -> None:
    result = extract_import_graph([
        SourceFile("app.py", "import requests\nimport app\nfrom missing import helper\n"),
    ])

    assert result["nodes"][0]["path"] == "app.py"
    assert result["edges"] == []
    assert result["resolved_relationships"] == 0


def test_graph_records_parse_errors_and_produces_stable_positions() -> None:
    files = [SourceFile("a.py", "import b\n"), SourceFile("b.py", "import a\n"), SourceFile("broken.py", "def nope(:\n")]

    first = extract_import_graph(files)
    second = extract_import_graph(list(reversed(files)))

    assert first["parse_errors"] == 1
    assert first["nodes"] == second["nodes"]
    assert first["edges"] == second["edges"]


def test_node_details_separates_direct_and_transitive_dependencies() -> None:
    graph = extract_import_graph([
        SourceFile("a.py", "import b\n"),
        SourceFile("b.py", "import c\n"),
        SourceFile("c.py", ""),
    ])

    details = node_details(graph, "file:a.py", depth=8)
    assert details is not None
    assert details["direct_dependencies"] == ["b.py"]
    assert details["dependencies"] == ["b.py", "c.py"]
    assert details["direct_dependents"] == []
    assert node_details(graph, "file:a.py", depth=1)["dependencies"] == ["b.py"]
    assert node_details(graph, "file:absent.py") is None


def test_search_keeps_matches_beyond_default_display_slice_and_neighbors() -> None:
    graph = extract_import_graph(
        [
            SourceFile("a.py", ""),
            SourceFile("b.py", ""),
            SourceFile("z_target.py", "import z_helper\n"),
            SourceFile("z_helper.py", ""),
        ],
        node_limit=2,
        query="target",
    )

    paths = {node["path"] for node in graph["nodes"]}
    assert paths == {"z_target.py", "z_helper.py"}
    assert graph["edges"][0]["source"] == "file:z_target.py"
    assert graph["truncated"] is True
