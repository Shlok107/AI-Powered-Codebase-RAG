"""Shared fixtures with a fail-closed database configuration for tests."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings

# Prevent test processes from loading credentials or configuration from a developer's .env.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["APP_ENV"] = "test"
os.environ["LLM_PROVIDER"] = "none"
os.environ["EMBEDDING_PROVIDER"] = "none"

# Pydantic Settings reads its configured env_file directly; PYTHON_DOTENV_DISABLED
# alone does not disable that source. Do not load credentials from the developer's .env.
Settings.model_config["env_file"] = None

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    _test_db_url = make_url(TEST_DATABASE_URL)
    if _test_db_url.get_backend_name() != "postgresql":
        raise pytest.UsageError("TEST_DATABASE_URL must point to PostgreSQL with pgvector support")
    if "test" not in (_test_db_url.database or "").lower():
        raise pytest.UsageError("TEST_DATABASE_URL database name must contain 'test' for safety")
    if _test_db_url.drivername not in {"postgresql+psycopg", "postgresql+asyncpg"}:
        raise pytest.UsageError("TEST_DATABASE_URL must use the psycopg or asyncpg SQLAlchemy driver")
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
else:
    # Never let imports of app.db.session fall back to the development database.
    os.environ["DATABASE_URL"] = (
        "postgresql+asyncpg://test:test@127.0.0.1:1/codebase_rag_test"
    )


@pytest.fixture(autouse=True)
def external_services_are_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep provider selection deterministic and prevent accidental paid API calls."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "none")


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Create an isolated schema per test in an explicitly named PostgreSQL test DB."""
    if not TEST_DATABASE_URL:
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL database with pgvector")

    from app.db.base import Base
    from app.db import models  # noqa: F401 - registers all model metadata

    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    schema = f"test_{uuid.uuid4().hex}"
    try:
        async with engine.connect() as connection:
            outer_transaction = None
            try:
                await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.execute(text(f'SET search_path TO "{schema}", public'))
                await connection.commit()
                await connection.run_sync(Base.metadata.create_all)
                await connection.commit()

                outer_transaction = await connection.begin()
                session = AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    autoflush=False,
                    join_transaction_mode="create_savepoint",
                )
                try:
                    yield session
                finally:
                    await session.close()
                    if outer_transaction.is_active:
                        await outer_transaction.rollback()
            finally:
                if connection.in_transaction():
                    await connection.rollback()
                await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                await connection.commit()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    """Exercise real FastAPI routes against the isolated test schema."""
    from app.db.session import get_session
    from app.main import app

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    async def no_op_job(*_args: object, **_kwargs: object) -> None:
        return None

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr("app.workers.indexing_worker.run_indexing_job", no_op_job)
    monkeypatch.setattr("app.api.routes.security.run_security_scan_job", no_op_job)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.fixture
def repository_factory():
    """Build repository model instances without hiding the real SQLAlchemy model."""
    from app.db.models import Repository, RepositorySourceType, RepositoryStatus

    def create(**overrides: object) -> Repository:
        values: dict[str, object] = {
            "id": uuid.uuid4(),
            "display_name": "sample-repository",
            "source_type": RepositorySourceType.ZIP_UPLOAD,
            "source_metadata": {"original_filename": "sample.zip"},
            "status": RepositoryStatus.PENDING,
            "detected_languages": ["python"],
            "file_count": 0,
            "chunk_count": 0,
        }
        values.update(overrides)
        return Repository(**values)

    return create


@pytest.fixture
def zip_bytes():
    """Create in-memory ZIP archives for upload and extraction tests."""
    from io import BytesIO
    from zipfile import ZIP_DEFLATED, ZipFile

    def create(entries: list[tuple[str, str]]) -> bytes:
        buffer = BytesIO()
        with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
            for path, content in entries:
                archive.writestr(path, content)
        return buffer.getvalue()

    return create
