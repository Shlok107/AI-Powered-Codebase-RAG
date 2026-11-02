import hashlib
import os
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


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
                    if len(zf.infolist()) > self.max_files:
                        raise ArchiveValidationError(
                            f"Archive contains too many files: {len(zf.infolist())} > {self.max_files}"
                        )

                    total_uncompressed = 0
                    file_count = 0
                    languages = set()
                    extracted_files = []

                    for info in zf.infolist():
                        # Skip directories
                        if info.is_dir():
                            continue

                        # Check for path traversal
                        if os.path.isabs(info.filename) or ".." in info.filename:
                            raise ArchiveValidationError(f"Path traversal attempt detected: {info.filename}")

                        # Normalize path - handle both forward and backward slashes
                        normalized_filename = info.filename.replace("\\", "/")
                        
                        # Check for path traversal after normalization
                        if ".." in normalized_filename.split("/"):
                            raise ArchiveValidationError(f"Path traversal attempt detected: {info.filename}")

                        # Normalize path
                        normalized_path = (extract_path / normalized_filename).resolve()
                        try:
                            normalized_path.relative_to(extract_path.resolve())
                        except ValueError:
                            raise ArchiveValidationError(f"Path escapes extraction directory: {info.filename}")

                        # Check file size
                        if info.file_size > self.max_single_file_bytes:
                            logger.warning("skipping_large_file", filename=info.filename, size=info.file_size)
                            continue

                        total_uncompressed += info.file_size
                        if total_uncompressed > self.max_uncompressed_bytes:
                            raise ArchiveValidationError(
                                f"Total uncompressed size exceeds limit: {total_uncompressed} > {self.max_uncompressed_bytes}"
                            )

                        # Check if file should be processed
                        rel_path = Path(normalized_filename)
                        if self._is_ignored_path(rel_path):
                            continue

                        if not self._is_supported_file(rel_path):
                            continue

                        file_count += 1
                        lang = self._detect_language(rel_path)
                        if lang:
                            languages.add(lang)

                        # Read file content directly from ZIP (avoids filesystem path issues)
                        try:
                            raw_content = zf.read(info)
                            content = raw_content.decode("utf-8", errors="replace")
                        except Exception:
                            content = ""
                        
                        content_hash = hashlib.sha256(content.encode()).hexdigest()
                        line_count = content.count("\n") + 1 if content else 0
                        size_bytes = info.file_size
                        
                        extracted_files.append(ExtractedFile(
                            relative_path=normalized_filename,
                            content=content,
                            size_bytes=size_bytes,
                            language=lang,
                            line_count=line_count,
                            content_hash=content_hash,
                        ))

            except zipfile.BadZipFile as e:
                raise ArchiveValidationError(f"Invalid ZIP file: {str(e)}")

            return ExtractResult(
                files=extracted_files,
                languages=sorted(languages),
                total_size=total_uncompressed,
            )