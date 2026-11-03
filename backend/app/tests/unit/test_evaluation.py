import json
import math
from pathlib import Path

import pytest

from app.evaluation.dataset import load_dataset
from app.evaluation.metrics import ranking_metrics, ranking_metrics_at_cutoffs
from app.evaluation.runner import compare_reports, write_report


def test_metrics_calculate_precision_recall_mrr_hit_rate_and_ndcg() -> None:
    result = ranking_metrics(["a", "x", "b"], {"a", "b"}, 3)
    assert result["precision@3"] == pytest.approx(2 / 3)
    assert result["recall@3"] == 1.0
    assert result["mrr"] == 1.0
    assert result["hit_rate@3"] == 1.0
    assert result["ndcg@3"] == pytest.approx(1.5 / (1 + 1 / math.log2(3)))


def test_metrics_deduplicate_and_handle_no_relevant_items() -> None:
    assert ranking_metrics(["a", "a", "b"], set(), 2) == {
        "precision@2": 0.0, "recall@2": 0.0, "mrr": 0.0,
        "hit_rate@2": 0.0, "ndcg@2": 0.0,
    }


def test_metrics_reject_nonpositive_cutoff() -> None:
    with pytest.raises(ValueError, match="positive"):
        ranking_metrics([], set(), 0)


def test_metrics_cover_empty_results_duplicates_and_k_beyond_results() -> None:
    assert ranking_metrics([], {"a"}, 3)["precision@3"] == 0
    assert ranking_metrics(["a", "a"], {"a"}, 3)["precision@3"] == pytest.approx(1 / 3)
    assert ranking_metrics(["a", "x"], {"a"}, 5)["recall@5"] == 1
    assert ranking_metrics_at_cutoffs(["x", "a"], {"a"})["mrr"] == 0.5


def test_dataset_loads_versioned_verified_questions() -> None:
    dataset = load_dataset("evaluation/datasets/codebase-rag-v1.json", repository_root=Path.cwd().parent)
    assert dataset["version"] == "1.0.0"
    assert len(dataset["questions"]) == 9
    assert any(question.get("insufficient_context") for question in dataset["questions"])


def test_dataset_rejects_duplicate_question_ids(tmp_path) -> None:
    path = tmp_path / "dataset.json"
    item = {"id": "same", "category": "x", "question": "q", "expected_answer": "a", "relevant_chunks": []}
    path.write_text(json.dumps({"version": "1", "questions": [item, item]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_dataset(path)


@pytest.mark.parametrize("reference", [
    {"file": "missing.py", "start_line": 1, "end_line": 2},
    {"file": "../outside.py", "start_line": 1, "end_line": 2},
    {"file": "C:/outside.py", "start_line": 1, "end_line": 2},
    {"file": "ok.py", "start_line": 3, "end_line": 2},
])
def test_dataset_rejects_invalid_references(tmp_path, reference) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "ok.py").write_text("one\ntwo\n", encoding="utf-8")
    item = {"id": "q", "category": "x", "question": "q", "expected_answer": "a", "relevant_chunks": [reference]}
    dataset = tmp_path / "d.json"
    dataset.write_text(json.dumps({"version": "1", "questions": [item]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_dataset(dataset, repository_root=root)


def test_dataset_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="Unable to load"):
        load_dataset(path)


def test_report_is_machine_readable_and_creates_parent(tmp_path) -> None:
    path = tmp_path / "nested" / "report.json"
    report = {"dataset_version": "1.0.0", "questions": [], "aggregate_metrics": {}}
    write_report(report, path)
    assert json.loads(path.read_text(encoding="utf-8")) == report


def test_report_comparison_requires_same_dataset_version_and_reports_deltas() -> None:
    before = {"dataset_version": "1", "aggregate_metrics": {"hybrid_rrf": {"mrr": 0.5}}}
    after = {"dataset_version": "1", "aggregate_metrics": {"hybrid_rrf": {"mrr": 0.75}}}
    assert compare_reports(before, after)["modes"]["hybrid_rrf"]["mrr"]["delta"] == 0.25
    with pytest.raises(ValueError, match="same dataset"):
        compare_reports(before, {**after, "dataset_version": "2"})
