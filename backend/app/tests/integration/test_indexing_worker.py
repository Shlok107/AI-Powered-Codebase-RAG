import hashlib
import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select

from app.db.models import BackgroundJob, CodeChunk, JobStatus, JobType, Repository, RepositoryFile, RepositoryStatus
from app.services.storage import RepositoryStorage
from app.workers import indexing_worker


pytestmark = [pytest.mark.integration, pytest.mark.database]


class FixedEmbeddingProvider:
    dimensions = 384

    def __init__(self, *, failure: Exception | None = None, vector_size: int = 384):
        self.failure = failure
        self.vector_size = vector_size

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self.failure:
            raise self.failure
        return [[0.125] * self.vector_size for _ in texts]


def make_repository_file(repository_id: uuid.UUID, path: str, source: str) -> RepositoryFile:
    return RepositoryFile(
        repository_id=repository_id,
        relative_path=path,
        language="python",
        size_bytes=len(source.encode()),
        content_hash=hashlib.sha256(source.encode()).hexdigest(),
        line_count=len(source.splitlines()),
        indexing_status="pending",
    )


def worker_context(session):
    @asynccontextmanager
    async def context():
        yield session

    return context


async def add_job(db_session, repository_id: uuid.UUID) -> BackgroundJob:
    job = BackgroundJob(repository_id=repository_id, job_type=JobType.INDEXING, status=JobStatus.QUEUED)
    db_session.add(job)
    await db_session.commit()
    return job


@pytest.mark.asyncio
async def test_indexing_worker_persists_chunks_embeddings_and_success_transitions(
    db_session, repository_factory, monkeypatch, tmp_path
) -> None:
    source = "def answer():\n    return 42\n"
    repository = repository_factory(status=RepositoryStatus.PENDING)
    repo_file = make_repository_file(repository.id, "src/main.py", source)
    db_session.add_all([repository, repo_file])
    await db_session.commit()
    job = await add_job(db_session, repository.id)
    storage = RepositoryStorage(str(tmp_path / "storage"))
    source_dir, _ = storage.create_repo_storage(repository.id)
    (source_dir / "src").mkdir(parents=True)
    (source_dir / "src" / "main.py").write_text(source, encoding="utf-8")
    monkeypatch.setattr(indexing_worker, "session_context", worker_context(db_session))
    monkeypatch.setattr(indexing_worker, "get_storage", lambda: storage)
    monkeypatch.setattr(indexing_worker, "create_embedding_provider", FixedEmbeddingProvider)

    await indexing_worker.run_indexing_job(str(repository.id), str(job.id))

    await db_session.refresh(repository)
    await db_session.refresh(repo_file)
    await db_session.refresh(job)
    chunks = (
        await db_session.execute(select(CodeChunk).where(CodeChunk.repository_id == repository.id))
    ).scalars().all()
    assert repository.status == RepositoryStatus.INDEXED
    assert repository.chunk_count == 1
    assert repo_file.indexing_status == "completed"
    assert job.status == JobStatus.COMPLETED
    assert job.progress == 100
    assert job.total_items == job.processed_items == 1
    assert len(chunks) == 1
    assert len(chunks[0].embedding) == 384
    assert chunks[0].text == "def answer():\n    return 42"


@pytest.mark.asyncio
async def test_indexing_worker_marks_repository_and_job_failed_when_there_are_no_files(
    db_session, repository_factory, monkeypatch
) -> None:
    repository = repository_factory(id=uuid.uuid4(), status=RepositoryStatus.PROCESSING)
    db_session.add(repository)
    await db_session.commit()
    job = await add_job(db_session, repository.id)
    monkeypatch.setattr(indexing_worker, "session_context", worker_context(db_session))

    await indexing_worker.run_indexing_job(str(repository.id), str(job.id))

    await db_session.refresh(repository)
    await db_session.refresh(job)
    assert repository.status == RepositoryStatus.FAILED
    assert repository.chunk_count == 0
    assert repository.error_summary == "No indexable files found in repository"
    assert job.status == JobStatus.FAILED
    assert job.error_message == repository.error_summary


