# Codebase RAG — Full Implementation Plan for OpenCode

## How to use this file

Give this entire file to OpenCode as the implementation specification. Use **Nemotron 3 Ultra** as the coding model. Instruct the agent to work through the phases in order, make changes directly in the repository, run tests and checks after each phase, and continue until the project is usable end-to-end. The agent must not stop after generating a plan or scaffolding.

---

# MASTER PROMPT FOR OPENCODE

You are the lead software engineer responsible for implementing a complete, credible, portfolio-quality MVP called **Codebase RAG: Codebase Intelligence and Security Analysis Platform** from scratch. Build the actual application, not just a design, architecture document, or mock-up.

The result must be a working, maintainable full-stack web application that can ingest a code repository, index its contents, answer questions grounded in that repository with file-and-line citations, and run security/configuration checks that present actionable findings. The interface must look polished and intentional, with a coherent dashboard, loading/empty/error states, and real API integration.

## 1. Execution rules

1. **Inspect before changing anything.** Examine the existing repository, current branch, files, available runtimes, and installed tools. Preserve useful existing work. If the repository is empty, initialize it. Do not overwrite or delete unrelated files.
2. **Implement in phases in the order below.** At the beginning, write a concise checklist to `IMPLEMENTATION_STATUS.md`. Update it as phases are completed. Do not treat the checklist as the deliverable.
3. **Do the work, do not only describe it.** Create the source files, migrations, tests, Docker configuration, documentation, and UI. Do not leave core features as TODOs, fake buttons, hardcoded demo data, or unimplemented stubs.
4. **Keep the project achievable.** Prefer a reliable end-to-end MVP over speculative enterprise architecture. Do not add Kubernetes, microservices, a separate vector database, or unnecessary abstractions.
5. **Use real, testable behavior.** The UI must call the backend. API responses must be based on actual indexed repository data or actual scan results. Demo fixtures may be used only in automated tests or a clearly labelled optional demo mode.
6. **Validate continuously.** Run relevant tests, lint/type checks, builds, and Docker checks where available. Fix failures before moving on. Never claim a command passed if it was not run.
7. **Be transparent about environment limits.** If an external API key or AWS credentials are absent, make the application runnable in local mode and explain exactly which features need credentials. Do not invent keys, cloud resources, test results, or deployment success.
8. **Do not ask the user to make routine engineering decisions.** Choose sensible defaults consistent with this specification. Ask only if a genuinely blocking decision cannot be resolved safely.
9. **At completion**, provide a concise summary of what was implemented, the exact commands to run it, required environment variables, test results actually obtained, and any remaining limitations.

## 2. Product definition

### Problem

Developers need to understand unfamiliar codebases quickly and spot common security risks and unsafe configuration. General-purpose chat assistants can hallucinate code details, miss relevant files, and provide advice without showing where it came from. Static scanners, meanwhile, often produce findings without enough repository-specific explanation.

### Solution

Codebase RAG combines repository ingestion, code-aware chunking, embeddings, PostgreSQL vector search, hybrid retrieval, grounded LLM answers, and deterministic security checks in one web interface.

### Primary user workflows

1. **Add a repository:** upload a ZIP of source code. Architect ingestion so a Git URL connector can be added cleanly, but do not make GitHub OAuth or authenticated private-repository access a blocker for the MVP.
2. **Inspect indexing status:** see repository name, detected languages, file count, indexed chunk count, status, and errors.
3. **Ask questions:** ask questions such as “Where is authentication implemented?”, “What happens when a user uploads a file?”, or “How is the database connection configured?” Receive an answer grounded in retrieved source with citations to exact paths and line ranges.
4. **Inspect a citation:** click a citation and see the relevant file excerpt, path, line numbers, and a confidence/relevance indicator where available.
5. **Run a security scan:** scan the uploaded repository for common secrets, dangerous code patterns, insecure configuration, dependency risks, and infrastructure misconfiguration.
6. **Review findings:** filter by severity, category, file, and status; inspect evidence, line numbers, explanation, confidence, and remediation advice.
7. **Re-run work:** re-index a repository or re-run its scan without creating duplicate or inconsistent records.
8. **Understand system status:** view health and indexing/scanning status; errors must be visible and actionable.

### Explicit scope boundaries

- This is a **repository analysis and Q&A tool**, not an autonomous coding agent. Do not implement automatic code rewriting, pull-request creation, or arbitrary shell execution on uploaded code.
- Do not execute, import, build, or run untrusted repository code.
- Do not promise complete vulnerability detection. Explain that findings are advisory and can include false positives or missed issues.
- The MVP must work locally using Docker Compose. AWS deployment should be supported by configuration and documentation, but must not be required for local development.
- Do not require a paid LLM API for the application to boot. Provide a clear provider interface and a deterministic fallback mode for basic local development and tests. The fallback must not pretend to be an intelligent LLM.

