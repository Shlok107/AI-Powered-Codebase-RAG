import hashlib
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.db.models import (
    BackgroundJob,
    CodeChunk,
    JobStatus,
    JobType,
    Repository,
    RepositoryFile,
    RepositoryStatus,
    SecurityFinding,
    SecurityScan,
    ScanStatus,
)
from app.services.retrieval import RetrievalService


pytestmark = [pytest.mark.integration, pytest.mark.database]


def make_file(repository_id: uuid.UUID, relative_path: str, *, status: str = "completed") -> RepositoryFile:
    return RepositoryFile(
        repository_id=repository_id,
        relative_path=relative_path,
        language="python",
        size_bytes=25,
        content_hash=hashlib.sha256(relative_path.encode()).hexdigest(),
        line_count=2,
        indexing_status=status,
    )


def make_chunk(repository_id: uuid.UUID, file_id: uuid.UUID, text: str, embedding: list[float]) -> CodeChunk:
    return CodeChunk(
        repository_id=repository_id,
        file_id=file_id,
        start_line=1,
        end_line=2,
        language="python",
        chunk_type="function",
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        text=text,
        embedding=embedding,
        chunk_metadata={"symbol": "query"},
    )


@pytest.mark.asyncio
async def test_postgresql_models_persist_relationships_vectors_and_job_scan_findings(
    db_session, repository_factory
) -> None:
    repository = repository_factory(status=RepositoryStatus.INDEXED, file_count=1, chunk_count=1)
    file = make_file(repository.id, "src/main.py")
    job = BackgroundJob(repository_id=repository.id, job_type=JobType.INDEXING, status=JobStatus.COMPLETED)
    scan = SecurityScan(repository_id=repository.id, status=ScanStatus.COMPLETED)
    db_session.add_all([repository, file, job, scan])
    await db_session.flush()
    chunk = make_chunk(repository.id, file.id, "def query(): return 42", [1.0] + [0.0] * 383)
    finding = SecurityFinding(
        scan_id=scan.id,
        repository_id=repository.id,
        rule_id="DANGEROUS_EVAL_EXEC",
        title="Dynamic evaluation",
        category="dangerous_code",
        severity="high",
        confidence="high",
        file_path=file.relative_path,
        start_line=2,
        end_line=2,
        redacted_evidence="eval(user_input)",
        explanation="Untrusted expression is evaluated.",
        remediation="Use literal parsing or explicit handlers.",
        references=[],
        status="open",
        content_hash=hashlib.sha256(b"dynamic-eval").hexdigest(),
    )
    db_session.add_all([chunk, finding])
    await db_session.commit()

    persisted = await db_session.scalar(
        select(Repository)
        .where(Repository.id == repository.id)
        .options(
            selectinload(Repository.files),
            selectinload(Repository.chunks),
            selectinload(Repository.jobs),
            selectinload(Repository.scans).selectinload(SecurityScan.findings),
        )
    )

    assert persisted is not None
    assert persisted.files[0].relative_path == "src/main.py"
    assert persisted.chunks[0].embedding == [1.0] + [0.0] * 383
    assert persisted.jobs[0].status == JobStatus.COMPLETED
    assert persisted.scans[0].findings[0].rule_id == "DANGEROUS_EVAL_EXEC"


@pytest.mark.asyncio
async def test_nested_transaction_rollback_keeps_test_database_clean(db_session, repository_factory) -> None:
    repo = repository_factory(display_name="rolled-back-project")
    db_session.add(repo)
    await db_session.flush()
    repo_id = repo.id

    await db_session.rollback()

    assert await db_session.get(Repository, repo_id) is None


@pytest.mark.asyncio
async def test_repository_file_unique_path_constraint_is_enforced(db_session, repository_factory) -> None:
    repo = repository_factory()
    db_session.add(repo)
    await db_session.flush()
    db_session.add_all([make_file(repo.id, "src/duplicate.py"), make_file(repo.id, "src/duplicate.py")])

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_keyword_retrieval_and_file_path_enrichment_use_postgresql_fts(
    db_session, repository_factory
) -> None:
    repo = repository_factory(status=RepositoryStatus.INDEXED)
    source_file = make_file(repo.id, "src/retrieval.py")
    db_session.add_all([repo, source_file])
    await db_session.flush()
    chunk = make_chunk(repo.id, source_file.id, "def safeguard_session(): return session.rollback()", [1.0] + [0.0] * 383)
    db_session.add(chunk)
    await db_session.commit()

    service = RetrievalService(embedding_provider=object())
    hits = await service._keyword_search(db_session, repo.id, "safeguard session", limit=5)
    enriched = await service.enrich_with_file_paths(db_session, hits)

    assert len(hits) == 1
    assert hits[0].chunk_id == chunk.id
    assert hits[0].keyword_score > 0
    assert enriched[0].file_path == "src/retrieval.py"
    assert await service._keyword_search(db_session, repo.id, "term-not-present", limit=5) == []


@pytest.mark.asyncio
async def test_vector_and_hybrid_retrieval_use_pgvector_and_actual_chunk_rows(db_session, repository_factory) -> None:
    repo = repository_factory(status=RepositoryStatus.INDEXED)
    vector_file = make_file(repo.id, "src/vector.py")
    keyword_file = make_file(repo.id, "src/keyword.py")
    db_session.add_all([repo, vector_file, keyword_file])
    await db_session.flush()
    vector_chunk = make_chunk(repo.id, vector_file.id, "nearest vector candidate", [1.0] + [0.0] * 383)
    both_chunk = make_chunk(repo.id, keyword_file.id, "safeguard session handler", [0.8, 0.6] + [0.0] * 382)
    db_session.add_all([vector_chunk, both_chunk])
    await db_session.commit()

    class QueryEmbeddingProvider:
        async def embed_text(self, _query: str) -> list[float]:
            return [1.0] + [0.0] * 383

    service = RetrievalService(QueryEmbeddingProvider())
    vector_results = await service._vector_search(db_session, repo.id, [1.0] + [0.0] * 383, limit=10)
    hybrid_results = await service.retrieve(db_session, repo.id, "safeguard session", top_k=5)
    await service.enrich_with_file_paths(db_session, hybrid_results)

    assert vector_results[0].chunk_id == vector_chunk.id
    assert vector_results[0].vector_score == pytest.approx(1.0)
    assert {item.chunk_id for item in hybrid_results} == {vector_chunk.id, both_chunk.id}
    assert next(item for item in hybrid_results if item.chunk_id == both_chunk.id).file_path == "src/keyword.py"
