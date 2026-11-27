FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.14 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --all-groups --no-install-project

COPY . .
RUN uv sync --frozen --all-groups

ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000

CMD ["sh", "-c", "uv run alembic upgrade head && exec uv run uvicorn enterprise_knowledge_copilot.main:app --host 0.0.0.0 --port 8000 --reload"]
