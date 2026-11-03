import uuid
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import session_context
from app.db.models import Repository, RepositoryFile, CodeChunk, BackgroundJob, JobStatus, RepositoryStatus
from app.services.chunking import get_chunker
from app.services.embeddings import create_embedding_provider
from app.services.storage import get_storage
from app.core.logging import get_logger

logger = get_logger(__name__)


async def run_indexing_job(repository_id: str, job_id: str | None = None) -> None:
    """Run indexing job for a repository."""
    async with session_context() as session:
        repo_uuid = uuid.UUID(repository_id)
        repository = await session.get(Repository, repo_uuid)

        if not repository:
            logger.error("repository_not_found", repository_id=repository_id)
            return

        # Update job status if provided
        if job_id:
            job = await session.get(BackgroundJob, uuid.UUID(job_id))
            if job:
                job.status = JobStatus.PROCESSING
                from datetime import datetime
                job.started_at = datetime.utcnow()
                await session.commit()

        repository.status = RepositoryStatus.PROCESSING
        await session.commit()

        try:
            logger.info("indexing_started", repository_id=repository_id)

            # Get files to index
            files_result = await session.execute(
                select(RepositoryFile).where(
                    RepositoryFile.repository_id == repo_uuid,
                    RepositoryFile.indexing_status == "pending"
                )
            )
            files = files_result.scalars().all()

            if not files:
                logger.warning("no_files_to_index", repository_id=repository_id)
                repository.status = RepositoryStatus.FAILED
                repository.error_summary = "No indexable files found in repository"
                from datetime import datetime
                repository.indexed_at = datetime.utcnow()
                repository.chunk_count = 0
                await session.commit()

                if job_id:
                    job = await session.get(BackgroundJob, uuid.UUID(job_id))
                    if job:
                        job.status = JobStatus.FAILED
                        job.completed_at = datetime.utcnow()
                        job.error_message = "No indexable files found in repository"
                        await session.commit()
                return

            # Initialize providers
            chunker_cache = {}
            embedding_provider = create_embedding_provider()

            # Check if provider is configured (NoOpEmbeddingProvider means not configured)
            if embedding_provider.__class__.__name__ == "NoOpEmbeddingProvider":
                logger.warning("embedding_provider_not_configured", repository_id=repository_id)

            storage = get_storage()
            total_chunks = 0
            processed_files = 0

            # Update job total items
            if job_id:
                job = await session.get(BackgroundJob, uuid.UUID(job_id))
                if job:
                    job.total_items = len(files)
                    await session.commit()

            for repo_file in files:
                try:
                    # Read file content from storage
                    content = storage.read_file(repo_uuid, repo_file.relative_path)
                    if content is None:
                        logger.warning("file_not_found_in_storage", path=repo_file.relative_path)
                        repo_file.indexing_status = "failed"
                        repo_file.skip_reason = "File not found in storage"
                        await session.commit()
                        continue

                    # Get chunker for language
                    language = repo_file.language or "unknown"
                    if language not in chunker_cache:
                        chunker_cache[language] = get_chunker(language)
                    chunker = chunker_cache[language]

                    # Chunk the file
                    chunks = chunker.chunk(repo_file.relative_path, content)

                    if not chunks:
                        logger.info("no_chunks_generated", file=repo_file.relative_path)
                        repo_file.indexing_status = "completed"
                        await session.commit()
                        continue

                    # Generate embeddings for all chunks
                    chunk_texts = [chunk.text for chunk in chunks]
                    embeddings = await embedding_provider.embed_batch(chunk_texts)

                    # Validate embeddings dimension
                    expected_dim = embedding_provider.dimensions
                    valid_embeddings = []
                    for i, emb in enumerate(embeddings):
                        if len(emb) == expected_dim:
                            valid_embeddings.append((i, emb))
                        else:
                            logger.warning(
                                "embedding_dimension_mismatch",
                                expected=expected_dim,
                                got=len(emb),
                                file=repo_file.relative_path,
                                chunk_index=i,
                            )

                    # Store chunks with embeddings
                    chunk_records = []
                    for i, chunk in enumerate(chunks):
                        # Find matching embedding
                        embedding = None
                        for idx, emb in valid_embeddings:
                            if idx == i:
                                embedding = emb
                                break

                        # If no valid embedding, use zero vector
                        if embedding is None:
                            embedding = [0.0] * expected_dim

                        chunk_record = CodeChunk(
                            repository_id=repo_uuid,
                            file_id=repo_file.id,
                            start_line=chunk.start_line,
                            end_line=chunk.end_line,
                            language=chunk.language,
                            chunk_type=chunk.chunk_type,
                            content_hash=chunk.content_hash,
                            text=chunk.text,
                            embedding=embedding,
                            chunk_metadata=chunk.metadata,
                        )
                        chunk_records.append(chunk_record)

                    # Bulk insert chunks
                    session.add_all(chunk_records)
                    total_chunks += len(chunk_records)
                    repo_file.indexing_status = "completed"
                    processed_files += 1

                    # Update progress
                    if job_id:
                        job = await session.get(BackgroundJob, uuid.UUID(job_id))
                        if job:
                            job.processed_items = processed_files
                            job.progress = int((processed_files / len(files)) * 100)
                            await session.commit()

                    logger.info(
                        "file_indexed",
                        repository_id=repository_id,
                        file=repo_file.relative_path,
                        chunks=len(chunk_records),
                    )

                except Exception as e:
                    logger.error(
                        "file_indexing_failed",
                        repository_id=repository_id,
                        file=repo_file.relative_path,
                        error_type=type(e).__name__,
                    )
                    repo_file.indexing_status = "failed"
                    repo_file.skip_reason = "File could not be indexed due to an internal error."
                    await session.commit()

            # Update repository status - only mark as indexed if we have chunks
            if total_chunks == 0:
                logger.warning("no_chunks_generated", repository_id=repository_id)
                repository.status = RepositoryStatus.FAILED
                repository.error_summary = "No chunks generated from repository files"
                from datetime import datetime
                repository.indexed_at = datetime.utcnow()
                repository.chunk_count = 0
            else:
                repository.chunk_count = total_chunks
                repository.status = RepositoryStatus.INDEXED
                from datetime import datetime
                repository.indexed_at = datetime.utcnow()

            if job_id:
                job = await session.get(BackgroundJob, uuid.UUID(job_id))
                if job:
                    job.status = JobStatus.COMPLETED if total_chunks > 0 else JobStatus.FAILED
                    job.completed_at = datetime.utcnow()
                    job.progress = 100
                    job.processed_items = job.total_items
                    if total_chunks == 0:
                        job.error_message = "No chunks generated from repository files"

            await session.commit()
            logger.info(
                "indexing_completed",
                repository_id=repository_id,
                total_chunks=total_chunks,
                processed_files=processed_files,
            )

        except Exception as e:
            repository.status = RepositoryStatus.FAILED
            repository.error_summary = "Indexing failed due to an internal error."

            if job_id:
                job = await session.get(BackgroundJob, uuid.UUID(job_id))
                if job:
                    job.status = JobStatus.FAILED
                    from datetime import datetime
                    job.completed_at = datetime.utcnow()
                    job.error_message = "Indexing failed due to an internal error."

            await session.commit()
            logger.error("indexing_failed", repository_id=repository_id, error_type=type(e).__name__)


from datetime import datetime