## 3. Required resume-aligned technology stack

Keep the implementation consistent with the project stack represented on the resume:

### Backend and APIs
- Python 3.11 or newer compatible Python 3.x.
- FastAPI for the REST API.
- Pydantic v2 for request/response validation and settings.
- SQLAlchemy 2.x for persistence.
- Alembic for database migrations.
- PostgreSQL as the primary database.
- `pgvector` extension for embedding storage and similarity search.
- PyYAML for safe YAML parsing where required.
- NetworkX for a lightweight dependency/reference graph if it can be implemented without destabilizing the MVP.
- `pytest` and `httpx` for backend tests.

### Frontend
- React with TypeScript.
- Vite.
- Tailwind CSS.
- React Router for navigation if multiple routes are used.
- A small, consistent component system. Use accessible semantic HTML and reusable components; do not build every screen as one giant component.
- Use a charting library only if it provides real value for real data. Never fill charts with invented metrics.

### Retrieval and analysis
- Embedding provider interface. Default configurable implementation should support an OpenAI-compatible embeddings API. The provider base URL, model name, key, and dimensions must be configuration-driven.
- Support a local sentence-transformer embedding backend using `sentence-transformers` and `all-MiniLM-L6-v2` when dependencies and model download are available. Its vector dimension is 384. Do not mix vectors of different dimensions in one index.
- PostgreSQL/pgvector for persistent vector search. Do not silently replace PostgreSQL with SQLite or FAISS as the main production storage path.
- Hybrid retrieval: combine vector similarity with PostgreSQL full-text/keyword matching where feasible. If ranking is combined, document the ranking strategy and test it.
- Tree-sitter parsers where practical for code-aware chunking; at minimum implement reliable Python parsing with Python's built-in `ast`, and robust line-based fallback chunking for unsupported or invalid syntax.
- A provider abstraction for chat completion. Configure an OpenAI-compatible chat endpoint so a Nemotron 3 Ultra endpoint can be used if it exposes a compatible API. Do not hardcode a vendor-specific endpoint, model ID, API key, or assume that Nemotron is automatically accessible. Document that endpoint compatibility and model context limits depend on the user's serving provider.
- Do not require LangChain. Prefer explicit, small modules and direct API calls so the pipeline remains debuggable and model/provider independent.

### Packaging and cloud alignment
- Docker and Docker Compose for reproducible local setup.
- AWS deployment documentation/configuration aligned with **ECS, S3, RDS for PostgreSQL, and SQS**.
- Keep cloud integration modular. Local mode must not require AWS credentials.
- Use S3 for repository archives/artifacts in the cloud configuration, RDS PostgreSQL with pgvector for persistence/vector search, ECS for API/worker containers, and SQS for asynchronous jobs. Do not claim these services are deployed unless actually configured and deployed.
- Use environment variables and `.env.example`; never commit secrets.

**Important:** Avoid tech-stack drift. Do not add MongoDB, Redis, SQLite as the main database, a separate vector database, or a frontend framework other than React unless there is a concrete, documented reason and user approval.

## 4. Proposed repository structure

Adapt if the existing repo has a better equivalent structure, but maintain clear separation of concerns. A reasonable target is:

```text
codebase-rag/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   └── routes/
│   │   │       ├── health.py
│   │   │       ├── repositories.py
│   │   │       ├── indexing.py
│   │   │       ├── chat.py
│   │   │       └── security.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── errors.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   ├── base.py
│   │   │   └── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── repository_ingestion.py
│   │   │   ├── safe_archive.py
│   │   │   ├── file_filter.py
│   │   │   ├── parsers.py
│   │   │   ├── chunking.py
│   │   │   ├── embeddings.py
│   │   │   ├── retrieval.py
│   │   │   ├── llm.py
│   │   │   ├── dependency_graph.py
│   │   │   ├── security_scanner.py
│   │   │   └── findings_rules/
│   │   ├── workers/
│   │   └── tests/
│   ├── alembic/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── types/
│   │   ├── utils/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── sample-repo/                 # tiny harmless fixture for manual testing, not a real app dependency
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── IMPLEMENTATION_STATUS.md
└── codebase_plan.md
```

Do not create empty files just to match this tree. Every created module should have a real purpose.

## 5. Core functional requirements

### 5.1 Repository upload and safe ingestion

