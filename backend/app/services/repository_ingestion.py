import hashlib
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Repository, RepositoryFile, RepositoryStatus
from app.services.safe_archive import SafeArchiveExtractor, ExtractResult, ExtractedFile
from app.services.storage import get_storage
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def ingest_repository(
    session: AsyncSession,
    repository_id: uuid.UUID,
    extract_result: ExtractResult,
) -> None:
    """Ingest extracted repository files into database and persistent storage."""
    repository = await session.get(Repository, repository_id)
    if not repository:
        raise ValueError(f"Repository {repository_id} not found")

    repository.status = RepositoryStatus.PROCESSING
    await session.flush()

    storage = get_storage()
    source_path, _ = storage.create_repo_storage(repository_id)

    file_records = []

    # Process each extracted file
    for extracted_file in extract_result.files:
        rel_path = Path(extracted_file.relative_path)
        rel_path_str = str(rel_path).replace("\\", "/")  # Normalize to forward slashes

        # Write to persistent storage
        dest_path = source_path / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(extracted_file.content, encoding="utf-8")

        # Create file record
        repo_file = RepositoryFile(
            repository_id=repository_id,
            relative_path=rel_path_str,
            language=extracted_file.language,
            size_bytes=extracted_file.size_bytes,
            content_hash=extracted_file.content_hash,
            line_count=extracted_file.line_count,
            indexing_status="pending",
        )
        file_records.append(repo_file)

    session.add_all(file_records)
    repository.file_count = len(file_records)
    repository.detected_languages = extract_result.languages
    await session.commit()

    logger.info(
        "repository_ingested",
        repository_id=str(repository_id),
        file_count=len(file_records),
        languages=extract_result.languages,
    )