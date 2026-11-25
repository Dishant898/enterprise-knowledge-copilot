from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_up_down_and_model_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "migration-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    backend_path = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(backend_path / "alembic.ini"))

    command.upgrade(alembic_config, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    try:
        table_names = set(inspect(engine).get_table_names())
        assert {
            "organizations",
            "users",
            "organization_memberships",
            "knowledge_bases",
            "knowledge_base_memberships",
            "alembic_version",
        } <= table_names
    finally:
        engine.dispose()

    command.check(alembic_config)
    command.downgrade(alembic_config, "base")

    engine = create_engine(f"sqlite:///{database_path}")
    try:
        assert not {
            "organizations",
            "users",
            "organization_memberships",
            "knowledge_bases",
            "knowledge_base_memberships",
        } & set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