- Accept ZIP uploads through the API and UI.
- Validate file type, configured maximum upload size, and archive entry count.
- Protect against ZIP Slip/path traversal: normalize and verify every resolved output path stays within the designated extraction directory.
- Protect against decompression bombs with limits for total uncompressed size, individual file size, number of files, and compression ratio where practical.
- Reject symlinks and unsafe archive entries; never follow archive paths outside the extraction root.
- Use a unique temporary directory per upload. Clean up temporary files on success and failure.
- Never execute repository files or package lifecycle scripts.
- Ignore `.git`, `node_modules`, virtual environments, caches, build outputs, binary/media files, generated bundles, and other irrelevant or potentially huge directories.
- Support sensible text/source/config formats, including Python, JavaScript, TypeScript, Java, C/C++, Go, HTML, CSS, JSON, YAML, TOML, Markdown, Dockerfile, and common infrastructure/config files.
- Detect likely secrets carefully. Do not echo full secret values into logs, API responses, or the UI. Redact evidence where appropriate.
- Store repository metadata and relative file paths. Avoid storing absolute server filesystem paths in API responses.
- Return upload and ingestion status with useful errors.
- Make processing idempotent or safely replace prior indexing for the same repository version. Avoid duplicate chunks on retries.

### 5.2 Parsing and chunking

- Build code-aware chunks rather than blindly splitting every file into equal-sized character blocks.
- For Python, use `ast` to identify functions, classes, and top-level definitions; preserve source line ranges.
- For supported Tree-sitter languages, identify reasonable syntax units such as functions, classes, methods, and top-level declarations.
- For unsupported languages, malformed files, or parser failures, fall back to bounded line-based chunks with overlap.
- Every chunk must preserve: repository ID, relative file path, start line, end line, language, chunk type, stable chunk identifier/content hash, and source text.
- Use configurable chunk size and overlap, with safe defaults.
- Avoid zero-length chunks, repeated overlapping duplicates, and chunks that exceed provider limits.
- Extract basic import/reference metadata when practical. Build a lightweight dependency/reference graph only from statically extracted metadata; do not claim it represents every runtime dependency.
- Keep a record of skipped files and reasons so indexing totals are explainable.

### 5.3 Embeddings and PostgreSQL/pgvector

- Use a provider abstraction with explicit configuration and error handling.
- Select one embedding model/dimension per index. Validate dimensions before writing to the vector column.
- Store embeddings in PostgreSQL via pgvector. Include a migration that enables the extension and creates the necessary tables/indexes.
- Create an index strategy appropriate to the chosen pgvector version and data size. If approximate indexes are used, document the minimum data/extension assumptions; exact search is acceptable for a small MVP.
- Batch embedding requests and handle provider rate limits, timeouts, and transient errors with bounded retries.
- Do not generate fake embeddings in normal operation. For tests, inject deterministic stub providers.
- If embeddings are not configured, allow the app to start and clearly mark semantic indexing as unavailable. Do not label a repository “fully indexed” if the required indexing steps failed.

### 5.4 Retrieval and grounded RAG answers

- Retrieve relevant chunks with vector similarity and keyword/full-text search.
- Merge and rank candidates using a simple documented strategy, such as normalized weighted scores or reciprocal rank fusion. Keep the implementation testable.
- Return a configurable top-k, default around 5–8 chunks, while respecting token/context budgets.
- Optionally rerank with a configurable cross-encoder only if it is practical and does not make local setup brittle. It must be optional.
- Construct prompts that tell the LLM to answer only from supplied repository evidence, distinguish evidence from inference, and say when the retrieved context is insufficient.
- Require source citations for code-specific claims. Citations must include repository-relative file path and exact start/end line range, and must map back to chunks actually retrieved.
- Do not allow the model to invent paths, line numbers, symbols, tests, or security findings. Validate cited sources against retrieval results. Remove or flag invalid citations.
- Include a confidence/relevance indication only if based on a real, documented heuristic. Do not present an uncalibrated LLM self-rating as a probability.
- Preserve chat history per conversation if implemented, but bound history and never send an unlimited transcript.
- Treat repository contents as untrusted data. A file can contain prompt injection such as “ignore previous instructions”; repository text must never override system instructions or trigger tools.
- The LLM must not have access to shell execution, arbitrary network requests, file writes, or secrets.
- If the LLM provider is unavailable, return a clear provider error or use an explicitly labelled extractive fallback that returns relevant source snippets. Never fabricate a natural-language answer and present it as an LLM response.

### 5.5 Security analysis

Implement a modular, explainable scanner. Use deterministic rules first; an LLM may explain or prioritize results but must not be the sole detector for high-confidence pattern findings.

At minimum, support checks for:

