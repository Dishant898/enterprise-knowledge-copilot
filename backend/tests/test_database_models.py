from __future__ import annotations

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enterprise_knowledge_copilot.db import (
    KnowledgeBase,
    KnowledgeBaseMembership,
    Organization,
    OrganizationMembership,
    User,
)


def test_organization_and_knowledge_base_membership(db_session: Session) -> None:
    organization = Organization(name="Acme", slug="acme")
    user = User(identity_provider_subject="idp|user-1")
    db_session.add_all([organization, user])
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role="member",
        )
    )
    knowledge_base = KnowledgeBase(
        organization_id=organization.id,
        name="Policies",
        slug="policies",
    )
    db_session.add(knowledge_base)
    db_session.flush()
    db_session.add(
        KnowledgeBaseMembership(
            organization_id=organization.id,
            knowledge_base_id=knowledge_base.id,
            user_id=user.id,
            role="viewer",
        )
    )
    db_session.commit()

    assert db_session.query(KnowledgeBaseMembership).count() == 1


def test_membership_pair_is_unique(db_session: Session) -> None:
    organization = Organization(name="Acme", slug="acme")
    user = User(identity_provider_subject="idp|user-1")
    db_session.add_all([organization, user])
    db_session.flush()
    membership = OrganizationMembership(
        organization_id=organization.id,
        user_id=user.id,
        role="member",
    )
    db_session.add(membership)
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.execute(
            insert(OrganizationMembership).values(
                organization_id=organization.id,
                user_id=user.id,
                role="admin",
            )
        )


def test_knowledge_base_membership_cannot_cross_organization(
    db_session: Session,
) -> None:
    organization_a = Organization(name="Acme", slug="acme")
    organization_b = Organization(name="Globex", slug="globex")
    user = User(identity_provider_subject="idp|user-1")
    db_session.add_all([organization_a, organization_b, user])
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            organization_id=organization_b.id,
            user_id=user.id,
            role="member",
        )
    )
    knowledge_base = KnowledgeBase(
        organization_id=organization_a.id,
        name="Policies",
        slug="policies",
    )
    db_session.add(knowledge_base)
    db_session.flush()
    db_session.add(
        KnowledgeBaseMembership(
            organization_id=organization_a.id,
            knowledge_base_id=knowledge_base.id,
            user_id=user.id,
            role="viewer",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
