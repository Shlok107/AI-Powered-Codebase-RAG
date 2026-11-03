from __future__ import annotations

import json
from pathlib import Path
from pathlib import PureWindowsPath
from typing import Any


def load_dataset(path: str | Path, repository_root: str | Path | None = None) -> dict[str, Any]:
    """Load and minimally validate a versioned JSON evaluation set."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load evaluation dataset: {exc.__class__.__name__}") from exc
    if not isinstance(data, dict) or not data.get("version") or not isinstance(data.get("questions"), list):
        raise ValueError("Dataset must contain a version and questions array")
    ids: set[str] = set()
    for item in data["questions"]:
        if not isinstance(item, dict) or not all(isinstance(item.get(key), str) and item[key].strip() for key in ("id", "category", "question")):
            raise ValueError("Each question needs id, category and question")
        if item["id"] in ids:
            raise ValueError(f"Duplicate question id: {item['id']}")
        ids.add(item["id"])
        if not isinstance(item.get("expected_answer"), str) or not item["expected_answer"].strip():
            raise ValueError(f"Question {item['id']} needs a verified expected_answer")
        if not isinstance(item.get("relevant_chunks"), list):
            raise ValueError(f"Question {item['id']} needs relevant_chunks")
        if item.get("insufficient_context") and item["relevant_chunks"]:
            raise ValueError(f"Insufficient-context question {item['id']} must not have relevant chunks")
        for ref in item["relevant_chunks"]:
            if not isinstance(ref, dict) or not isinstance(ref.get("file"), str) or not ref["file"].strip() or not isinstance(ref.get("start_line"), int) or isinstance(ref.get("start_line"), bool) or not isinstance(ref.get("end_line"), int) or isinstance(ref.get("end_line"), bool):
                raise ValueError(f"Question {item['id']} has an invalid chunk reference")
            if ref["start_line"] < 1 or ref["end_line"] < ref["start_line"]:
                raise ValueError(f"Question {item['id']} has an invalid line range")
            ref["file"] = ref["file"].replace("\\", "/")
            windows = PureWindowsPath(ref["file"])
            if ref["file"].startswith("/") or windows.is_absolute() or windows.drive or ".." in Path(ref["file"]).parts:
                raise ValueError(f"Question {item['id']} has an unsafe repository-relative path")
            if repository_root is not None:
                root = Path(repository_root).resolve()
                source = root.joinpath(*ref["file"].split("/"))
                try:
                    source.resolve().relative_to(root)
                except ValueError as exc:
                    raise ValueError(f"Question {item['id']} reference escapes repository root") from exc
                if not source.is_file():
                    raise ValueError(f"Question {item['id']} references missing file: {ref['file']}")
                line_count = len(source.read_text(encoding="utf-8", errors="replace").splitlines())
                if ref["end_line"] > line_count:
                    raise ValueError(f"Question {item['id']} line interval exceeds {ref['file']} ({line_count} lines)")
    return data