**Secrets and sensitive data**
- Common API-token/private-key patterns and cloud credential formats.
- Hardcoded passwords and tokens in source/config files, with contextual false-positive filters.
- Secrets accidentally exposed in frontend/public configuration.
- Never return a complete discovered credential; redact it in all findings and logs.

**Dangerous code patterns**
- Python uses of `eval`/unsafe `exec`, unsafe deserialization patterns, risky subprocess invocation, and SQL assembled with string concatenation where detectable.
- Injection indicators in common contexts, including SQL and shell command construction.
- Path traversal and unsafe file handling patterns where statically detectable.
- SSRF indicators where user-controlled URLs flow into server-side requests, with conservative claims.
- Unsafe upload/archive extraction patterns.
- Weak cryptographic algorithms and insecure random number use in security-sensitive contexts where detectable.
- Debug mode, permissive CORS, insecure cookie/session flags, and unsafe authentication/authorization defaults in common configurations.
- Avoid reporting every occurrence of a dangerous function as exploitable without context. State the evidence and limitations.

**Dependencies**
- Parse `requirements.txt`, `pyproject.toml`, `package.json`/lockfiles, common Java dependency manifests, and other practical manifest formats.
- Detect known vulnerabilities only through a clearly documented, configurable advisory source or a local advisory dataset. If no advisory source is configured or reachable, report dependency inventory and mark vulnerability intelligence as unavailable; do not invent CVEs or imply complete coverage.
- If using a public advisory API, set timeouts, handle network failure, cache results when appropriate, and never send repository source code or secrets to the service.

**Infrastructure/configuration**
- Dockerfile risks such as running as root when avoidable, overly broad permissions, floating base-image tags, and secret-bearing build arguments/environment declarations.
- Kubernetes YAML risks if present, such as privileged containers, host namespaces, missing resource limits, and overly permissive security contexts.
- Cloud/IaC configuration issues only for formats that are actually parsed. Do not claim broad IaC support if only a few rules exist.

**Finding schema**
Each finding should include:
- Stable ID and rule ID.
- Title and category.
- Severity (`critical`, `high`, `medium`, `low`, `info`) and confidence (`high`, `medium`, `low`) as separate fields.
- Relative file path and line range where available.
- Redacted evidence/snippet.
- Explanation of why the pattern matters.
- Practical remediation guidance.
- Optional CWE/reference URL only when known and valid.
- Status (`open`, `dismissed`, `resolved`) if persisted triage is implemented.
- Timestamp and scan ID.

Severity must be determined by explicit rule logic or documented mapping, not arbitrary model judgment. De-duplicate findings from repeated scans and use stable rule/path/line/content identifiers where possible. Include rule IDs and rule descriptions in the UI. Add tests for true positives, false positives, redaction, and duplicate handling.

### 5.6 API design

Use versioned, typed REST endpoints. Keep route handlers thin and place business logic in services. Exact endpoint names can be adjusted, but equivalent functionality must exist:

- `GET /api/v1/health` — application and dependency status without exposing credentials.
- `GET /api/v1/repositories` — list repositories and status.
- `POST /api/v1/repositories/upload` — multipart ZIP upload.
- `GET /api/v1/repositories/{repository_id}` — repository details and summary.
- `DELETE /api/v1/repositories/{repository_id}` — delete metadata, chunks, embeddings, files/artifacts owned by the repository, and related records safely.
- `POST /api/v1/repositories/{repository_id}/index` — trigger or retry indexing.
- `GET /api/v1/repositories/{repository_id}/files` — list indexed files.
- `GET /api/v1/repositories/{repository_id}/files/content?path=...` — return a bounded, sanitized file excerpt with line metadata; validate path against repository contents.
- `POST /api/v1/repositories/{repository_id}/chat` — ask a repository question; return answer, citations, and relevant sources.
- `GET /api/v1/repositories/{repository_id}/scans` — list scans.
- `POST /api/v1/repositories/{repository_id}/scans` — run a security scan.
- `GET /api/v1/repositories/{repository_id}/findings` — list/filter findings.
- `PATCH /api/v1/findings/{finding_id}` — update triage status if triage is supported.
- `GET /api/v1/repositories/{repository_id}/graph` — return dependency graph data if graph extraction is implemented.

Use consistent response schemas, pagination where lists can grow, clear HTTP status codes, request validation, and structured error responses. Configure CORS from an explicit environment allowlist. Do not enable unrestricted CORS in production. Add API docs through FastAPI's OpenAPI support.

### 5.7 Async jobs and scalability

