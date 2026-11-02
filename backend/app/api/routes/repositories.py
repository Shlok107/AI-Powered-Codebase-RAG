import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationError
from app.db.session import get_session
from app.db.models import Repository, RepositoryFile, RepositoryStatus, RepositorySourceType
from app.schemas import (
    RepositoryCreate,
    RepositoryRead,
    RepositoryDetail,
    RepositoryListResponse,
    FileRead,
    FileContentRequest,
    FileContentResponse,
    IndexRequest,
    JobRead,
)
from app.services.repository_ingestion import ingest_repository
from app.services.safe_archive import SafeArchiveExtractor, ArchiveValidationError

router = APIRouter()
settings = get_settings()


@router.get("", response_model=RepositoryListResponse)
async def list_repositories(
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
    offset: int = 0,
):
    """List all repositories with pagination."""
    # Get total count
    count_result = await session.execute(select(func.count(Repository.id)))
    total = count_result.scalar_one()

    # Get repositories
    result = await session.execute(
        select(Repository)
        .order_by(Repository.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    repositories = result.scalars().all()

    return RepositoryListResponse(
        repositories=[RepositoryRead.model_validate(r) for r in repositories],
        total=total,
    )


@router.post("/upload", response_model=RepositoryRead, status_code=status.HTTP_201_CREATED)
async def upload_repository(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Upload and ingest a repository ZIP file."""
    # Validate file type
    if not file.filename or not file.filename.endswith(".zip"):
        raise ValidationError("Only ZIP files are allowed")

    # Check file size
    max_size = settings.max_upload_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise ValidationError(f"File size exceeds maximum of {settings.max_upload_mb} MB")

    # Create repository record
    repository = Repository(
        display_name=file.filename.replace(".zip", ""),
        source_type=RepositorySourceType.ZIP_UPLOAD,
        source_metadata={"original_filename": file.filename, "size_bytes": len(content)},
        status=RepositoryStatus.PROCESSING,
    )
    session.add(repository)
    await session.flush()

    # Extract and process archive
    try:
        extractor = SafeArchiveExtractor(settings)
        extract_result = await extractor.extract(content, str(repository.id))

        # Ingest repository files into persistent storage and database
        await ingest_repository(session, repository.id, extract_result)

        # Update repository with file info
        repository.file_count = extract_result.file_count
        repository.detected_languages = extract_result.languages
        repository.status = RepositoryStatus.PENDING  # Will be updated to INDEXED after indexing
        await session.commit()

        # Refresh the repository to load updated fields (like updated_at)
        await session.refresh(repository)

        # Trigger indexing job (async in background)
        # For now, run inline for simplicity - in production this would be a background job
        from app.workers.indexing_worker import run_indexing_job
        import asyncio
        asyncio.create_task(run_indexing_job(str(repository.id)))

    except ArchiveValidationError as e:
        repository.status = RepositoryStatus.FAILED
        repository.error_summary = str(e)
        await session.commit()
        raise ValidationError(str(e))
    except Exception as e:
        repository.status = RepositoryStatus.FAILED
        repository.error_summary = f"Processing failed: {str(e)}"
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process repository: {str(e)}",
        )

    return RepositoryRead.model_validate(repository)


@router.get("/{repository_id:uuid}", response_model=RepositoryDetail)
async def get_repository(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get repository details."""
    result = await session.execute(
        select(Repository).where(Repository.id == repository_id)
    )
    repository = result.scalar_one_or_none()

    if not repository:
        raise NotFoundError("Repository", str(repository_id))

    return RepositoryDetail.model_validate(repository)


@router.delete("/{repository_id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Delete a repository and all associated data."""
    result = await session.execute(
        select(Repository).where(Repository.id == repository_id)
    )
    repository = result.scalar_one_or_none()

    if not repository:
        raise NotFoundError("Repository", str(repository_id))

    await session.delete(repository)
    await session.commit()


@router.get("/{repository_id:uuid}/files", response_model=list[FileRead])
async def list_repository_files(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    limit: int = 100,
    offset: int = 0,
):
    """List files in a repository."""
    # Verify repository exists
    repo_result = await session.execute(
        select(Repository.id).where(Repository.id == repository_id)
    )
    if not repo_result.scalar_one_or_none():
        raise NotFoundError("Repository", str(repository_id))

    result = await session.execute(
        select(RepositoryFile)
        .where(RepositoryFile.repository_id == repository_id)
        .order_by(RepositoryFile.relative_path)
        .limit(limit)
        .offset(offset)
    )
    files = result.scalars().all()

    return [FileRead.model_validate(f) for f in files]


@router.get("/{repository_id:uuid}/files/content", response_model=FileContentResponse)
async def get_file_content(
    repository_id: uuid.UUID,
    request: FileContentRequest = Depends(),
    session: AsyncSession = Depends(get_session),
):
    """Get file content with line range."""
    # Verify repository exists
    repo_result = await session.execute(
        select(Repository.id).where(Repository.id == repository_id)
    )
    if not repo_result.scalar_one_or_none():
        raise NotFoundError("Repository", str(repository_id))

    # Get file
    result = await session.execute(
        select(RepositoryFile).where(
            RepositoryFile.repository_id == repository_id,
            RepositoryFile.relative_path == request.path,
        )
    )
    file = result.scalar_one_or_none()

    if not file:
        raise NotFoundError("File", request.path)

    # For now, we don't store full file content in DB
    # In a full implementation, we'd read from extracted archive or storage
    # Return a placeholder indicating content not available via this endpoint
    return FileContentResponse(
        path=file.relative_path,
        language=file.language,
        content="File content not stored in database. Use chunk retrieval for source code.",
        start_line=request.start_line or 1,
        end_line=request.end_line or file.line_count,
        total_lines=file.line_count,
    )


@router.post("/{repository_id:uuid}/index", response_model=JobRead)
async def trigger_indexing(
    repository_id: uuid.UUID,
    request: IndexRequest,
    session: AsyncSession = Depends(get_session),
):
    """Trigger or retry indexing for a repository."""
    result = await session.execute(
        select(Repository).where(Repository.id == repository_id)
    )
    repository = result.scalar_one_or_none()

    if not repository:
        raise NotFoundError("Repository", str(repository_id))

    # Create indexing job
    from app.db.models import BackgroundJob, JobType, JobStatus
    job = BackgroundJob(
        repository_id=repository_id,
        job_type=JobType.INDEXING,
        status=JobStatus.QUEUED,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Trigger background job
    from app.workers.indexing_worker import run_indexing_job
    import asyncio
    asyncio.create_task(run_indexing_job(str(repository_id), str(job.id)))

    return JobRead.model_validate(job)