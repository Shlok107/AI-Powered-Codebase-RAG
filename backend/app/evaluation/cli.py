from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from app.evaluation.dataset import load_dataset
from app.evaluation.runner import compare_reports, run_evaluation, write_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Codebase RAG retrieval on a versioned dataset")
    parser.add_argument("--repository-id", type=uuid.UUID)
    parser.add_argument("--dataset", default="evaluation/datasets/codebase-rag-v1.json")
    parser.add_argument("--output", default="evaluation/reports/latest.json")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--mode", choices=("all", "vector", "keyword", "hybrid_rrf"), default="all")
    parser.add_argument("--source-root", help="Optional checkout root used to validate dataset file/line references")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE.json", "AFTER.json"), help="Compare two saved reports and exit")
    args = parser.parse_args()
    if args.compare:
        before, after = (json.loads(Path(path).read_text(encoding="utf-8")) for path in args.compare)
        print(json.dumps(compare_reports(before, after), indent=2))
        return
    if not args.repository_id:
        parser.error("--repository-id is required unless --compare is used")
    if args.top_k < 1:
        parser.error("--top-k must be positive")
    root = args.source_root or str(Path.cwd().parent)
    load_dataset(args.dataset, repository_root=root)
    report = asyncio.run(run_evaluation(args.dataset, args.repository_id, args.top_k, args.mode, root))
    write_report(report, args.output)
    print(json.dumps({"run_id": report["run_id"], "dataset_version": report["dataset_version"],
                      "output": str(Path(args.output)), "aggregate_metrics": report["aggregate_metrics"]}, indent=2))


if __name__ == "__main__":
    main()
