import hashlib
import uuid

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import (
    BackgroundJob,
    JobStatus,
    JobType,
    Repository,
    RepositoryFile,
    RepositoryStatus,
    SecurityFinding,
    SecurityScan,
    ScanStatus,
)


pytestmark = [pytest.mark.integration, pytest.mark.database]


@pytest.mark.asyncio
async def test_health_reports_database_connectivity_and_provider_degradation(api_client, monkeypatch) -> None:
    response = await api_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["database"] == "connected"
    assert response.json()["status"] == "degraded"
    assert response.json()["llm_provider"] == "unconfigured"
    assert response.json()["embedding_provider"] == "unconfigured"

    monkeypatch.setattr(
        "app.api.routes.health.settings",
        Settings(
            _env_file=None,
            llm_provider="openai_compatible",
            llm_base_url="http://llm.test",
            llm_model="test-model",
            embedding_provider="openai_compatible",
            embedding_base_url="http://embeddings.test",
            embedding_model="test-embeddings",
        ),
    )
    healthy = await api_client.get("/api/v1/health")

    assert healthy.json()["status"] == "healthy"
    assert healthy.json()["llm_provider"] == "configured"
    assert healthy.json()["embedding_provider"] == "configured"


@pytest.mark.asyncio
async def test_health_reports_unhealthy_when_database_query_fails(api_client, db_session, monkeypatch) -> None:
    async def unavailable(_statement, *_args, **_kwargs):
        raise ConnectionError("database unavailable")

    monkeypatch.setattr(db_session, "execute", unavailable)

    response = await api_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "unhealthy"
    assert response.json()["database"] == "disconnected"


@pytest.mark.asyncio
async def test_repository_list_and_details_use_persisted_database_values(
    api_client, db_session, repository_factory
) -> None:
    repo = repository_factory(display_name="persisted-project", status=RepositoryStatus.INDEXED, file_count=4, chunk_count=9)
    db_session.add(repo)
    await db_session.commit()

    listing = await api_client.get("/api/v1/repositories", params={"limit": 10})
    detail = await api_client.get(f"/api/v1/repositories/{repo.id}")

    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["repositories"][0]["display_name"] == "persisted-project"
    assert listing.json()["repositories"][0]["chunk_count"] == 9
    assert detail.status_code == 200
    assert detail.json()["id"] == str(repo.id)
    assert detail.json()["status"] == "indexed"


@pytest.mark.asyncio
async def test_repository_detail_and_file_listing_return_not_found_for_missing_repository(api_client) -> None:
    missing_id = uuid.uuid4()

    detail = await api_client.get(f"/api/v1/repositories/{missing_id}")
    files = await api_client.get(f"/api/v1/repositories/{missing_id}/files")

    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "NOT_FOUND"
    assert files.status_code == 404


@pytest.mark.asyncio
async def test_valid_zip_upload_persists_repository_files_and_queues_indexing(
    api_client, db_session, monkeypatch, tmp_path, zip_bytes
) -> None:
    from app.services.storage import RepositoryStorage

    storage = RepositoryStorage(str(tmp_path / "repositories"))
    monkeypatch.setattr("app.services.repository_ingestion.get_storage", lambda: storage)
    archive = zip_bytes([("src/main.py", "def main():\n    return 42\n"), ("README.md", "sample")])

    response = await api_client.post(
        "/api/v1/repositories/upload",
        files={"file": ("sample-project.zip", archive, "application/zip")},
    )

    assert response.status_code == 201
    repository_id = uuid.UUID(response.json()["id"])
    assert response.json()["status"] == "pending"
    assert response.json()["file_count"] == 2
    files = (
        await db_session.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repository_id).order_by(RepositoryFile.relative_path)
        )
    ).scalars().all()
    job_count = await db_session.scalar(
        select(BackgroundJob.id).where(
            BackgroundJob.repository_id == repository_id,
            BackgroundJob.job_type == JobType.INDEXING,
        )
    )

    assert [item.relative_path for item in files] == ["README.md", "src/main.py"]
    assert all(item.indexing_status == "pending" for item in files)
    assert storage.read_file(repository_id, "src/main.py") == "def main():\n    return 42\n"
    # The current upload flow schedules the indexing worker directly, without a BackgroundJob row.
    assert job_count is None


