# Enterprise Knowledge Copilot

An enterprise application for uploading documents, asking questions grounded in those documents, and managing retrieval behavior.

## Implementation

### Recommended technology baseline

These are recommended starting choices and can be adapted to deployment requirements:

- Initial formats: PDF, DOCX, and legacy DOC. Reject unsupported formats with an actionable message.
- Backend: Python with FastAPI; background ingestion workers for parsing and indexing.
- Frontend: TypeScript with React (Next.js is a reasonable starting point).
- Primary data store: PostgreSQL; use `pgvector` for embeddings and PostgreSQL full-text search for lexical retrieval in the first version.
- Original files: private object storage (S3-compatible), never public URLs.
- Background jobs/cache: Redis and a worker framework such as Celery or RQ.
- LLM and embedding providers: behind provider interfaces, selected through server-side configuration.
- Multi-user access: use organization/tenant and knowledge-base membership checks on every relevant operation.

If requirements later call for a dedicated vector service, OCR service, identity provider, or cloud platform, those can be introduced behind the same application boundaries.

### Application components

- **Knowledge user app:** document upload and status, knowledge-base selection, chat, source citations, and conversation history.
- **Admin dashboard:** user and knowledge-base management, configuration testing, and publishing approved chunking/retrieval options.
- **API:** authentication, authorization, uploads, chat orchestration, configuration, and audit events.
- **Ingestion workers:** file validation, text extraction/OCR, chunking, embedding generation, and indexing.
- **Storage:** PostgreSQL for application data, `pgvector` for embeddings, Redis for background jobs, and private object storage for originals.
- **AI integrations:** provider adapters for embeddings, retrieval reranking, and answer generation.

### Document and question flow

1. A user uploads an authorized PDF, DOCX, or DOC file to a knowledge base.
2. The backend validates and stores the file privately, then queues asynchronous processing.
3. A worker extracts text, applies the published chunking configuration, creates embeddings, and indexes the chunks.
4. The UI reports the document as searchable only after indexing completes.
5. A user asks a question about authorized knowledge bases.
6. The backend retrieves permitted evidence, generates an answer from that evidence, validates citations, and returns both answer and sources.

### Administration flow

1. An administrator configures chunking and retrieval strategies and their supported parameters.
2. The administrator evaluates draft settings against representative questions and documents.
3. The administrator publishes a validated, versioned configuration.
4. New questions use the published retrieval settings; future ingestion uses the published chunking settings.
5. Existing documents are reindexed only through an explicit admin operation.

## Implementation principles

- Never treat a successful upload as proof that a document was parsed or indexed. Expose each processing state.
- Do not answer from documents the requesting user cannot access. Apply access filters during retrieval, not only in the UI.
- Every answer should include citations to retrieved document passages. If evidence is insufficient, say so instead of inventing an answer.
- Administrators publish configurations. A user can select only options explicitly enabled by an administrator; if no user choice is enabled, use the published default.
- Configuration changes apply to new ingestion jobs and new questions. Existing indexes retain their configuration version until explicitly reprocessed.
- Keep original files, parsed text, chunks, embeddings, and chat data private and governed by a documented retention policy.

## Suggested build order

1. Authentication, organization membership, and knowledge-base permissions.
2. File upload, private storage, asynchronous processing, and processing status.
3. One reliable chunking strategy and vector retrieval with cited answers.
4. Document management and chat history.
5. Admin configuration with validation, preview/evaluation, and publish/version history.
6. Additional chunking and retrieval options, hybrid search, reranking, OCR, and production hardening.

## Local development

Requirements: Python 3.12–3.14 with [uv](https://docs.astral.sh/uv/), and Node.js 22.12+ with npm.

### Docker development stack

The backend and frontend run in Docker with automatic reload; Redis runs in Docker as well. The
database is the PostgreSQL instance already listening on the host at port 5432, because the
requested `DATABASE_URL` points to `localhost:5432`. The requested PostgreSQL role and database
must exist and allow migrations. Docker uses `host.docker.internal` to reach that same host
database; it does not create or switch to a second database. Copy the root and backend templates:

```sh
cp .env.example .env
cp backend/.env.example backend/.env
```

Start the app stack from the repository root:

```sh
docker compose up --build
```

The backend applies pending migrations at startup. The frontend is at http://localhost:3000 and
the API is at http://localhost:8000. Both reload after source changes, and containers restart
unless stopped. To run in the background, use `docker compose up --build -d`; view logs with
`docker compose logs -f backend frontend`; stop with `docker compose down`.

The host `DATABASE_URL` in the root and backend `.env` files remains
`postgresql+psycopg://username:password@localhost:5432/knowledge-copilot`. Only the Docker
container's hostname changes to `host.docker.internal`, which routes to that same host database.
The `username`/`password` credentials shown in the local templates are for development only.

### Backend

The backend reads `DATABASE_URL` from `backend/.env`. To use a PostgreSQL server installed
directly on your machine, set it to a synchronous SQLAlchemy URL such as
`postgresql+psycopg://username:password@localhost:5432/knowledge-copilot`. This app uses
synchronous SQLAlchemy with Psycopg; `asyncpg` URLs are not used by the runtime. Docker is optional
when this direct database is available.

```sh
cd backend
cp .env.example .env
uv sync --all-groups
uv run uvicorn enterprise_knowledge_copilot.main:app --reload
```

In another backend shell, run the checks:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

Apply or inspect database migrations from the backend directory:

```sh
uv run --env-file .env alembic upgrade head
uv run --env-file .env alembic current
uv run --env-file .env alembic check
```

Create a migration after changing models with
`uv run --env-file .env alembic revision --autogenerate -m "describe the schema change"`.
Review generated migrations before applying them. `alembic downgrade -1` rolls back one
revision; use it only in a disposable or explicitly approved environment. The initial downgrade
removes the application tables but intentionally leaves the shared `vector` extension installed.

### Frontend

```sh
cd frontend
npm ci
npm run dev
```

In another frontend shell, run the checks:

```sh
npm test
npm run lint
npm run format:check
npm run typecheck
```

The frontend is available at http://localhost:3000. The backend API is available at
http://localhost:8000, with its generated API docs at http://localhost:8000/docs.
The frontend proxies `/api/*` and `/health/*` requests to the backend, so the status and health
endpoints can also be accessed through `http://localhost:3000/api/v1/status`,
`http://localhost:3000/health/live`, and `http://localhost:3000/health/ready`.

### Local sign-in and owner account

For local development only, keep `DEVELOPMENT_AUTH_ENABLED=true` in `backend/.env`. The Docker
backend applies migrations at startup. Seed the owner account if it does not already exist:

```sh
cd backend
uv run --env-file .env alembic upgrade head
uv run --env-file .env python scripts/seed_local_admin.py
```

Start the Docker stack, open http://localhost:3000, and use the development credentials in
`backend/.env`. The seed creates the configured identity subject as an organization `owner` and
manager of the default `company-knowledge` knowledge base. Development authentication is blocked when
`ENVIRONMENT=production` and is not an identity-provider integration for deployed environments.