@pytest.mark.asyncio
async def test_indexing_worker_keeps_partial_file_failures_visible_when_other_files_succeed(
    db_session, repository_factory, monkeypatch, tmp_path
) -> None:
    source = "def available():\n    return True\n"
    repository = repository_factory(status=RepositoryStatus.PENDING)
    good_file = make_repository_file(repository.id, "src/good.py", source)
    missing_file = make_repository_file(repository.id, "src/missing.py", "def missing(): pass")
    db_session.add_all([repository, good_file, missing_file])
    await db_session.commit()
    job = await add_job(db_session, repository.id)
    storage = RepositoryStorage(str(tmp_path / "storage"))
    source_dir, _ = storage.create_repo_storage(repository.id)
    (source_dir / "src").mkdir(parents=True)
    (source_dir / "src" / "good.py").write_text(source, encoding="utf-8")
    monkeypatch.setattr(indexing_worker, "session_context", worker_context(db_session))
    monkeypatch.setattr(indexing_worker, "get_storage", lambda: storage)
    monkeypatch.setattr(indexing_worker, "create_embedding_provider", FixedEmbeddingProvider)

    await indexing_worker.run_indexing_job(str(repository.id), str(job.id))

    await db_session.refresh(repository)
    await db_session.refresh(good_file)
    await db_session.refresh(missing_file)
    await db_session.refresh(job)
    assert repository.status == RepositoryStatus.INDEXED
    assert repository.chunk_count == 1
    assert good_file.indexing_status == "completed"
    assert missing_file.indexing_status == "failed"
    assert missing_file.skip_reason == "File not found in storage"
    assert job.status == JobStatus.COMPLETED
    assert job.processed_items == 2


@pytest.mark.asyncio
async def test_embedding_failure_does_not_mark_indexing_as_success(
    db_session, repository_factory, monkeypatch, tmp_path
) -> None:
    source = "def answer():\n    return 42\n"
    repository = repository_factory(status=RepositoryStatus.PENDING)
    repo_file = make_repository_file(repository.id, "src/main.py", source)
    db_session.add_all([repository, repo_file])
    await db_session.commit()
    job = await add_job(db_session, repository.id)
    storage = RepositoryStorage(str(tmp_path / "storage"))
    source_dir, _ = storage.create_repo_storage(repository.id)
    (source_dir / "src").mkdir(parents=True)
    (source_dir / "src" / "main.py").write_text(source, encoding="utf-8")
    monkeypatch.setattr(indexing_worker, "session_context", worker_context(db_session))
    monkeypatch.setattr(indexing_worker, "get_storage", lambda: storage)
    monkeypatch.setattr(
        indexing_worker,
        "create_embedding_provider",
        lambda: FixedEmbeddingProvider(failure=RuntimeError("provider secret at C:\\private\\token")),
    )

    await indexing_worker.run_indexing_job(str(repository.id), str(job.id))

    await db_session.refresh(repository)
    await db_session.refresh(repo_file)
    await db_session.refresh(job)
    assert repository.status == RepositoryStatus.FAILED
    assert repository.chunk_count == 0
    assert repository.error_summary == "No chunks generated from repository files"
    assert repo_file.indexing_status == "failed"
    assert repo_file.skip_reason == "File could not be indexed due to an internal error."
    assert "private" not in repo_file.skip_reason
    assert job.status == JobStatus.FAILED
    assert job.error_message == repository.error_summary


@pytest.mark.asyncio
async def test_embedding_dimension_mismatch_uses_384_zero_vector_and_completes_indexing(
    db_session, repository_factory, monkeypatch, tmp_path
) -> None:
    source = "def answer():\n    return 42\n"
    repository = repository_factory(status=RepositoryStatus.PENDING)
    repo_file = make_repository_file(repository.id, "src/main.py", source)
    db_session.add_all([repository, repo_file])
    await db_session.commit()
    storage = RepositoryStorage(str(tmp_path / "storage"))
    source_dir, _ = storage.create_repo_storage(repository.id)
    (source_dir / "src").mkdir(parents=True)
    (source_dir / "src" / "main.py").write_text(source, encoding="utf-8")
    monkeypatch.setattr(indexing_worker, "session_context", worker_context(db_session))
    monkeypatch.setattr(indexing_worker, "get_storage", lambda: storage)
    monkeypatch.setattr(indexing_worker, "create_embedding_provider", lambda: FixedEmbeddingProvider(vector_size=3))

    await indexing_worker.run_indexing_job(str(repository.id))

    await db_session.refresh(repository)
    chunk = await db_session.scalar(select(CodeChunk).where(CodeChunk.repository_id == repository.id))
    assert repository.status == RepositoryStatus.INDEXED
    assert chunk is not None
    assert chunk.embedding == [0.0] * 384


@pytest.mark.asyncio
async def test_database_query_failure_marks_repository_failed_instead_of_stuck_processing(
    repository_factory, monkeypatch
) -> None:
    repository = repository_factory(id=uuid.uuid4(), status=RepositoryStatus.PROCESSING)

    class BrokenSession:
        async def get(self, model, _identifier):
            return repository if model is Repository else None

        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("database password secret-value")

        async def commit(self):
            return None

    monkeypatch.setattr(indexing_worker, "session_context", worker_context(BrokenSession()))

    await indexing_worker.run_indexing_job(str(repository.id))

    assert repository.status == RepositoryStatus.FAILED
    assert repository.error_summary == "Indexing failed due to an internal error."
    assert "secret-value" not in repository.error_summary
