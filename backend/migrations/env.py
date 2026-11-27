from __future__ import annotations

import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from alembic.runtime.migration import MigrationContext
from pgvector.sqlalchemy import Vector
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.type_api import TypeEngine

from enterprise_knowledge_copilot.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _compare_type(
    migration_context: MigrationContext,
    _inspected_column: Column[Any],
    _metadata_column: Column[Any],
    _inspected_type: TypeEngine[Any],
    metadata_type: TypeEngine[Any],
) -> bool | None:
    if migration_context.dialect.name == "sqlite" and isinstance(metadata_type, Vector):
        return False
    return None


def _database_url() -> str:
    raw_url = os.environ.get("DATABASE_URL")
    if not raw_url:
        raise RuntimeError(
            "DATABASE_URL is required. Run Alembic with the backend .env loaded "
            "(for example: uv run --env-file .env alembic current)."
        )
    url = make_url(raw_url)
    if url.drivername in {"postgres", "postgresql", "postgresql+asyncpg"}:
        url = url.set(drivername="postgresql+psycopg")
    return url.render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=_compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=_compare_type,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
