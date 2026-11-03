import hashlib
import os
import stat
import tempfile
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional

from app.core.config import Settings
class ArchiveValidationError(Exception):
    """Raised when archive validation fails."""
    pass


@dataclass
class ExtractedFile:
    """Represents a single extracted file with its content."""
    relative_path: str
    content: str
    size_bytes: int
    language: Optional[str]
    line_count: int
    content_hash: str


@dataclass
class ExtractResult:
    """Result of archive extraction containing file contents (not paths)."""
    files: list[ExtractedFile] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    total_size: int = 0
    
    @property
    def file_count(self) -> int:
        return len(self.files)


class SafeArchiveExtractor:
    """Safely extracts ZIP archives with protection against common attacks."""

    # Directories to ignore
    IGNORED_DIRS = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".env",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "target",
        "bin",
        "obj",
        ".idea",
        ".vscode",
        ".vs",
        "coverage",
        ".nyc_output",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "htmlcov",
        ".coverage",
    }

    # File extensions to ignore (binary, media, etc.)
    IGNORED_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
        ".mp4", ".webm", ".mov", ".avi", ".mkv",
        ".mp3", ".wav", ".ogg", ".flac",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".zip", ".tar", ".gz", ".rar", ".7z", ".bz2", ".xz",
        ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a", ".lib",
        ".class", ".jar", ".war", ".ear",
        ".pyc", ".pyo", ".pyd",
        ".woff", ".woff2", ".ttf", ".eot", ".otf",
        ".map", ".min.js", ".min.css",
    }

    # Supported text/source file extensions
    SUPPORTED_EXTENSIONS = {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte",
        ".java", ".kt", ".scala", ".groovy",
        ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hxx",
        ".go", ".rs", ".swift", ".m", ".mm",
        ".rb", ".php", ".pl", ".pm",
        ".cs", ".vb", ".fs",
        ".html", ".htm", ".css", ".scss", ".sass", ".less",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
        ".md", ".markdown", ".rst", ".txt",
        ".dockerfile", ".dockerignore",
        ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
        ".sql", ".graphql", ".gql",
        ".proto", ".avro",
        ".tf", ".tfvars", ".hcl",
        ".gradle", ".maven", ".sbt",
        ".xml", ".xsd", ".xsl",
    }

    def __init__(self, settings: Settings):
        self.settings = settings
        self.max_uncompressed_bytes = settings.max_uncompressed_mb * 1024 * 1024
        self.max_single_file_bytes = settings.max_single_file_mb * 1024 * 1024
        self.max_files = settings.max_archive_files
        self.max_path_length = settings.max_archive_path_length
        self.max_compression_ratio = settings.max_archive_compression_ratio

    def _is_ignored_path(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        parts = path.parts
        for part in parts:
            if part in self.IGNORED_DIRS:
                return True
            if part.startswith(".") and part not in {".github", ".gitlab", ".vscode"}:
                # Allow some dotfiles but ignore most
                if part not in {".github", ".gitlab", ".vscode", ".dockerignore", ".env.example"}:
                    return True
        return False

    def _is_supported_file(self, path: Path) -> bool:
        """Check if file extension is supported."""
        suffix = path.suffix.lower()
        if suffix in self.IGNORED_EXTENSIONS:
            return False
        if suffix in self.SUPPORTED_EXTENSIONS:
            return True
        # Check for files without extension but known names
        name = path.name.lower()
        if name in {
            "dockerfile", "makefile", "rakefile", "gemfile", "podfile",
            "license", "readme", "changelog", "contributing",
            "gitignore", "gitattributes", "editorconfig",
            "prettierrc", "eslintrc", "stylelintrc",
        }:
            return True
        return False

    def _detect_language(self, path: Path) -> Optional[str]:
        """Detect programming language from file extension."""
        suffix = path.suffix.lower()
        name = path.name.lower()

        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".vue": "vue",
            ".svelte": "svelte",
            ".java": "java",
            ".kt": "kotlin",
            ".scala": "scala",
            ".groovy": "groovy",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".hpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".go": "go",
            ".rs": "rust",
            ".swift": "swift",
            ".m": "objective-c",
            ".mm": "objective-cpp",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".vb": "vbnet",
            ".fs": "fsharp",
            ".html": "html",
            ".htm": "html",
            ".css": "css",
            ".scss": "scss",
            ".sass": "sass",
            ".less": "less",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".md": "markdown",
            ".markdown": "markdown",
            ".rst": "rst",
            ".sh": "shell",
            ".bash": "shell",
            ".zsh": "shell",
            ".fish": "shell",
            ".ps1": "powershell",
            ".bat": "batch",
            ".cmd": "batch",
            ".sql": "sql",
            ".graphql": "graphql",
            ".gql": "graphql",
            ".proto": "protobuf",
            ".tf": "terraform",
            ".tfvars": "terraform",
            ".hcl": "hcl",
            ".dockerfile": "dockerfile",
        }

        if suffix in language_map:
            return language_map[suffix]
        if name in {"dockerfile", "makefile", "rakefile", "gemfile", "podfile"}:
            return "dockerfile" if name == "dockerfile" else "makefile"
        return None

    async def extract(self, content: bytes, repository_id: str) -> ExtractResult:
        """Extract ZIP archive safely and return file contents."""
        # Create temporary extraction directory
        with tempfile.TemporaryDirectory(prefix=f"repo_{repository_id}_") as tmpdir:
            extract_path = Path(tmpdir) / "source"
            extract_path.mkdir()

            # Write ZIP to temporary file for processing
            zip_path = Path(tmpdir) / "archive.zip"
            zip_path.write_bytes(content)

            # Validate and extract
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    # Check file count
                    entries = zf.infolist()
                    if len(entries) > self.max_files:
                        raise ArchiveValidationError(
                            f"Archive contains too many files (maximum {self.max_files})."
                        )

                    total_declared_uncompressed = 0
                    total_actual_uncompressed = 0
                    file_count = 0
                    languages = set()
                    extracted_files = []
                    seen_paths: set[str] = set()

                    for info in entries:
                        # Normalize path - handle both forward and backward slashes
                        normalized_filename = info.filename.replace("\\", "/")
                        windows_path = PureWindowsPath(info.filename)
                        posix_path = PurePosixPath(normalized_filename)

                        # ZIP names are platform-independent; reject Windows drives and roots even
                        # when extraction is running on POSIX, and check normalized path segments.
                        if (
                            os.path.isabs(info.filename)
                            or posix_path.is_absolute()
                            or windows_path.is_absolute()
                            or bool(windows_path.drive)
                            or ".." in posix_path.parts
                            or "\x00" in info.filename
                        ):
                            raise ArchiveValidationError("Archive contains an unsafe path.")

                        if len(normalized_filename) > self.max_path_length:
                            raise ArchiveValidationError("Archive contains a path that exceeds the configured limit.")

                        unix_mode = info.external_attr >> 16
                        if stat.S_ISLNK(unix_mode):
                            raise ArchiveValidationError("Archive contains a symbolic link, which is not supported.")

                        # Validate metadata for every entry, including ignored and unsupported files.
                        if info.file_size < 0 or info.compress_size < 0:
                            raise ArchiveValidationError("Archive contains invalid file size metadata.")
                        total_declared_uncompressed += info.file_size
                        if total_declared_uncompressed > self.max_uncompressed_bytes:
                            raise ArchiveValidationError("Archive exceeds the configured total uncompressed size limit.")
                        if info.file_size and (
                            info.compress_size == 0
                            or info.file_size / info.compress_size > self.max_compression_ratio
                        ):
                            raise ArchiveValidationError("Archive contains an entry with an excessive compression ratio.")

                        normalized_relative_path = posix_path.as_posix()
                        path_key = normalized_relative_path.casefold()
                        if path_key in seen_paths:
                            raise ArchiveValidationError("Duplicate archive file paths are not allowed.")
                        seen_paths.add(path_key)

                        # Directory entries have already been checked for unsafe names and metadata.
                        if info.is_dir():
                            continue

                        # Normalize path
                        normalized_path = (extract_path / normalized_filename).resolve()
                        try:
                            normalized_path.relative_to(extract_path.resolve())
                        except ValueError:
                            raise ArchiveValidationError("Archive contains a path outside its extraction directory.")

                        # Check if file should be processed
                        rel_path = Path(normalized_filename)
                        if self._is_ignored_path(rel_path):
                            continue

                        if not self._is_supported_file(rel_path):
                            continue

                        if info.file_size > self.max_single_file_bytes:
                            raise ArchiveValidationError("An indexable archive file exceeds the configured per-file size limit.")

                        file_count += 1
                        lang = self._detect_language(rel_path)
                        if lang:
                            languages.add(lang)

                        # Stream decompression and enforce limits against actual output bytes;
                        # ZipInfo sizes alone are untrusted archive metadata.
                        try:
                            raw_content = bytearray()
                            actual_file_size = 0
                            with zf.open(info, "r") as zipped_file:
                                while chunk := zipped_file.read(64 * 1024):
                                    actual_file_size += len(chunk)
                                    total_actual_uncompressed += len(chunk)
                                    if actual_file_size > self.max_single_file_bytes:
                                        raise ArchiveValidationError("An archive file exceeds the configured per-file size limit.")
                                    if total_actual_uncompressed > self.max_uncompressed_bytes:
                                        raise ArchiveValidationError("Archive exceeds the configured total uncompressed size limit.")
                                    raw_content.extend(chunk)
                            content = bytes(raw_content).decode("utf-8", errors="replace")
                        except ArchiveValidationError:
                            raise
                        except (zipfile.BadZipFile, RuntimeError, EOFError, NotImplementedError, zlib.error, OSError) as e:
                            raise ArchiveValidationError("Archive is malformed or contains unsupported compressed data.") from e
                        
                        content_hash = hashlib.sha256(content.encode()).hexdigest()
                        line_count = len(content.splitlines()) if content else 0
                        size_bytes = actual_file_size
                        
                        extracted_files.append(ExtractedFile(
                            relative_path=normalized_filename,
                            content=content,
                            size_bytes=size_bytes,
                            language=lang,
                            line_count=line_count,
                            content_hash=content_hash,
                        ))

            except (zipfile.BadZipFile, EOFError, OSError) as e:
                raise ArchiveValidationError("Invalid ZIP archive.") from e

            return ExtractResult(
                files=extracted_files,
                languages=sorted(languages),
                total_size=total_declared_uncompressed,
            )
