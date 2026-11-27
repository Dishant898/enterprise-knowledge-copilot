from __future__ import annotations

from sqlalchemy import select

from enterprise_knowledge_copilot.config import Settings
from enterprise_knowledge_copilot.db import (
    KnowledgeBase,
    KnowledgeBaseMembership,
    Organization,
    OrganizationMembership,
    User,
)
from enterprise_knowledge_copilot.db.session import configure_database, get_session_factory


def seed_local_admin() -> None:
    settings = Settings()
    if settings.environment.strip().lower() not in {"local", "development", "dev", "test"}:
        raise RuntimeError("Local admin seeding is only allowed outside production environments.")
    if not settings.development_auth_enabled:
        raise RuntimeError("Development authentication must be enabled to seed the local admin.")
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required.")

    configure_database(settings.database_url)
    subject = settings.development_auth_subject

    with get_session_factory()() as session:
        user = session.scalar(select(User).where(User.identity_provider_subject == subject))
        if user is None:
            user = User(identity_provider_subject=subject)
            session.add(user)
            session.flush()

        organization = session.scalar(select(Organization).where(Organization.slug == "acme"))
        if organization is None:
            organization = Organization(name="Acme", slug="acme")
            session.add(organization)
            session.flush()

        membership = session.get(OrganizationMembership, (organization.id, user.id))
        if membership is None:
            session.add(
                OrganizationMembership(
                    organization_id=organization.id,
                    user_id=user.id,
                    role="owner",
                )
            )
        elif membership.role != "owner":
            membership.role = "owner"

        knowledge_base = session.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.organization_id == organization.id,
                KnowledgeBase.slug == "company-knowledge",
            )
        )
        if knowledge_base is None:
            knowledge_base = KnowledgeBase(
                organization_id=organization.id,
                name="Company Knowledge",
                slug="company-knowledge",
                description="Default knowledge base managed by the local owner.",
            )
            session.add(knowledge_base)
            session.flush()

        kb_membership = session.get(
            KnowledgeBaseMembership,
            (organization.id, knowledge_base.id, user.id),
        )
        if kb_membership is None:
            session.add(
                KnowledgeBaseMembership(
                    organization_id=organization.id,
                    knowledge_base_id=knowledge_base.id,
                    user_id=user.id,
                    role="manager",
                )
            )
        elif kb_membership.role != "manager":
            kb_membership.role = "manager"

        session.commit()
        print(f"Seeded local owner {subject} in organization acme ({organization.id})")


if __name__ == "__main__":
    seed_local_admin()