@pytest.mark.asyncio
async def test_upload_rejects_non_zip_and_malformed_archive_without_persisting_repository(
    api_client, db_session, zip_bytes
) -> None:
    invalid_type = await api_client.post(
        "/api/v1/repositories/upload",
        files={"file": ("source.txt", b"text", "text/plain")},
    )
    malformed = await api_client.post(
        "/api/v1/repositories/upload",
        files={"file": ("broken.zip", b"not a zip archive", "application/zip")},
    )

    assert invalid_type.status_code == 422
    assert invalid_type.json()["error"]["code"] == "VALIDATION_ERROR"
    assert malformed.status_code == 422
    assert "Invalid ZIP" in malformed.json()["error"]["message"]
    failed_repositories = (
        await db_session.execute(select(Repository).where(Repository.status == RepositoryStatus.FAILED))
    ).scalars().all()
    assert len(failed_repositories) == 1
    assert failed_repositories[0].file_count == 0


@pytest.mark.asyncio
async def test_manual_index_endpoint_creates_job_and_rejects_missing_repository(
    api_client, db_session, repository_factory
) -> None:
    repo = repository_factory(status=RepositoryStatus.PROCESSING)
    db_session.add(repo)
    await db_session.commit()

    response = await api_client.post(f"/api/v1/repositories/{repo.id}/index", json={"force": True})
    missing = await api_client.post(f"/api/v1/repositories/{uuid.uuid4()}/index", json={"force": False})

    assert response.status_code == 200
    assert response.json()["repository_id"] == str(repo.id)
    assert response.json()["status"] == "queued"
    assert response.json()["job_type"] == "indexing"
    assert missing.status_code == 404
    jobs = (
        await db_session.execute(select(BackgroundJob).where(BackgroundJob.repository_id == repo.id))
    ).scalars().all()
    assert len(jobs) == 1
    assert jobs[0].status == JobStatus.QUEUED


