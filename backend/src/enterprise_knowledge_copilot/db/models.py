from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
    true,
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
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active"
    )
    settings: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'archived')",
            name="status_allowed",
        ),
    )


class User(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "email IS NULL OR email = lower(email)",
            name="email_lowercase",
        ),
        CheckConstraint(
            "username IS NULL OR username = lower(username)",
            name="username_lowercase",
        ),
    )

    identity_provider_subject: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )
    username: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, unique=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default=true())
    is_email_verified: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=false()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OrganizationMembership(Timestamped, Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="role_allowed",
        ),
        CheckConstraint(
            "status IN ('active', 'invited', 'suspended')",
            name="status_allowed",
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
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active"
    )


class KnowledgeBase(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_knowledge_bases_org_id_id"),
        UniqueConstraint("organization_id", "name", name="uq_knowledge_bases_org_name"),
        UniqueConstraint("organization_id", "slug", name="uq_knowledge_bases_org_slug"),
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="status_allowed",
        ),
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
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active"
    )


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


class ConfigurationVersion(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "configuration_versions"
    __table_args__ = (
        UniqueConstraint("organization_id", "version", name="uq_config_versions_org_version"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "status IN ('draft', 'published', 'retired')",
            name="status_allowed",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_config_versions_organization_id_organizations",
            ondelete="CASCADE",
        ),
        Index("ix_config_versions_org_status", "organization_id", "status"),
        Index(
            "uq_config_versions_one_published_per_org",
            "organization_id",
            unique=True,
            sqlite_where=text("status = 'published'"),
            postgresql_where=text("status = 'published'"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    settings: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft"
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Document(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'ready', 'failed', 'archived', 'deleted')",
            name="status_allowed",
        ),
        ForeignKeyConstraint(
            ["organization_id", "knowledge_base_id"],
            ["knowledge_bases.organization_id", "knowledge_bases.id"],
            name="fk_documents_org_knowledge_base",
            ondelete="CASCADE",
        ),
        Index(
            "ix_documents_org_kb_status",
            "organization_id",
            "knowledge_base_id",
            "status",
        ),
        Index("ix_documents_uploaded_by_user_id", "uploaded_by_user_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    knowledge_base_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="uploaded", server_default="uploaded"
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict, server_default=text("'{}'")
    )


class DocumentVersion(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_versions_number"),
        CheckConstraint("version_number > 0", name="version_number_positive"),
        CheckConstraint("size_bytes >= 0", name="size_bytes_nonnegative"),
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'ready', 'failed', 'archived')",
            name="status_allowed",
        ),
        Index("ix_document_versions_document_id", "document_id"),
    )

    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ingestion_config_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("configuration_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    extraction_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="uploaded", server_default="uploaded"
    )


class IngestionJob(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('extract', 'chunk', 'embed', 'index')",
            name="job_type_allowed",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="status_allowed",
        ),
        CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
        CheckConstraint("max_attempts > 0", name="max_attempts_positive"),
        Index("ix_ingestion_jobs_status_created", "status", "created_at"),
        Index("ix_ingestion_jobs_version_status", "document_version_id", "status"),
    )

    document_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    configuration_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("configuration_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", server_default="queued"
    )
    attempts: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(nullable=False, default=5, server_default="5")
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentChunk(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id",
            "ordinal",
            name="uq_document_chunks_version_ordinal",
        ),
        CheckConstraint("ordinal >= 0", name="ordinal_nonnegative"),
        CheckConstraint("page_number IS NULL OR page_number > 0", name="page_number_positive"),
        CheckConstraint(
            "start_char IS NULL OR start_char >= 0",
            name="start_char_nonnegative",
        ),
        CheckConstraint(
            "end_char IS NULL OR end_char >= start_char",
            name="char_range_valid",
        ),
        Index("ix_document_chunks_version_id", "document_version_id"),
        Index("ix_document_chunks_content_hash", "content_hash"),
    )

    document_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    section_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    start_char: Mapped[int | None] = mapped_column(nullable=True)
    end_char: Mapped[int | None] = mapped_column(nullable=True)
    chunk_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict, server_default=text("'{}'")
    )


class ChunkEmbedding(Timestamped, Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        CheckConstraint("dimensions > 0", name="dimensions_positive"),
        Index("ix_chunk_embeddings_model", "model_name", "model_version"),
    )

    chunk_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    dimensions: Mapped[int] = mapped_column(nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)


class Chat(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "chats"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_chats_org_id_id"),
        CheckConstraint("status IN ('active', 'archived')", name="status_allowed"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_chats_organization_id_organizations",
            ondelete="CASCADE",
        ),
        Index("ix_chats_org_owner_updated", "organization_id", "owner_user_id", "updated_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active"
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatKnowledgeBase(Timestamped, Base):
    __tablename__ = "chat_knowledge_bases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "chat_id"],
            ["chats.organization_id", "chats.id"],
            name="fk_chat_kbs_org_chat",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "knowledge_base_id"],
            ["knowledge_bases.organization_id", "knowledge_bases.id"],
            name="fk_chat_kbs_org_knowledge_base",
            ondelete="CASCADE",
        ),
        Index("ix_chat_knowledge_bases_knowledge_base_id", "knowledge_base_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    chat_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    knowledge_base_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)


class Message(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("chat_id", "sequence_number", name="uq_messages_chat_sequence"),
        CheckConstraint("sequence_number > 0", name="sequence_number_positive"),
        CheckConstraint("role IN ('system', 'user', 'assistant', 'tool')", name="role_allowed"),
        CheckConstraint(
            "status IN ('pending', 'complete', 'failed')",
            name="status_allowed",
        ),
        CheckConstraint(
            "prompt_tokens IS NULL OR prompt_tokens >= 0", name="prompt_tokens_nonnegative"
        ),
        CheckConstraint(
            "completion_tokens IS NULL OR completion_tokens >= 0",
            name="completion_tokens_nonnegative",
        ),
        Index("ix_messages_chat_created", "chat_id", "created_at"),
    )

    chat_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_number: Mapped[int] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="complete", server_default="complete"
    )
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    configuration_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("configuration_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    prompt_tokens: Mapped[int | None] = mapped_column(nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(nullable=True)
    usage_metadata: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )


class Citation(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "citations"
    __table_args__ = (
        UniqueConstraint("message_id", "citation_number", name="uq_citations_message_number"),
        CheckConstraint("citation_number > 0", name="citation_number_positive"),
        CheckConstraint("page_number IS NULL OR page_number > 0", name="page_number_positive"),
        Index("ix_citations_chunk_id", "chunk_id"),
    )

    message_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    citation_number: Mapped[int] = mapped_column(nullable=False)
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    start_char: Mapped[int | None] = mapped_column(nullable=True)
    end_char: Mapped[int | None] = mapped_column(nullable=True)
    excerpt_metadata: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class Feedback(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "feedback"
    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_feedback_message_user"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
        Index("ix_feedback_created_at", "created_at"),
    )

    message_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rating: Mapped[int] = mapped_column(nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEvent(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_org_created", "organization_id", "created_at"),
        Index("ix_audit_events_request_id", "request_id"),
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
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcome: Mapped[str] = mapped_column(
        String(32), nullable=False, default="succeeded", server_default="succeeded"
    )
