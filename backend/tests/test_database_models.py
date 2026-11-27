from __future__ import annotations

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enterprise_knowledge_copilot.db import (
    AuditEvent,
    Chat,
    ChatKnowledgeBase,
    ChunkEmbedding,
    Citation,
    ConfigurationVersion,
    Document,
    DocumentChunk,
    DocumentVersion,
    Feedback,
    IngestionJob,
    KnowledgeBase,
    KnowledgeBaseMembership,
    Message,
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


def test_user_profile_fields_and_unique_email(db_session: Session) -> None:
    user = User(
        identity_provider_subject="idp|profile",
        username="alice",
        email="alice@example.com",
        full_name="Alice Example",
        password_hash="$argon2id$encoded-value",
    )
    db_session.add(user)
    db_session.commit()

    assert user.email == "alice@example.com"
    assert user.password_hash is not None
    assert user.password_hash.startswith("$argon2id$")
    assert user.is_active
    assert not user.is_email_verified

    db_session.add(User(identity_provider_subject="idp|duplicate", email="alice@example.com"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_full_domain_schema_relations(db_session: Session) -> None:
    organization = Organization(name="Acme", slug="acme")
    user = User(identity_provider_subject="idp|alice", email="alice@example.com")
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
        created_by_user_id=user.id,
    )
    configuration = ConfigurationVersion(
        organization_id=organization.id,
        version=1,
        schema_version="1",
        settings={"chunk_size": 500},
        status="published",
        created_by_user_id=user.id,
    )
    db_session.add_all([knowledge_base, configuration])
    db_session.flush()

    document = Document(
        organization_id=organization.id,
        knowledge_base_id=knowledge_base.id,
        uploaded_by_user_id=user.id,
        original_filename="policy.pdf",
    )
    chat = Chat(organization_id=organization.id, owner_user_id=user.id, title="Policies")
    db_session.add_all([document, chat])
    db_session.flush()

    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        storage_key="private/acme/policy.pdf",
        sha256="a" * 64,
        mime_type="application/pdf",
        size_bytes=1234,
        ingestion_config_version_id=configuration.id,
    )
    db_session.add(version)
    db_session.flush()

    job = IngestionJob(document_version_id=version.id, job_type="extract")
    chunk = DocumentChunk(
        document_version_id=version.id,
        ordinal=0,
        content="Policy text",
        content_hash="b" * 64,
        page_number=1,
        start_char=0,
        end_char=11,
    )
    db_session.add_all([job, chunk])
    db_session.flush()
    db_session.add(
        ChunkEmbedding(
            chunk_id=chunk.id,
            model_name="example-embedding",
            model_version="v1",
            dimensions=3,
            embedding=[0.1, 0.2, 0.3],
        )
    )
    db_session.add(
        ChatKnowledgeBase(
            organization_id=organization.id,
            chat_id=chat.id,
            knowledge_base_id=knowledge_base.id,
        )
    )
    message = Message(
        chat_id=chat.id,
        sequence_number=1,
        role="assistant",
        content="See the policy.",
        configuration_version_id=configuration.id,
    )
    db_session.add(message)
    db_session.flush()
    db_session.add_all(
        [
            Citation(message_id=message.id, chunk_id=chunk.id, citation_number=1),
            Feedback(message_id=message.id, user_id=user.id, rating=5),
            AuditEvent(
                organization_id=organization.id,
                actor_user_id=user.id,
                action="document.uploaded",
                entity_type="document",
                entity_id=document.id,
                request_id="request-1",
            ),
        ]
    )
    db_session.commit()

    assert db_session.query(ChunkEmbedding).count() == 1
    assert db_session.query(Citation).count() == 1
    assert db_session.query(Feedback).count() == 1
    assert db_session.query(IngestionJob).count() == 1
