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

### Local infrastructure

Use Docker to start the local PostgreSQL + pgvector and Redis dependencies before the backend service. Copy the repository template and start the stack:

```sh
cp .env.example .env
docker compose up -d
```

Check readiness:

```sh
docker compose ps
docker compose exec postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose exec redis sh -lc 'redis-cli -a "$REDIS_PASSWORD" ping'
```

Stop the stack without deleting the named volumes:

```sh
docker compose stop
```

Reset the local data only when you intentionally want to destroy the developer volumes:

```sh
docker compose down -v
```

This project intentionally does not add an S3-compatible object-store emulator yet; the first upload steps will use a fake/test adapter until the private-storage implementation is introduced in Step 08.

### Backend

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