- Repository parsing, embedding, and scans may be slow. Implement a clean job abstraction and visible status states (`queued`, `processing`, `completed`, `failed`).
- For local development, a simple background worker/process is acceptable if reliable and documented.
- Provide an adapter boundary for AWS SQS and an ECS worker deployment. The local setup must work without AWS.
- Do not run long jobs inside a request without a timeout or status mechanism. Do not introduce Celery/Redis unless necessary and justified.
- Make retry behavior bounded and safe; record failure reasons without leaking secrets.
- Keep jobs idempotent and ensure the UI can poll for status.

### 5.8 Data model

Use SQLAlchemy models and Alembic migrations for at least:
- `Repository`: id, display name, source type, source metadata safe for display, status, detected languages, file/chunk counts, timestamps, error summary.
- `RepositoryFile`: repository ID, relative path, language, size, content hash, line count, indexing/skipped status, skip reason.
- `CodeChunk`: repository ID, file ID/path, start/end lines, language, chunk type, content hash, text, embedding vector, metadata.
- `Conversation` and `ChatMessage` if persistent chat history is implemented.
- `SecurityScan`: repository ID, status, timestamps, counts by severity, error summary.
- `SecurityFinding`: scan/repository IDs, stable rule ID, title, category, severity, confidence, path/line range, redacted evidence, explanation, remediation, references, triage status.
- `BackgroundJob` if jobs are persisted.

Add appropriate foreign keys, indexes, cascading deletion behavior, uniqueness constraints, and timestamps. Avoid storing redundant fields unless they improve query performance or preserve useful scan history.

### 5.9 UI/UX requirements

Build a real, polished dark-mode-first developer dashboard. The design should feel like a modern code intelligence/security product, not a generic admin template. Use a restrained palette (near-black/slate surfaces, subtle borders, readable neutral text, one restrained accent color), consistent spacing, clear typography, and a responsive layout. Do not use excessive gradients, glowing effects, emoji, fake terminal animations, or gratuitous charts.

Required screens/components:

1. **App shell**
   - Persistent sidebar with product mark/name and navigation.
   - Main content area with page title, contextual description, and repository selector where appropriate.
   - Responsive behavior for laptop and smaller screens.
   - Clear active navigation and keyboard-accessible controls.

2. **Overview/dashboard**
   - Repository count, indexed file/chunk totals, latest scan status, and findings counts computed from the backend.
   - Recent repositories and recent scan activity.
   - First-run empty state that explains how to upload a repository.
   - Never show invented KPI values.

3. **Repositories**
   - Upload ZIP by drag-and-drop and file picker.
   - Upload progress, validation errors, and indexing status.
   - Repository list with status, language badges, file/chunk counts, and last updated time.
   - Repository detail page with overview, indexed files, indexing status, and actions to re-index, scan, or delete (confirm destructive actions).

4. **Ask Codebase**
   - Select repository and enter a question.
   - Conversation layout with readable answers, loading state, error state, and retry.
   - Citations displayed as clickable source chips/cards with path and line range.
   - Clicking a citation opens a source viewer or file drawer at the cited lines.
   - Display retrieved sources separately from the generated answer when useful.
   - Empty state with example questions, clearly labelled as examples rather than actual results.

5. **Security findings**
   - Summary of findings by severity using actual API data.
   - Search and filters for severity, category, file, and status.
   - Findings table/list with clear severity, rule ID, file and line, confidence, and triage state.
   - Finding detail drawer/page with redacted evidence, explanation, remediation, and valid references.
   - Scan button with progress/status and an explicit “no findings” state distinct from scan failure.
   - Explain that the scanner is advisory and not a substitute for a comprehensive security review.

6. **Dependency graph** (only if the backend provides real extracted graph data)
   - Show a simple graph/list of actual detected relationships.
   - Provide a helpful empty state if no relationships were extracted.
   - Do not generate a decorative fake graph.

7. **Settings / system status**
   - Show safe configuration status, such as “LLM provider configured/unconfigured”, “embedding provider configured/unconfigured”, and database health.
   - Never expose API keys, secret values, raw environment dumps, or full connection strings.

### UI implementation quality

- Use TypeScript types for API responses.
- Centralize API requests and error handling.
- Use environment-configured API base URL.
- Include skeleton/loading states, useful empty states, errors, success feedback, and destructive-action confirmation.
- Make forms keyboard-accessible; label inputs and provide visible focus states.
- Ensure color contrast and accessible names.
- Prevent duplicate submissions and show job status polling while indexing/scanning.
- Do not use fake buttons, placeholder links, hardcoded production data, or `alert()` as the main UX.
- Keep components small and reusable; handle long file paths and code excerpts gracefully.
- Include responsive layouts and ensure no horizontal overflow at common laptop widths.

## 6. Security, privacy, and reliability requirements

