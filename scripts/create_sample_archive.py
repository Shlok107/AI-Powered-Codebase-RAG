from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_REPOSITORY = REPOSITORY_ROOT / "sample-repo"
OUTPUT_ARCHIVE = REPOSITORY_ROOT / "sample-repo.zip"
EXCLUDED_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def main() -> None:
    if not SAMPLE_REPOSITORY.is_dir():
        raise SystemExit(f"Sample repository not found: {SAMPLE_REPOSITORY}")

    file_count = 0
    with ZipFile(OUTPUT_ARCHIVE, "w", ZIP_DEFLATED) as archive:
        for path in sorted(SAMPLE_REPOSITORY.rglob("*")):
            relative_path = path.relative_to(SAMPLE_REPOSITORY)
            if any(part in EXCLUDED_DIRS for part in relative_path.parts):
                continue
            if not path.is_file() or path.suffix in EXCLUDED_SUFFIXES:
                continue
            archive.write(path, relative_path.as_posix())
            file_count += 1

    print(f"Created {OUTPUT_ARCHIVE.relative_to(REPOSITORY_ROOT)} ({file_count} files)")


if __name__ == "__main__":
    main()
