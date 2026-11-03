import hashlib
import os
import shutil
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RepositoryStorage:
    """Manages persistent storage for repository files."""

    def __init__(self, base_path: Optional[str] = None):
        if base_path:
            self.base_path = Path(base_path)
        else:
            # Default to a local directory
            self.base_path = Path(os.getenv("REPOSITORY_STORAGE_PATH", "./data/repositories"))
        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_repo_path(self, repository_id: uuid.UUID) -> Path:
        """Get the storage path for a repository."""
        return self.base_path / str(repository_id)

    def get_repo_source_path(self, repository_id: uuid.UUID) -> Path:
        """Get the source code path for a repository."""
        return self.get_repo_path(repository_id) / "source"

    def get_repo_meta_path(self, repository_id: uuid.UUID) -> Path:
        """Get the metadata path for a repository."""
        return self.get_repo_path(repository_id) / "meta"

    def create_repo_storage(self, repository_id: uuid.UUID) -> tuple[Path, Path]:
        """Create storage directories for a repository."""
        source_path = self.get_repo_source_path(repository_id)
        meta_path = self.get_repo_meta_path(repository_id)
        source_path.mkdir(parents=True, exist_ok=True)
        meta_path.mkdir(parents=True, exist_ok=True)
        return source_path, meta_path

    def delete_repo_storage(self, repository_id: uuid.UUID) -> bool:
        """Delete all storage for a repository."""
        repo_path = self.get_repo_path(repository_id)
        if repo_path.exists():
            shutil.rmtree(repo_path)
            logger.info("deleted_repo_storage", repository_id=str(repository_id))
            return True
        return False

    def repo_exists(self, repository_id: uuid.UUID) -> bool:
        """Check if repository storage exists."""
        return self.get_repo_path(repository_id).exists()

    def get_file_path(self, repository_id: uuid.UUID, relative_path: str) -> Path:
        """Get the absolute path for a repository file."""
        normalized = relative_path.replace("\\", "/")
        posix_path = PurePosixPath(normalized)
        windows_path = PureWindowsPath(relative_path)
        if (
            not relative_path
            or posix_path.is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.drive)
            or ".." in posix_path.parts
        ):
            raise ValueError("Repository file path must be relative to its source directory")

        source_root = self.get_repo_source_path(repository_id).resolve()
        file_path = (source_root / Path(*posix_path.parts)).resolve()
        try:
            file_path.relative_to(source_root)
        except ValueError as exc:
            raise ValueError("Repository file path escapes its source directory") from exc
        return file_path

    def read_file(self, repository_id: uuid.UUID, relative_path: str) -> Optional[str]:
        """Read a file from repository storage."""
        file_path = self.get_file_path(repository_id, relative_path)
        if not file_path.exists():
            return None
        try:
            return file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

    def get_file_size(self, repository_id: uuid.UUID, relative_path: str) -> Optional[int]:
        """Get file size in bytes."""
        file_path = self.get_file_path(repository_id, relative_path)
        if not file_path.exists():
            return None
        return file_path.stat().st_size


# Global storage instance
_storage: Optional[RepositoryStorage] = None


def get_storage() -> RepositoryStorage:
    """Get the global storage instance."""
    global _storage
    if _storage is None:
        _storage = RepositoryStorage()
    return _storage
