from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_schema_migration_preserves_existing_users_and_model_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "migration-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    backend_path = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(backend_path / "alembic.ini"))

    command.upgrade(alembic_config, "0002_knowledge_base_api")
    engine = create_engine(f"sqlite:///{database_path}")
    legacy_user_id = uuid4()
    local_user_id = uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO users (id, identity_provider_subject) VALUES (:id, :subject)"),
                {"id": str(legacy_user_id), "subject": "idp|legacy-user"},
            )
    finally:
        engine.dispose()

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
            "audit_events",
            "configuration_versions",
            "documents",
            "document_versions",
            "ingestion_jobs",
            "document_chunks",
            "chunk_embeddings",
            "chats",
            "chat_knowledge_bases",
            "messages",
            "citations",
            "feedback",
            "alembic_version",
        } <= table_names
        user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
        assert {
            "username",
            "email",
            "full_name",
            "password_hash",
            "is_active",
            "is_email_verified",
            "last_login_at",
        } <= user_columns
        with engine.begin() as connection:
            legacy_user = (
                connection.execute(
                    text(
                        "SELECT identity_provider_subject, email, password_hash, is_active "
                        "FROM users WHERE id = :id"
                    ),
                    {"id": str(legacy_user_id)},
                )
                .mappings()
                .one()
            )
            assert legacy_user["identity_provider_subject"] == "idp|legacy-user"
            assert legacy_user["email"] is None
            assert legacy_user["password_hash"] is None
            assert legacy_user["is_active"] == 1
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, identity_provider_subject, username, email, full_name, password_hash) "
                    "VALUES (:id, NULL, :username, :email, :full_name, :password_hash)"
                ),
                {
                    "id": str(local_user_id),
                    "username": "local-user",
                    "email": "local@example.com",
                    "full_name": "Local User",
                    "password_hash": "$argon2id$encoded-value",
                },
            )
    finally:
        engine.dispose()

    command.check(alembic_config)
    engine = create_engine(f"sqlite:///{database_path}")
    try:
        with engine.begin() as connection:
            local_user = (
                connection.execute(
                    text(
                        "SELECT identity_provider_subject, username, email, password_hash "
                        "FROM users WHERE id = :id"
                    ),
                    {"id": str(local_user_id)},
                )
                .mappings()
                .one()
            )
            assert local_user["identity_provider_subject"] is None
            assert local_user["username"] == "local-user"
            assert local_user["email"] == "local@example.com"
            assert local_user["password_hash"].startswith("$argon2id$")
            connection.execute(
                text("DELETE FROM users WHERE id = :id"),
                {"id": str(local_user_id)},
            )
    finally:
        engine.dispose()

    command.downgrade(alembic_config, "base")

    engine = create_engine(f"sqlite:///{database_path}")
    try:
        assert not {
            "organizations",
            "users",
            "organization_memberships",
            "knowledge_bases",
            "knowledge_base_memberships",
            "audit_events",
            "configuration_versions",
            "documents",
            "document_versions",
            "ingestion_jobs",
            "document_chunks",
            "chunk_embeddings",
            "chats",
            "chat_knowledge_bases",
            "messages",
            "citations",
            "feedback",
        } & set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
