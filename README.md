# Codebase RAG

**Codebase Intelligence and Security Analysis Platform**

A full-stack web application that ingests code repositories, indexes their contents, answers questions grounded in the codebase with file-and-line citations, and runs security/configuration checks with actionable findings.

## Features

- **Repository Upload**: Safe ZIP upload with ZIP slip protection and decompression limits
- **Code-Aware Indexing**: AST-based chunking for Python, Tree-sitter support, fallback for other languages
- **Semantic Search**: PostgreSQL/pgvector for embeddings with hybrid vector + keyword retrieval
- **Grounded Q&A**: Ask questions about the codebase with citations to exact file paths and line numbers
- **Security Scanning**: Detect secrets, dangerous code patterns, dependency risks, and infrastructure misconfigurations
- **Modern UI**: Dark-mode-first developer dashboard with responsive design

## Tech Stack

### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy 2.x + Alembic
- PostgreSQL + pgvector
- Pydantic v2
- sentence-transformers (local embeddings)

### Frontend
- React 18 + TypeScript
- Vite
- Tailwind CSS
- React Router

### Infrastructure
- Docker & Docker Compose
- AWS ECS/S3/RDS/SQS ready (configuration only)

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Git (optional)

### Using Docker Compose

```bash
# Clone the repository
git clone https://github.com/Shlok107/AI-Powered-Codebase-RAG.git
cd AI-Powered-Codebase-RAG

# Copy environment file
cp .env.example .env

# Start all services
docker compose up -d --build

# Wait for services to be healthy, then run migrations
docker-compose exec backend alembic upgrade head

# Access the application
# Frontend: http://localhost:5173
# Backend API: http://localhost:8001
# API Docs: http://localhost:8001/docs
```

### Manual Development Setup

#### Backend
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Set environment variables
cp ../.env.example .env
# Edit .env with your settings

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

## Configuration

See `.env.example` for all available options. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://postgres:postgres@db:5432/codebase_rag` |
| `LLM_PROVIDER` | LLM provider (`openai_compatible`, `none`) | `none` |
| `LLM_BASE_URL` | OpenAI-compatible API base URL | - |
| `LLM_API_KEY` | LLM API key | - |
| `LLM_MODEL` | Model name | - |
| `EMBEDDING_PROVIDER` | Embedding provider (`openai_compatible`, `sentence_transformers`, `none`) | `none` |
| `EMBEDDING_MODEL` | Embedding model name | `sentence-transformers/all-MiniLM-L6-v2` |
| `EMBEDDING_DIMENSIONS` | Vector dimensions | `384` |
| `MAX_UPLOAD_MB` | Max upload size in MB | `50` |

### Upload limits and deployment boundary

ZIP uploads are limited by `MAX_UPLOAD_MB` (50 MiB by default), `MAX_ARCHIVE_FILES` (10,000 entries), `MAX_UNCOMPRESSED_MB` (300 MiB of declared expansion), `MAX_SINGLE_FILE_MB` (5 MiB per indexed file), `MAX_ARCHIVE_PATH_LENGTH` (1,024 characters), and `MAX_ARCHIVE_COMPRESSION_RATIO` (1,000:1). The extractor also enforces per-file and aggregate limits while streaming actual decompressed bytes. Large supported source files are rejected rather than silently omitted. These settings can be set in the backend environment; `.env.example` lists the local defaults.

Dependency vulnerability checks query the OSV database for exact versions from supported manifests and lock files (requirements, `pyproject.toml`, npm lock files, Poetry/uv/Cargo lock files, and `go.mod`). `MAX_DEPENDENCY_QUERIES` and `MAX_DEPENDENCY_ADVISORIES` cap per-scan work. Advisory responses are cached in process for six hours. An unavailable service, malformed manifest, or reached cap is reported as incomplete coverage on the scan; it does not convert an unknown result into a clean result. Version ranges in unlocked manifests are not resolved, and the scanner does not claim to report general package freshness.

The Docker Compose stack binds its published ports to `127.0.0.1` and is for local development. The frontend is at `127.0.0.1:5173`, the backend API at `127.0.0.1:8001` (container port 8000), and PostgreSQL at `127.0.0.1:5433` (container port 5432). The alternate host ports avoid collisions with native services on the standard ports; containers use the internal `db:5432` address. The API currently has no authentication or per-user repository authorization; do not expose it directly to a network or public internet. A public deployment requires an identity provider, per-repository authorization, production database credentials managed by a secret store, TLS termination, and an edge/API gateway with request and operation rate limits. CORS restrictions do not replace authentication. The backend image defaults `APP_ENV` to `production`; Compose explicitly sets development mode for local use.

