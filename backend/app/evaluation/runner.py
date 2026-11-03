from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.evaluation.dataset import load_dataset
from app.evaluation.metrics import ranking_metrics, ranking_metrics_at_cutoffs
from app.db.models import Repository
from app.services.embeddings import create_embedding_provider
from app.services.retrieval import RetrievalService


def _chunk_key(chunk: Any) -> str:
    return f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}"


def is_relevant(chunk: Any, references: list[dict[str, Any]]) -> bool:
    for ref in references:
        if chunk.file_path != ref["file"]:
            continue
        if chunk.start_line <= ref["end_line"] and chunk.end_line >= ref["start_line"]:
            return True
    return False


def _reference_key(ref: dict[str, Any]) -> str:
    return f"{ref['file']}:{ref['start_line']}-{ref['end_line']}"


def _matched_reference_keys(chunk: Any, references: list[dict[str, Any]]) -> list[str]:
    return [_reference_key(ref) for ref in references if is_relevant(chunk, [ref])]


async def run_evaluation(dataset_path: str | Path, repository_id: uuid.UUID, top_k: int = 6, mode: str = "all", source_root: str | Path | None = None) -> dict[str, Any]:
    """Run the dataset against the existing PostgreSQL retrieval methods; no LLM calls."""
    from app.db.session import async_session_maker
    from app.core.config import get_settings

    dataset = load_dataset(dataset_path, repository_root=source_root)
    settings = get_settings()
    if mode not in {"all", "vector", "keyword", "hybrid_rrf"}:
        raise ValueError("mode must be all, vector, keyword, or hybrid_rrf")
    if settings.embedding_provider == "openai_compatible":
        raise ValueError("Offline evaluation requires a local or no-op embedding provider; external embedding APIs are disabled")
    provider = create_embedding_provider()
    service = RetrievalService(provider)
    results: list[dict[str, Any]] = []
    aggregate: dict[str, list[dict[str, float]]] = defaultdict(list)
    category_aggregate: dict[str, dict[str, list[dict[str, float]]]] = defaultdict(lambda: defaultdict(list))

    async with async_session_maker() as session:
        repository = await session.get(Repository, repository_id)
        if repository is None:
            raise ValueError(f"Repository {repository_id} does not exist")
        if repository.status.value != "indexed":
            raise ValueError("Evaluation requires an indexed repository")
        for question in dataset["questions"]:
            query = question["question"]
            embedding = await provider.embed_text(query) if mode in {"all", "vector", "hybrid_rrf"} else []
            vector = [] if not embedding or all(v == 0 for v in embedding) else await service._vector_search(session, repository_id, embedding, top_k)
            keyword = await service._keyword_search(session, repository_id, query, top_k) if mode in {"all", "keyword", "hybrid_rrf"} else []
            hybrid = service._reciprocal_rank_fusion(vector, keyword, top_k) if mode in {"all", "hybrid_rrf"} else []
            modes = {"vector": vector, "keyword": keyword, "hybrid_rrf": hybrid}
            if mode != "all":
                modes = {mode: modes[mode]}
            question_result = {
                "id": question["id"], "category": question["category"], "question": query,
                "expected_answer": question["expected_answer"],
                "insufficient_context": bool(question.get("insufficient_context", False)),
                "relevant_chunks": question["relevant_chunks"], "retrieval": {},
            }
            for mode, chunks in modes.items():
                await service.enrich_with_file_paths(session, chunks)
                relevant_keys = {_reference_key(ref) for ref in question["relevant_chunks"]}
                ranked_reference_keys = []
                for chunk in chunks:
                    matched = _matched_reference_keys(chunk, question["relevant_chunks"])
                    # Keep irrelevant retrieved chunks in the ranking as misses.
                    ranked_reference_keys.append(matched[0] if matched else _chunk_key(chunk))
                if question.get("insufficient_context"):
                    metrics = {"scored": False, "reason": "expected_insufficient_context"}
                elif question["relevant_chunks"]:
                    metrics = ranking_metrics_at_cutoffs(ranked_reference_keys, relevant_keys)
                    metrics.update(ranking_metrics(ranked_reference_keys, relevant_keys, top_k))
                else:
                    metrics = {f"{name}@{cutoff}": 0.0 for cutoff in set((1, 3, 5, top_k)) for name in ("precision", "recall", "hit_rate", "ndcg")}
                    metrics["mrr"] = 0.0
                question_result["retrieval"][mode] = {
                    "metrics": metrics,
                    "chunks": [{"chunk_id": str(c.chunk_id), "file": c.file_path,
                                "start_line": c.start_line, "end_line": c.end_line,
                                "text": c.text, "score": c.combined_score or c.vector_score or c.keyword_score}
                               for c in chunks],
                }
                if question["relevant_chunks"] and not question.get("insufficient_context"):
                    aggregate[mode].append(metrics)
                    category_aggregate[question["category"]][mode].append(metrics)
            results.append(question_result)

    aggregate_metrics = {
        mode: {key: sum(item[key] for item in rows) / len(rows) for key in rows[0]}
        for mode, rows in aggregate.items() if rows
    }
    category_metrics = {
        category: {name: {key: sum(row[key] for row in rows) / len(rows) for key in rows[0]}
                   for name, rows in modes.items() if rows}
        for category, modes in category_aggregate.items()
    }
    return {
        "run_id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version": dataset["version"], "repository_id": str(repository_id), "top_k": top_k,
        "repository": {"name": repository.display_name, "status": repository.status.value,
                       "file_count": repository.file_count, "chunk_count": repository.chunk_count},
        "configuration": {"embedding_provider": settings.embedding_provider,
                          "embedding_model": settings.embedding_model,
                          "embedding_dimensions": settings.embedding_dimensions,
                          "retrieval_top_k": settings.retrieval_top_k,
                          "retrieval": "existing vector + PostgreSQL full-text + RRF; unmodified",
                          "llm": "not called"},
        "aggregate_metrics": aggregate_metrics, "category_metrics": category_metrics, "questions": results,
    }


def write_report(report: dict[str, Any], output: str | Path) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compare_reports(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    if before.get("dataset_version") != after.get("dataset_version"):
        raise ValueError("Reports must use the same dataset version")
    for key in ("repository_id", "top_k"):
        if before.get(key) != after.get(key):
            raise ValueError(f"Reports must use the same {key}")
    before_ids = {item.get("id") for item in before.get("questions", [])}
    after_ids = {item.get("id") for item in after.get("questions", [])}
    if before_ids != after_ids:
        raise ValueError("Reports must evaluate the same question IDs")
    modes: dict[str, Any] = {}
    for mode in sorted(set(before.get("aggregate_metrics", {})) & set(after.get("aggregate_metrics", {}))):
        old, new = before["aggregate_metrics"][mode], after["aggregate_metrics"][mode]
        modes[mode] = {key: {"before": value, "after": new[key], "delta": new[key] - value}
                       for key, value in old.items() if key in new}
    return {"dataset_version": before.get("dataset_version"), "modes": modes}
