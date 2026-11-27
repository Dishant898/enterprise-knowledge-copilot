from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from enterprise_knowledge_copilot.app_factory import create_app
from enterprise_knowledge_copilot.config import Settings
from enterprise_knowledge_copilot.db import (
    AuditEvent,
    Base,
    KnowledgeBase,
    Organization,
    OrganizationMembership,
    User,
)


@pytest.fixture
def kb_api() -> Iterator[tuple[TestClient, sessionmaker[Session], Organization, User]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with factory() as session:
        organization = Organization(name="Acme", slug="acme")
        owner = User(identity_provider_subject="dev|owner")
        member = User(identity_provider_subject="dev|member")
        session.add_all([organization, owner, member])
        session.flush()
        session.add_all(
            [
                OrganizationMembership(
                    organization_id=organization.id,
                    user_id=owner.id,
                    role="owner",
                ),
                OrganizationMembership(
                    organization_id=organization.id,
                    user_id=member.id,
                    role="member",
                ),
            ]
        )
        session.commit()

    settings = Settings(
        database_url="sqlite://",
        redis_url="redis://localhost/0",
        environment="local",
        development_auth_enabled=True,
    )
    app = create_app(settings)
    app.state.db_session = factory
    client = TestClient(app)
    with factory() as session:
        org = session.get(Organization, organization.id)
        owner_user = session.scalar(
            select(User).where(User.identity_provider_subject == "dev|owner")
        )
        assert org is not None
        assert owner_user is not None
    yield client, factory, org, owner_user
    engine.dispose()


def _owner_headers() -> dict[str, str]:
    return {"X-Development-Subject": "dev|owner"}


def _member_headers() -> dict[str, str]:
    return {"X-Development-Subject": "dev|member"}


def test_create_list_detail_update_and_membership(
    kb_api: tuple[TestClient, sessionmaker[Session], Organization, User],
) -> None:
    client, factory, organization, owner = kb_api
    prefix = f"/api/v1/organizations/{organization.id}/knowledge-bases"

    response = client.post(
        prefix,
        headers=_owner_headers(),
        json={"name": "Policies", "slug": "policies", "description": "Company policies"},
    )
    assert response.status_code == 201
    kb_id = response.json()["id"]

    listed = client.get(prefix, headers=_owner_headers())
    assert listed.status_code == 200
    assert [item["slug"] for item in listed.json()] == ["policies"]

    detail = client.get(f"{prefix}/{kb_id}", headers=_owner_headers())
    assert detail.status_code == 200
    assert detail.json()["description"] == "Company policies"

    updated = client.patch(
        f"{prefix}/{kb_id}",
        headers=_owner_headers(),
        json={"name": "Updated Policies", "description": "Updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Policies"

    with factory() as session:
        member = session.scalar(select(User).where(User.identity_provider_subject == "dev|member"))
        assert member is not None
        member_id = member.id

    membership = client.put(
        f"{prefix}/{kb_id}/memberships",
        headers=_owner_headers(),
        json={"user_id": str(member_id), "role": "viewer"},
    )
    assert membership.status_code == 200

    member_list = client.get(prefix, headers=_member_headers())
    assert member_list.status_code == 200
    assert [item["id"] for item in member_list.json()] == [kb_id]

    removed = client.delete(
        f"{prefix}/{kb_id}/memberships/{member_id}",
        headers=_owner_headers(),
    )
    assert removed.status_code == 204

    with factory() as session:
        audit_count = session.query(AuditEvent).count()
        assert audit_count >= 4


def test_regular_member_cannot_create_or_cross_tenant_access(
    kb_api: tuple[TestClient, sessionmaker[Session], Organization, User],
) -> None:
    client, factory, organization, owner = kb_api
    prefix = f"/api/v1/organizations/{organization.id}/knowledge-bases"

    denied_create = client.post(
        prefix,
        headers=_member_headers(),
        json={"name": "Secret", "slug": "secret"},
    )
    assert denied_create.status_code == 403

    with factory() as session:
        other_org = Organization(name="Other", slug="other")
        kb = KnowledgeBase(
            organization_id=organization.id,
            name="Private",
            slug="private",
        )
        session.add_all([other_org, kb])
        session.flush()

    detail = client.get(
        f"/api/v1/organizations/{other_org.id}/knowledge-bases/{kb.id}",
        headers=_member_headers(),
    )
    assert detail.status_code == 403
