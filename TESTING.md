# Automated testing

The backend suite uses pytest, HTTPX, SQLAlchemy and a real PostgreSQL/pgvector test database. Unit tests exercise parsing, chunking, provider boundaries, retrieval ranking, citation handling and each registered security rule. Integration tests run the existing FastAPI routes and indexing/security workers against real PostgreSQL models and full-text/vector queries. They do not use the development database.

The test fixture requires an explicit `TEST_DATABASE_URL`, accepts only PostgreSQL URLs using `psycopg` or `asyncpg`, and requires the database name to contain `test`. It never falls back to `DATABASE_URL`; without a test URL, database tests are skipped and application imports use a non-routable test-only URL. Each database test creates a uniquely named schema, installs/uses pgvector in the dedicated test database, and removes only that schema when the test finishes. Model loading, embedding and NVIDIA-compatible LLM calls are mocked at provider boundaries. The test configuration disables LLM and embedding providers and does not require paid credentials.

The frontend suite uses Vitest, React Testing Library, `user-event`, jsdom and the Vitest V8 coverage provider. HTTP calls are mocked in page tests. A separate API client test exercises the actual Axios upload method and verifies that it sends a `FormData` body containing the original `File` under `file` without forcing JSON or a multipart content type without its boundary.

## Run tests

Install backend test dependencies from `backend`:

```powershell
python -m pip install -e ".[dev]"
```

Install frontend dependencies from `frontend`:

```powershell
npm ci
```

For local PostgreSQL-backed tests, start the dedicated, disposable pgvector test service. It uses tmpfs storage and does not share configuration or volumes with the application services:

```powershell
docker compose -f docker-compose.test.yml up -d --wait
$env:TEST_DATABASE_URL = "postgresql+asyncpg://codebase_rag_test:codebase_rag_test@localhost:55432/codebase_rag_test"
$env:DATABASE_URL = $env:TEST_DATABASE_URL
$env:APP_ENV = "test"
$env:PYTHON_DOTENV_DISABLED = "1"
$env:LLM_PROVIDER = "none"
$env:EMBEDDING_PROVIDER = "none"
```

From the repository root, use these commands:

```powershell
.\scripts\test.ps1 -Scope all
.\scripts\test.ps1 -Scope backend
.\scripts\test.ps1 -Scope backend-unit
.\scripts\test.ps1 -Scope backend-integration
.\scripts\test.ps1 -Scope backend-coverage
.\scripts\test.ps1 -Scope frontend
.\scripts\test.ps1 -Scope frontend-coverage
```

`backend-unit` does not require PostgreSQL. The other backend scopes require `TEST_DATABASE_URL`. Run `docker compose -f docker-compose.test.yml stop postgres-test` when finished; the test service has no named or bind-mounted database volume.

Coverage reports are written to `backend/coverage.xml` and `frontend/coverage/` (HTML), with a text summary printed for both suites. Backend coverage omits the tests themselves and has a 65% general floor so the unit-only command remains useful; CI enforces 70% on the full PostgreSQL-backed suite. The full local suite measured 82.89%.

## CI

`.github/workflows/tests.yml` starts an ephemeral `pgvector/pgvector:pg16` service, installs both dependency sets, runs all backend tests, runs the frontend tests with coverage, and builds the frontend. CI uses only test credentials and disables the runtime LLM/embedding providers.

Alembic migrations are not invoked by the current automated suite. The integration fixture creates the ORM schema in a per-test schema; migration upgrade/downgrade coverage remains a known testing gap.