- Validate every input at the API boundary.
- Use safe ZIP extraction and path normalization.
- Never execute uploaded code.
- Never interpolate user input into SQL; use SQLAlchemy parameterization.
- Treat all repository contents as untrusted data and potential prompt injection.
- Redact credentials in findings, logs, errors, and UI.
- Avoid logging source files, complete prompts containing secrets, authorization headers, or provider keys.
- Add upload limits and timeouts. Bound text size, number of files, chunk count, embedding batch size, and model context.
- Add rate limits or at least configurable per-request limits for expensive endpoints where practical.
- Avoid SSRF: do not implement arbitrary URL fetching as part of ZIP upload. If a Git URL connector is added, restrict schemes to HTTPS/SSH as deliberately supported, block loopback/private/link-local/metadata addresses, revalidate redirects and resolved addresses, and never accept file:// URLs. This connector is optional; ZIP upload is the MVP.
- Return generic client-facing errors and detailed but sanitized server logs.
- Do not store or display full secrets found in the repository.
- Use dependency versions compatible with one another and pin or constrain them responsibly.
- Add health checks and graceful startup/shutdown.
- Use non-root container users where practical and avoid copying `.env` or local secrets into Docker images.
- Include a disclaimer that security findings are advisory and the tool does not guarantee absence of vulnerabilities.

## 7. Configuration

Create `.env.example` with documented, non-secret placeholders. At minimum include equivalent settings for:

```dotenv
APP_ENV=development
APP_NAME=Codebase RAG
API_PREFIX=/api/v1
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
FRONTEND_PORT=5173
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/codebase_rag
CORS_ORIGINS=http://localhost:5173
MAX_UPLOAD_MB=50
MAX_ARCHIVE_FILES=10000
MAX_UNCOMPRESSED_MB=300
MAX_SINGLE_FILE_MB=5
CHUNK_SIZE=1200
CHUNK_OVERLAP=150
RETRIEVAL_TOP_K=6
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
LLM_TIMEOUT_SECONDS=60
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_BASE_URL=
EMBEDDING_API_KEY=
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
AWS_REGION=
S3_BUCKET=
SQS_QUEUE_URL=
```

Adapt names as needed, but settings must be typed, validated, and documented. Never put real credentials in the file. Do not assume every OpenAI-compatible provider uses identical request payloads or supports embeddings; test the configured provider and provide actionable errors. If an endpoint supports chat but not embeddings, allow chat and embeddings to be configured independently.

For Docker Compose, ensure the database image has the `pgvector` extension available. Add a health check and ensure the backend waits for database readiness. The migration/startup strategy must be explicit and reproducible.

## 8. Testing requirements

Tests are a core deliverable, not an optional finishing task.

### Backend unit tests
- ZIP traversal rejection and decompression limits.
- File filtering and language detection.
- Python AST chunking and fallback chunking.
- Stable chunk IDs and idempotent re-index behavior.
- Embedding provider configuration, dimension validation, and provider failure.
- Retrieval ranking and citation validation.
- Prompt injection text in repository files remains untrusted evidence.
- Secret redaction.
- Security rules for representative true-positive and false-positive fixtures.
- Severity/confidence mapping and finding deduplication.
- API validation, status transitions, and deletion/cascade behavior.

### Backend integration tests
- Health endpoint.
- Upload and ingestion lifecycle.
- Repository listing/details/files.
- Chat endpoint using injected fake LLM/embedding providers.
- Security scan and findings endpoint.
- Correct behavior when providers are not configured.
- PostgreSQL/pgvector integration tests when Docker/database is available. Clearly mark tests that require services; do not pretend they ran if they did not.

### Frontend validation
- TypeScript check.
- Production build.
- Tests for key components/API state where practical.
- Manually verify that empty, loading, failure, and successful states render without crashes.

### End-to-end smoke test
Provide a repeatable manual or automated path:
1. Start services.
2. Upload a small harmless sample repository.
3. Wait for indexing to finish.
4. Ask a question about a known function and verify path/line citations.
5. Run a scan against intentional safe test patterns.
6. Open a finding and verify redaction/remediation.
7. Delete the repository and verify associated data is removed.

Never include a real secret in a test fixture. Use clearly fake placeholder strings.

## 9. Docker and local developer experience

