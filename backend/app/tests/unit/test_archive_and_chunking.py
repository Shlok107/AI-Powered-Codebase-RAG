from pathlib import Path
from zipfile import ZipFile

import pytest

from app.core.config import Settings
from app.services.chunking import LineChunker, PythonChunker, get_chunker
from app.services.safe_archive import ArchiveValidationError, SafeArchiveExtractor


pytestmark = pytest.mark.unit


@pytest.fixture
def extractor() -> SafeArchiveExtractor:
    return SafeArchiveExtractor(Settings(_env_file=None))


@pytest.mark.asyncio
async def test_archive_extracts_supported_files_and_ignores_binary_and_vendor_paths(extractor, zip_bytes) -> None:
    result = await extractor.extract(
        zip_bytes(
            [
                ("src/app.py", "def run():\n    return 7\n"),
                ("assets/logo.png", "not source"),
                ("node_modules/pkg/index.js", "ignored"),
            ]
        ),
        "repo-id",
    )

    assert result.file_count == 1
    assert result.files[0].relative_path == "src/app.py"
    assert result.files[0].language == "python"
    assert result.files[0].line_count == 2
    assert result.languages == ["python"]


@pytest.mark.asyncio
async def test_empty_archive_has_no_files_or_languages(extractor, zip_bytes) -> None:
    result = await extractor.extract(zip_bytes([]), "repo-id")

    assert result.file_count == 0
    assert result.files == []
    assert result.languages == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["../escape.py", "..\\escape.py", "/absolute.py", "C:\\outside.py"],
)
async def test_archive_rejects_posix_and_windows_path_escape_forms(extractor, zip_bytes, path) -> None:
    with pytest.raises(ArchiveValidationError):
        await extractor.extract(zip_bytes([(path, "print('unsafe')")]), "repo-id")


@pytest.mark.asyncio
async def test_invalid_and_truncated_zip_archives_are_rejected(extractor) -> None:
    with pytest.raises(ArchiveValidationError, match="Invalid ZIP"):
        await extractor.extract(b"not a zip", "repo-id")

    malformed = b"PK\x03\x04\x14\x00\x00"
    with pytest.raises(ArchiveValidationError, match="Invalid ZIP"):
        await extractor.extract(malformed, "repo-id")


@pytest.mark.asyncio
async def test_duplicate_archive_paths_are_rejected(extractor) -> None:
    import warnings
    from io import BytesIO

    data = BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(data, "w") as archive:
            archive.writestr("src/app.py", "print('first')")
            archive.writestr("src/app.py", "print('second')")

    with pytest.raises(ArchiveValidationError, match="Duplicate"):
        await extractor.extract(data.getvalue(), "repo-id")


@pytest.mark.asyncio
async def test_archive_file_count_limit_is_enforced(zip_bytes) -> None:
    extractor = SafeArchiveExtractor(Settings(_env_file=None, max_archive_files=1))

    with pytest.raises(ArchiveValidationError, match="too many files"):
        await extractor.extract(zip_bytes([("a.py", "pass"), ("b.py", "pass")]), "repo-id")


def test_supported_and_unknown_language_detection(extractor) -> None:
    assert extractor._detect_language(Path("src/main.py")) == "python"
    assert extractor._detect_language(Path("src/main.ts")) == "typescript"
    assert extractor._detect_language(Path("README")) is None
    assert extractor._detect_language(Path("mystery.unknown")) is None
    assert extractor._detect_language(Path("Makefile")) == "makefile"


def test_python_ast_chunking_preserves_top_level_symbols_and_line_ranges() -> None:
    source = """# module docs

def first():
    return 1

class Worker:
    def run(self):
        return 2
"""

    chunks = PythonChunker(chunk_size=3, chunk_overlap=1).chunk("worker.py", source)

    symbols = {chunk.metadata.get("name"): chunk for chunk in chunks if chunk.chunk_type in {"function", "class"}}
    assert set(symbols) == {"first", "Worker"}
    assert symbols["first"].start_line == 3
    assert symbols["first"].end_line == 4
    assert symbols["Worker"].start_line == 6
    assert symbols["Worker"].end_line == 8
    assert all(chunk.file_path == "worker.py" and chunk.content_hash for chunk in chunks)


def test_python_chunker_falls_back_for_malformed_source_and_empty_files() -> None:
    malformed = PythonChunker(chunk_size=2, chunk_overlap=0).chunk("bad.py", "def nope(:\n  pass")
    empty = PythonChunker().chunk("empty.py", "")

    assert len(malformed) == 1
    assert malformed[0].start_line == 1
    assert malformed[0].end_line == 2
    assert empty == []


def test_line_chunker_respects_overlap_and_chunk_metadata() -> None:
    content = "\n".join(f"line {i}" for i in range(1, 8))

    chunks = LineChunker(chunk_size=3, chunk_overlap=1, language="typescript").chunk("src.ts", content)

    assert [(chunk.start_line, chunk.end_line) for chunk in chunks] == [(1, 3), (3, 5), (5, 7)]
    assert chunks[1].text.splitlines() == ["line 3", "line 4", "line 5"]
    assert all(chunk.language == "typescript" and chunk.chunk_type == "block" for chunk in chunks)


def test_chunker_factory_selects_ast_chunker_only_for_python() -> None:
    assert isinstance(get_chunker("python", chunk_size=20), PythonChunker)
    assert isinstance(get_chunker("typescript", chunk_size=20), LineChunker)
