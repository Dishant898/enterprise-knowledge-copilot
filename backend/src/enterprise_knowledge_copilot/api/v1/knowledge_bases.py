from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enterprise_knowledge_copilot.auth import AuthenticatedPrincipal, require_principal
from enterprise_knowledge_copilot.db import (
    AuditEvent,
    KnowledgeBase,
    KnowledgeBaseMembership,
    OrganizationMembership,
)
from enterprise_knowledge_copilot.db.session import get_db

router = APIRouter(
    prefix="/organizations/{organization_id}/knowledge-bases",
    tags=["knowledge-bases"],
)


class KnowledgeBaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class KnowledgeBaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class MembershipUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    role: Literal["manager", "editor", "viewer"]


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    description: str | None


def _require_org_admin(
    principal: AuthenticatedPrincipal,
    organization_id: UUID,
) -> None:
    role = principal.organization_roles.get(organization_id)
    if role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")


def _require_kb_access(
    principal: AuthenticatedPrincipal,
    organization_id: UUID,
    knowledge_base_id: UUID,
) -> None:
    org_role = principal.organization_roles.get(organization_id)
    if org_role in {"owner", "admin"}:
        return
    kb_role = principal.knowledge_base_roles.get((organization_id, knowledge_base_id))
    if kb_role not in {"manager", "editor", "viewer"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Knowledge base not found."
        )


def _require_kb_manager(
    principal: AuthenticatedPrincipal,
    organization_id: UUID,
    knowledge_base_id: UUID,
) -> None:
    org_role = principal.organization_roles.get(organization_id)
    if org_role in {"owner", "admin"}:
        return
    kb_role = principal.knowledge_base_roles.get((organization_id, knowledge_base_id))
    if kb_role != "manager":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")


def _audit(
    session: Session,
    principal: AuthenticatedPrincipal,
    organization_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    metadata: dict[str, object],
) -> None:
    session.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=principal.user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            event_metadata=metadata,
        )
    )


@router.get("", response_model=list[KnowledgeBaseResponse])
def list_knowledge_bases(
    organization_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_principal)],
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[KnowledgeBase]:
    org_role = principal.organization_roles.get(organization_id)
    if org_role not in {"owner", "admin", "member"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    if org_role in {"owner", "admin"}:
        statement = (
            select(KnowledgeBase)
            .where(KnowledgeBase.organization_id == organization_id)
            .order_by(KnowledgeBase.name, KnowledgeBase.id)
            .offset(offset)
            .limit(limit)
        )
    else:
        ids = [
            knowledge_base_id
            for (org_id, knowledge_base_id) in principal.knowledge_base_roles
            if org_id == organization_id
        ]
        if not ids:
            return []
        statement = (
            select(KnowledgeBase)
            .where(KnowledgeBase.organization_id == organization_id)
            .where(KnowledgeBase.id.in_(ids))
            .order_by(KnowledgeBase.name, KnowledgeBase.id)
            .offset(offset)
            .limit(limit)
        )
    return list(session.scalars(statement).all())


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    organization_id: UUID,
    payload: KnowledgeBaseCreate,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_principal)],
    session: Annotated[Session, Depends(get_db)],
) -> KnowledgeBase:
    _require_org_admin(principal, organization_id)
    knowledge_base = KnowledgeBase(
        organization_id=organization_id,
        name=payload.name.strip(),
        slug=payload.slug,
        description=payload.description.strip() if payload.description else None,
    )
    session.add(knowledge_base)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Knowledge base already exists."
        ) from exc
    _audit(
        session,
        principal,
        organization_id,
        "knowledge_base.created",
        "knowledge_base",
        knowledge_base.id,
        {"name": knowledge_base.name, "slug": knowledge_base.slug},
    )
    session.commit()
    session.refresh(knowledge_base)
    return knowledge_base


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
def get_knowledge_base(
    organization_id: UUID,
    knowledge_base_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_principal)],
    session: Annotated[Session, Depends(get_db)],
) -> KnowledgeBase:
    _require_kb_access(principal, organization_id, knowledge_base_id)
    knowledge_base = session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.organization_id == organization_id,
            KnowledgeBase.id == knowledge_base_id,
        )
    )
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found."
        )
    return knowledge_base


@router.patch("/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
def update_knowledge_base(
    organization_id: UUID,
    knowledge_base_id: UUID,
    payload: KnowledgeBaseUpdate,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_principal)],
    session: Annotated[Session, Depends(get_db)],
) -> KnowledgeBase:
    _require_kb_manager(principal, organization_id, knowledge_base_id)
    knowledge_base = session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.organization_id == organization_id,
            KnowledgeBase.id == knowledge_base_id,
        )
    )
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found."
        )

    changes: dict[str, object] = {}
    for field_name in ("name", "slug", "description"):
        value = getattr(payload, field_name)
        if value is not None:
            normalized = value.strip() if isinstance(value, str) else value
            setattr(knowledge_base, field_name, normalized)
            changes[field_name] = normalized
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Knowledge base already exists."
        ) from exc
    _audit(
        session,
        principal,
        organization_id,
        "knowledge_base.updated",
        "knowledge_base",
        knowledge_base.id,
        changes,
    )
    session.commit()
    session.refresh(knowledge_base)
    return knowledge_base


@router.put("/{knowledge_base_id}/memberships", response_model=dict[str, str])
def upsert_membership(
    organization_id: UUID,
    knowledge_base_id: UUID,
    payload: MembershipUpsert,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_principal)],
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    _require_kb_manager(principal, organization_id, knowledge_base_id)

    knowledge_base = session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.organization_id == organization_id,
            KnowledgeBase.id == knowledge_base_id,
        )
    )
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found."
        )

    org_membership = session.get(
        OrganizationMembership,
        (organization_id, payload.user_id),
    )
    if org_membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User membership not found."
        )

    membership = session.scalar(
        select(KnowledgeBaseMembership).where(
            KnowledgeBaseMembership.organization_id == organization_id,
            KnowledgeBaseMembership.knowledge_base_id == knowledge_base_id,
            KnowledgeBaseMembership.user_id == payload.user_id,
        )
    )
    old_role = membership.role if membership else None
    if membership is None:
        membership = KnowledgeBaseMembership(
            organization_id=organization_id,
            knowledge_base_id=knowledge_base_id,
            user_id=payload.user_id,
            role=payload.role,
        )
        session.add(membership)
    else:
        membership.role = payload.role

    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Membership could not be saved."
        ) from exc
    _audit(
        session,
        principal,
        organization_id,
        "knowledge_base.membership.upserted",
        "knowledge_base_membership",
        knowledge_base_id,
        {"user_id": str(payload.user_id), "old_role": old_role, "role": payload.role},
    )
    session.commit()
    return {"user_id": str(payload.user_id), "role": payload.role}


@router.delete("/{knowledge_base_id}/memberships/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_membership(
    organization_id: UUID,
    knowledge_base_id: UUID,
    user_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_principal)],
    session: Annotated[Session, Depends(get_db)],
) -> None:
    _require_kb_manager(principal, organization_id, knowledge_base_id)
    membership = session.scalar(
        select(KnowledgeBaseMembership).where(
            KnowledgeBaseMembership.organization_id == organization_id,
            KnowledgeBaseMembership.knowledge_base_id == knowledge_base_id,
            KnowledgeBaseMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found.")
    old_role = membership.role
    session.delete(membership)
    _audit(
        session,
        principal,
        organization_id,
        "knowledge_base.membership.removed",
        "knowledge_base_membership",
        knowledge_base_id,
        {"user_id": str(user_id), "old_role": old_role},
    )
    session.commit()