- Provide `docker-compose.yml` for PostgreSQL/pgvector, backend, and frontend.
- Include database health checks and persistent volume for PostgreSQL.
- Document migrations and startup order.
- Include a backend Dockerfile and frontend Dockerfile suitable for local development or production builds.
- Ensure frontend API requests reach the backend from the browser; avoid accidentally using an internal Docker hostname in browser-side requests.
- Add `.gitignore` for `.env`, Python caches/virtual environments, Node dependencies/build output, uploaded repositories, logs, and local databases.
- Add a small sample repository with harmless code and configuration examples to make the workflow demonstrable. Any intentionally insecure sample must use fake credentials, be clearly marked as a test fixture, and never be executed.
- Provide commands for both Docker-based setup and manual local development where practical.

## 10. AWS deployment alignment

Prepare a practical, honest deployment path aligned with the resume's AWS claims:

- **ECS:** containerized API and worker tasks.
- **S3:** uploaded ZIP archives and optional repository artifacts.
- **RDS PostgreSQL:** primary database, configured with a compatible pgvector extension where supported by the selected RDS engine/version.
- **SQS:** queue for asynchronous indexing and scanning jobs.
- **IAM:** least-privilege roles for S3/SQS access; no long-lived credentials baked into images.
- **CloudWatch:** logs/metrics and health visibility where practical.
- **Secrets Manager or task secrets:** document secure runtime secret injection rather than committing secrets.
- Provide deployment notes or infrastructure templates only if they are accurate and usable. Do not create a sprawling infrastructure stack before the local MVP works.
- Document the differences between local and AWS modes, the required IAM permissions, migration execution, and how to verify deployment.
- Clearly distinguish “configuration/documentation provided” from “deployed and tested.”

## 11. Observability and maintainability

- Use Python type hints and clear module boundaries.
- Add structured logs with request/job identifiers where practical.
- Add useful error categories for upload, parsing, embedding, LLM, database, and scan failures.
- Track job start/end times and basic counts. Do not collect source content or secrets in telemetry.
- Use stable error response formats.
- Add a short architecture section in the README and document the ingestion → parsing/chunking → embedding/indexing → retrieval → answer flow.
- Document the scan pipeline and current limitations.
- Add a `Makefile` or equivalent scripts for common commands if helpful.

## 12. Implementation phases

Complete each phase in sequence. After each phase, run the relevant checks, fix failures, and update `IMPLEMENTATION_STATUS.md` with completed work and test outcomes.

### Phase 0 — Repository reconnaissance and implementation checklist
- Inspect the current workspace and available toolchain.
- Identify existing files and preserve useful code.
- Create/update `IMPLEMENTATION_STATUS.md` with phases, assumptions, commands, and known environment constraints.
- Establish a minimal architecture decision record in the README or `docs/architecture.md`.
- Do not spend excessive time writing plans; proceed to implementation.

**Exit criteria:** a clear checklist and a chosen structure that matches the actual workspace.

### Phase 1 — Project foundation and runnable services
- Set up backend and frontend project configurations.
- Add typed settings, logging, error handling, health endpoint, and API version prefix.
- Add PostgreSQL/pgvector Docker Compose service and health checks.
- Add initial SQLAlchemy configuration, Alembic, and the first migration.
- Add React/Vite/TypeScript/Tailwind application shell and API client.
- Add `.env.example`, `.gitignore`, and baseline README instructions.

**Exit criteria:** local services can start, health endpoint works, frontend renders, database connection is verifiable, and frontend production build succeeds.

### Phase 2 — Data model and repository upload
- Implement repository/file/chunk/job/scan/finding models as needed and migrations.
- Implement safe ZIP validation/extraction, filtering, file inventory, hashing, and upload endpoint.
- Implement repository list/detail/delete endpoints.
- Build upload UI, repository list, repository detail shell, and upload/indexing statuses.
- Add traversal, size-limit, filtering, and API tests.

**Exit criteria:** user can upload a ZIP, see repository metadata and files, and safely delete the repository.

### Phase 3 — Parsing, chunking, and indexing
- Implement language detection and code-aware chunking, beginning with Python AST.
- Add Tree-sitter support where feasible and a robust fallback for all other text files.
- Store chunks with line ranges, metadata, and content hashes.
- Implement embedding providers, dimension validation, batching, and pgvector writes.
- Add indexing job lifecycle and idempotent retries.
- Show indexing progress/status in the UI.

**Exit criteria:** a sample repository can be indexed reproducibly; chunk records include accurate file paths and line ranges; failures are visible and do not falsely mark the repository as indexed.

### Phase 4 — Retrieval and grounded code Q&A
- Implement vector and keyword retrieval, candidate merging/ranking, context budgeting, and source validation.
- Implement configurable chat provider, including an OpenAI-compatible endpoint configuration suitable for a compatible Nemotron 3 Ultra serving endpoint.
- Add grounded answer prompts and citations validated against retrieved chunks.
- Add a clearly labelled extractive fallback when the LLM is unavailable.
- Build the Ask Codebase UI, conversation state, citations, and source viewer.
- Add tests for ranking, citations, missing providers, and prompt injection.

