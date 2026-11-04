# Codebase RAG Backend

FastAPI service for repository ingestion, indexing, codebase Q&A, static security analysis, and dependency graph queries.

This package is part of the [Codebase RAG project](../README.md). The root README is the primary guide for running the complete application with Docker Compose.

## Responsibilities

- Accept and safely extract ZIP repository uploads.
- Inventory repository files and store extracted source in repository storage.
- Chunk source files and create embeddings for retrieval.
- Retrieve relevant code using vector and keyword search.
- Generate repository-grounded answers through an OpenAI-compatible chat endpoint.
- Run static security checks and OSV dependency advisory lookups.
- Compute bounded internal Python import graphs from indexed repository source.

## Runtime requirements

- Python 3.11 or newer.
- PostgreSQL 16 with the pgvector extension.
- Docker Compose is the recommended way to run the full application.
- An embedding provider for meaningful vector indexing and an optional LLM provider for generated answers.

## Local development

The commands below assume PostgreSQL with pgvector is available on `localhost:5433`. That is the host port published by the repository's Docker Compose configuration.

### 1. Create and activate a virtual environment

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev,local-embeddings]"
```

The `local-embeddings` extra installs Sentence Transformers and PyTorch. If you only need API development or tests that use the no-op providers, install `.[dev]` instead.

### 3. Configure the environment

While the current directory is `backend`, create `backend/.env` from the example:

**PowerShell:**

```powershell
Copy-Item ..\.env.example .env
```

**macOS / Linux:**

```bash
cp ../.env.example .env
```

For a backend process running directly on the host, set the database URL to the host-published database port:

```env
APP_ENV=development
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/codebase_rag
CORS_ORIGINS_STR=http://localhost:5173
```

The default provider values are `none`. Configure embedding and chat providers as described in the [root configuration guide](../README.md#configure-ai-providers) when you need those features.

### 4. Apply migrations and start the API

```bash
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at http://localhost:8000. Interactive API documentation is available at http://localhost:8000/docs in development mode.

When using the root Docker Compose stack, do not run this manual server command: Compose applies migrations and starts the backend container automatically.

## API areas

All application routes use the configured API prefix (default: `/api/v1`).

| Area | Route prefix | Purpose |
|---|---|---|
| Health | `/api/v1/health` | Service health |
| Repositories | `/api/v1/repositories` | Upload, list, inspect and delete repositories; list files; trigger indexing |
| Chat | `/api/v1/repositories/{repository_id}/chat` | Ask questions about an indexed repository |
| Security | `/api/v1/repositories/{repository_id}/scans`, `/findings` | Start scans, list findings, and update triage state |
| Dependency graph | `/api/v1/repositories/{repository_id}/graph` | Retrieve graph, node details and reverse impact data |

For exact request and response schemas, run the service and use its OpenAPI documentation at `/docs`.

## Tests

Run backend tests from the `backend` directory:

```bash
python -m pytest
```

The database-backed fixtures require `TEST_DATABASE_URL` to point to a dedicated PostgreSQL database with pgvector enabled. Its database name must contain the word `test`. The test configuration deliberately rejects non-test database names and does not fall back to the development database.

Example:

```env
TEST_DATABASE_URL=postgresql+psycopg://codebase_rag_test:codebase_rag_test@localhost:5433/codebase_rag_test
```

Use a separate test database and credentials in your local PostgreSQL setup. Never point `TEST_DATABASE_URL` at the database containing repositories you want to keep.

## Implementation boundaries

- Uploaded code is parsed and analyzed; the application does not execute or import repository code as part of ingestion or graph extraction.
- Indexing and security scan jobs are currently started as asynchronous tasks by the API process. A separate worker service and durable message queue are not part of the current local implementation.
- Dependency graph coverage is limited to resolvable Python imports. Graph results are computed on request and bounded by service limits.
- OSV-based dependency checks depend on an external service and report incomplete coverage when they cannot complete the configured work.
- The API does not currently provide authentication or per-user repository authorization. Keep it bound to localhost during development; do not expose it directly to an untrusted network.

See the [root README](../README.md) for full architecture, usage, configuration, security notes, and project limitations.