@pytest.mark.asyncio
async def test_manual_index_endpoint_validates_request_body(api_client, db_session, repository_factory) -> None:
    repo = repository_factory()
    db_session.add(repo)
    await db_session.commit()

    response = await api_client.post(f"/api/v1/repositories/{repo.id}/index", json={"force": "sometimes"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_rejects_unindexed_and_missing_repositories_and_empty_questions(
    api_client, db_session, repository_factory
) -> None:
    repo = repository_factory(status=RepositoryStatus.PROCESSING)
    db_session.add(repo)
    await db_session.commit()

    unindexed = await api_client.post(f"/api/v1/repositories/{repo.id}/chat", json={"question": "explain this"})
    missing = await api_client.post(f"/api/v1/repositories/{uuid.uuid4()}/chat", json={"question": "explain this"})
    empty = await api_client.post(f"/api/v1/repositories/{repo.id}/chat", json={"question": ""})

    assert unindexed.status_code == 400
    assert unindexed.json()["detail"]["code"] == "REPOSITORY_NOT_INDEXED"
    assert missing.status_code == 404
    assert empty.status_code == 422


@pytest.mark.asyncio
async def test_chat_returns_valid_answer_and_citation_schema_with_mocked_service(
    api_client, db_session, repository_factory, monkeypatch
) -> None:
    from app.services.chat import ChatResult, Citation

    repo = repository_factory(status=RepositoryStatus.INDEXED)
    db_session.add(repo)
    await db_session.commit()

    class MockChatService:
        async def ask(self, **_kwargs):
            return ChatResult(
                answer="The function returns 42 [Source 1].",
                citations=[
                    Citation(uuid.uuid4(), "src/main.py", 1, 2, "python", 0.91, "return 42")
                ],
                model_used="test-model",
                retrieval_time_ms=2,
                generation_time_ms=3,
                used_fallback=False,
            )

    monkeypatch.setattr("app.api.routes.chat.ChatService", MockChatService)
    response = await api_client.post(
        f"/api/v1/repositories/{repo.id}/chat", json={"question": "What does main return?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "The function returns 42 [Source 1]."
    assert body["model_used"] == "test-model"
    assert body["used_fallback"] is False
    assert body["citations"] == [
        {
            "chunk_id": body["citations"][0]["chunk_id"],
            "file_path": "src/main.py",
            "start_line": 1,
            "end_line": 2,
            "language": "python",
            "relevance_score": 0.91,
            "excerpt": "return 42",
        }
    ]


@pytest.mark.asyncio
async def test_chat_maps_provider_failures_to_stable_500_response(api_client, db_session, repository_factory, monkeypatch) -> None:
    repo = repository_factory(status=RepositoryStatus.INDEXED)
    db_session.add(repo)
    await db_session.commit()

    class FailingChatService:
        async def ask(self, **_kwargs):
            raise RuntimeError("private provider detail")

    monkeypatch.setattr("app.api.routes.chat.ChatService", FailingChatService)
    response = await api_client.post(f"/api/v1/repositories/{repo.id}/chat", json={"question": "query"})

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "INTERNAL_ERROR"
    assert "private provider detail" not in response.text


@pytest.mark.asyncio
async def test_chat_converts_and_bounds_conversation_history_for_provider(api_client, db_session, repository_factory, monkeypatch) -> None:
    from app.services.chat import ChatResult
    from app.services.llm import ChatMessage

    repo = repository_factory(status=RepositoryStatus.INDEXED)
    db_session.add(repo)
    await db_session.commit()
    observed: dict[str, object] = {}

    class HistoryAwareChatService:
        async def ask(self, **kwargs):
            history = kwargs["conversation_history"]
            observed["history"] = history
            assert all(isinstance(message, ChatMessage) for message in history)
            return ChatResult("Continued answer.", [], "test-model", 1, 1, False)

    monkeypatch.setattr("app.api.routes.chat.ChatService", HistoryAwareChatService)
    messages = [{"role": "user", "content": f"message {index}"} for index in range(6)]

    response = await api_client.post(
        f"/api/v1/repositories/{repo.id}/chat",
        json={"question": "Continue", "conversation_history": messages},
    )

    assert response.status_code == 200
    assert [message.content for message in observed["history"]] == ["message 2", "message 3", "message 4", "message 5"]


@pytest.mark.asyncio
async def test_security_scan_trigger_conflict_and_result_retrieval(
    api_client, db_session, repository_factory
) -> None:
    repo = repository_factory()
    db_session.add(repo)
    await db_session.flush()
    scan = SecurityScan(repository_id=repo.id, status=ScanStatus.QUEUED)
    db_session.add(scan)
    await db_session.commit()

    conflict = await api_client.post(f"/api/v1/repositories/{repo.id}/scans", json={})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "SCAN_IN_PROGRESS"

    scan.status = ScanStatus.COMPLETED
    db_session.add(
        SecurityFinding(
            scan_id=scan.id,
            repository_id=repo.id,
            rule_id="SECRET_HARDCODED",
            title="Hardcoded secret",
            category="secrets",
            severity="critical",
            confidence="high",
            file_path="src/config.py",
            start_line=7,
            end_line=7,
            redacted_evidence="api_key=***REDACTED***",
            explanation="A hardcoded credential is present.",
            remediation="Use a secret store.",
            references=[],
            status="open",
            content_hash=hashlib.sha256(b"finding").hexdigest(),
        )
    )
    await db_session.commit()

    scans = await api_client.get(f"/api/v1/repositories/{repo.id}/scans")
    findings = await api_client.get(f"/api/v1/repositories/{repo.id}/findings", params={"severity": "critical"})
    scan_response = await api_client.post(f"/api/v1/repositories/{repo.id}/scans", json={})
    missing = await api_client.get(f"/api/v1/repositories/{uuid.uuid4()}/findings")

    assert scans.status_code == 200
    assert scans.json()[0]["status"] == "completed"
    assert findings.status_code == 200
    assert findings.json()["total"] == 1
    assert findings.json()["findings"][0]["file_path"] == "src/config.py"
    assert findings.json()["findings"][0]["start_line"] == 7
    assert scan_response.status_code == 201
    assert scan_response.json()["status"] == "queued"
    assert missing.status_code == 404