### LLM Provider Configuration

For AI-powered Q&A, configure an OpenAI-compatible endpoint:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=gpt-4
```

For local models (Ollama, vLLM, etc.):
```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=nemotron-3-ultra
```

### Embedding Provider Configuration

For local embeddings (no API key needed):
```env
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
```

For OpenAI-compatible embeddings:
```env
EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=your-api-key
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

## Usage

1. **Upload a Repository**: Go to Repositories page, click "Upload Repository", select a ZIP file
2. **Wait for Indexing**: The repository will be processed and indexed automatically
3. **Ask Questions**: Go to "Ask Codebase", select the repository, ask questions
4. **Run Security Scan**: Go to "Security", click "Run Security Scan"
5. **Review Findings**: Filter by severity, category, file, and status

## Project Structure

```
codebase-rag/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # API endpoints
│   │   ├── core/             # Config, logging, errors
│   │   ├── db/               # Database models, session
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   └── workers/          # Background jobs
│   ├── alembic/              # Database migrations
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/              # API client
│   │   ├── components/       # Reusable UI components
│   │   ├── features/         # Feature-specific components
│   │   ├── layouts/          # Page layouts
│   │   ├── pages/            # Page components
│   │   ├── hooks/            # Custom React hooks
│   │   ├── types/            # TypeScript types
│   │   └── utils/            # Utilities
│   └── Dockerfile
├── sample-repo/              # Sample repository for testing
├── docker-compose.yml
├── .env.example
└── README.md
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend   │────▶│   Backend   │────▶│  PostgreSQL │
│  (React)    │     │  (FastAPI)  │     │  + pgvector │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Workers    │
                    │ (Indexing,  │
                    │  Scanning)  │
                    └─────────────┘
```

### Data Flow

1. **Ingestion**: ZIP upload → Safe extraction → File inventory → Language detection
2. **Chunking**: Code-aware parsing (AST/Tree-sitter) → Line-range preserving chunks
3. **Embedding**: Batch embedding generation → pgvector storage
4. **Retrieval**: Vector similarity + keyword search → Hybrid ranking → Top-K
5. **Answer**: Context construction → LLM call → Citation validation → Response

## Security Considerations

- **Safe ZIP Extraction**: Path traversal protection, size limits, decompression bomb prevention
- **No Code Execution**: Uploaded code is never executed or imported
- **Secret Redaction**: Credentials are redacted in findings and logs
- **Input Validation**: All inputs validated at API boundary
- **SQL Safety**: Parameterized queries via SQLAlchemy
- **Prompt Injection Protection**: Repository content treated as untrusted
- **Local Exposure**: Compose ports bind to loopback; the API has no authentication or per-user authorization and is not suitable for direct public exposure
- **Dependency Advisories**: Exact lockfile versions are checked against OSV when available; unavailable or capped checks are surfaced as incomplete coverage

## Development documentation

- [Automated testing guide](docs/TESTING.md)
- [Engineering audit report](docs/AUDIT_REPORT.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Original project implementation plan](docs/codebase_plan.md)

Run the test harness from the repository root with `.\scripts\test.ps1 -Scope all` on Windows PowerShell. See the testing guide for database setup and individual test scopes.

## AWS Deployment (Configuration Only)

The application is designed for AWS deployment with:
- **ECS**: Containerized API and worker tasks
- **S3**: Repository archives and artifacts
- **RDS PostgreSQL**: Primary database with pgvector
- **SQS**: Asynchronous job queue
- **IAM**: Least-privilege roles
- **Secrets Manager**: Secure credential injection

Note: This configuration is provided but not deployed. AWS deployment is planned but has not been implemented yet.

## Limitations

- MVP implementation - not production-hardened
- Local embeddings require sentence-transformers dependencies
- No Git URL connector (ZIP upload only)
- No persistent chat history in MVP
- Dependency advisory lookup requires OSV availability for current vulnerability intelligence; offline scans report incomplete coverage
- Single embedding model per index (dimension validation enforced)

## License

A license file has not been added yet.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request