**Exit criteria:** a user can ask about a real indexed repository and receive a grounded answer with valid file/line citations, or a clear fallback/error without fabricated claims.

### Phase 5 — Security scanning
- Implement modular deterministic rules and a documented rule registry.
- Add secret detection/redaction, dangerous-code/config checks, dependency manifest inventory, and Docker/Kubernetes checks for supported formats.
- Add optional advisory lookup only with explicit configuration and transparent failure behavior.
- Persist scan results and findings; implement filters and triage status if supported.
- Build the findings dashboard, detail drawer, severity/category filters, scan progress, and empty/error states.
- Add representative rule tests and redaction/deduplication tests.

**Exit criteria:** a scan completes on the sample repository, findings have real evidence and remediation, secrets are redacted, and no-findings is distinct from scan failure.

### Phase 6 — Dependency/reference graph and dashboard polish
- Implement lightweight import/reference extraction and graph endpoint if it can be made reliable.
- Populate overview metrics exclusively from backend data.
- Finish responsive styling, navigation, repository selector, loading/empty/error states, confirmations, and accessibility.
- Add system-status view for database/provider configuration without exposing secrets.
- Remove fake controls and dead navigation.

**Exit criteria:** all visible controls work, overview values are real, core screens are usable at laptop and smaller widths, and no obvious UI crashes remain.

### Phase 7 — Reliability, tests, and security hardening
- Run unit and integration tests, lint/type checks, and frontend production build.
- Run end-to-end smoke test.
- Review archive safety, path handling, prompt injection, secret redaction, CORS, timeouts, error leakage, SQL safety, and deletion behavior.
- Fix bugs and add regression tests.
- Verify idempotency and job status transitions.
- Check dependency compatibility and container non-root behavior where practical.

**Exit criteria:** checks that can run in the current environment pass; blocked tests are explicitly listed with reasons; no known critical blocker remains unaddressed.

### Phase 8 — Documentation and AWS-ready configuration
- Write the complete README: product overview, architecture, features, limitations, prerequisites, setup, environment variables, migrations, tests, troubleshooting, and screenshots guidance.
- Document local Docker setup and manual development commands.
- Document AWS ECS/S3/RDS/pgvector/SQS/CloudWatch architecture, permissions, secret handling, migrations, and deployment verification.
- Ensure all resume-listed technologies are represented truthfully in implementation or clearly scoped configuration/documentation. Do not imply AWS services were deployed if they were not.
- Verify a clean clone can follow the documented setup.

**Exit criteria:** another developer can understand the architecture and run the MVP from the README without relying on undocumented steps.

## 13. Completion checklist

Before declaring the project complete, verify all applicable items:

- [ ] Frontend and backend are real implementations, not mock screens.
- [ ] Local Docker Compose setup is documented and configuration is valid.
- [ ] PostgreSQL/pgvector is the main persistence and vector-search path.
- [ ] Repository ZIP upload is safe and bounded.
- [ ] Code-aware chunks have correct file/line metadata.
- [ ] Embedding configuration and dimension checks are enforced.
- [ ] Q&A uses retrieved repository evidence and validates citations.
- [ ] Missing LLM/embedding providers produce honest, understandable states.
- [ ] Security scanner uses explainable rules and redacts secrets.
- [ ] Findings are persisted, filterable, and linked to source locations.
- [ ] UI has working navigation, real API integration, loading/error/empty states, and responsive styling.
- [ ] Tests cover key safety and correctness behaviors.
- [ ] Frontend type-check/build and backend tests were actually run where possible.
- [ ] README, `.env.example`, migrations, and Docker files are present and accurate.
- [ ] AWS integration is clearly described as configured/documented versus actually deployed.
- [ ] No real secrets, private repository contents, or credentials are committed.
- [ ] `IMPLEMENTATION_STATUS.md` accurately records what passed, failed, or remains blocked.

## 14. Final response format from the coding agent

At the end, report:

1. **Implemented:** the actual features and main files/modules created.
2. **Run locally:** exact commands and URL(s).
3. **Configuration:** required and optional environment variables, including how to configure the LLM endpoint/model and embedding provider.
4. **Validation:** exact tests/builds run and their real results.
5. **Known limitations:** features that are incomplete, provider-specific, or not tested.
6. **AWS status:** what is implemented, what is only documented/configurable, and what would still be required for a real deployment.

Start by inspecting the repository, then implement Phase 0 through Phase 8. Do not stop at planning, and do not mark any exit criterion complete until it has been verified.
