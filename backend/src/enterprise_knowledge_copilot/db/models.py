from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from enterprise_knowledge_copilot.db.base import Base


class UUIDPrimaryKey:
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Organization(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)


class User(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "users"

    identity_provider_subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )


class OrganizationMembership(Timestamped, Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="role_allowed",
        ),
        Index("ix_organization_memberships_user_id", "user_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)


class KnowledgeBase(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_knowledge_bases_org_id_id"),
        UniqueConstraint("organization_id", "name", name="uq_knowledge_bases_org_name"),
        UniqueConstraint("organization_id", "slug", name="uq_knowledge_bases_org_slug"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_knowledge_bases_organization_id_organizations",
            ondelete="CASCADE",
        ),
        Index("ix_knowledge_bases_organization_id", "organization_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class KnowledgeBaseMembership(Timestamped, Base):
    __tablename__ = "knowledge_base_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('manager', 'editor', 'viewer')",
            name="role_allowed",
        ),
        ForeignKeyConstraint(
            ["organization_id", "knowledge_base_id"],
            ["knowledge_bases.organization_id", "knowledge_bases.id"],
            name="fk_kb_memberships_org_knowledge_base",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            name="fk_kb_memberships_org_membership",
            ondelete="CASCADE",
        ),
        Index("ix_kb_memberships_org_user", "organization_id", "user_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    knowledge_base_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)


class AuditEvent(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_org_created", "organization_id", "created_at"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_audit_events_organization_id_organizations",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    event_metadata: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
