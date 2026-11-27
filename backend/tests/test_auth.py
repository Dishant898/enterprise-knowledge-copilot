from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from enterprise_knowledge_copilot.app_factory import create_app
from enterprise_knowledge_copilot.auth import (
    AuthenticatedPrincipal,
    DevelopmentIdentityAdapter,
    IdentityClaims,
    resolve_principal,
)
from enterprise_knowledge_copilot.config import Settings
from enterprise_knowledge_copilot.db import (
    Base,
    KnowledgeBase,
    KnowledgeBaseMembership,
    Organization,
    OrganizationMembership,
    User,
)


def test_development_auth_rejected_in_production() -> None:
    try:
        Settings(
            database_url="postgresql://localhost/app",
            redis_url="redis://localhost/0",
            environment="production",
            development_auth_enabled=True,
        )
    except ValidationError:
        return
    raise AssertionError("development authentication was allowed in production")


def test_development_adapter_rejects_explicit_production() -> None:
    try:
        DevelopmentIdentityAdapter(enabled=True, environment="production")
    except RuntimeError:
        return
    raise AssertionError("development adapter was allowed in production")


def test_missing_authentication_is_rejected() -> None:
    settings = Settings(
        database_url="postgresql://localhost/app",
        redis_url="redis://localhost/0",
    )
    app = create_app(settings)
    app.state.db_session = None

    response = TestClient(app).get("/api/v1/auth/me")

    assert response.status_code == 401


def test_development_principal_resolves_current_memberships() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        organization = Organization(name="Acme", slug="acme")
        user = User(identity_provider_subject="dev|alice")
        session.add_all([organization, user])
        session.flush()
        session.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role="admin",
            )
        )
        knowledge_base = KnowledgeBase(
            organization_id=organization.id,
            name="Policies",
            slug="policies",
        )
        session.add(knowledge_base)
        session.flush()
        session.add(
            KnowledgeBaseMembership(
                organization_id=organization.id,
                knowledge_base_id=knowledge_base.id,
                user_id=user.id,
                role="manager",
            )
        )
        session.commit()

        principal = resolve_principal(session, IdentityClaims(subject="dev|alice"))
        assert principal.organization_roles[organization.id] == "admin"
        assert principal.knowledge_base_roles[(organization.id, knowledge_base.id)] == "manager"

        settings = Settings(
            database_url="sqlite://",
            redis_url="redis://localhost/0",
            environment="local",
            development_auth_enabled=True,
        )
        app = create_app(settings)
        app.state.db_session = session
        response = TestClient(app).get(
            "/api/v1/auth/me",
            headers={"X-Development-Subject": "dev|alice"},
        )
        assert response.status_code == 200

    engine.dispose()


def test_organization_and_kb_permission_helpers() -> None:
    organization_id = "8cefd3bc-bd4d-4bd7-9ab6-5b8c0ca1d4e4"
    knowledge_base_id = "3d7818d8-a1a1-4cd8-b1f4-4f3fe6a872cc"
    from uuid import UUID

    principal = AuthenticatedPrincipal(
        subject="user",
        organization_roles={UUID(organization_id): "owner"},
        knowledge_base_roles={
            (UUID(organization_id), UUID(knowledge_base_id)): "manager"
        },
    )
    from enterprise_knowledge_copilot.permissions import (
        knowledge_base_role_at_least,
        organization_role_at_least,
    )

    assert organization_role_at_least(principal, UUID(organization_id), "admin")
    assert knowledge_base_role_at_least(
        principal,
        UUID(organization_id),
        UUID(knowledge_base_id),
        "editor",
    )
