from __future__ import annotations

from uuid import UUID

from enterprise_knowledge_copilot.auth import AuthenticatedPrincipal

ORGANIZATION_ROLE_ORDER = {"member": 1, "admin": 2, "owner": 3}
KNOWLEDGE_BASE_ROLE_ORDER = {"viewer": 1, "editor": 2, "manager": 3}


def has_organization_role(
    principal: AuthenticatedPrincipal,
    organization_id: UUID,
    role: str,
) -> bool:
    return principal.organization_roles.get(organization_id) == role


def organization_role_at_least(
    principal: AuthenticatedPrincipal,
    organization_id: UUID,
    minimum_role: str,
) -> bool:
    role = principal.organization_roles.get(organization_id)
    if role not in ORGANIZATION_ROLE_ORDER or minimum_role not in ORGANIZATION_ROLE_ORDER:
        return False
    return ORGANIZATION_ROLE_ORDER[role] >= ORGANIZATION_ROLE_ORDER[minimum_role]


def has_knowledge_base_role(
    principal: AuthenticatedPrincipal,
    organization_id: UUID,
    knowledge_base_id: UUID,
    role: str,
) -> bool:
    return principal.knowledge_base_roles.get((organization_id, knowledge_base_id)) == role


def knowledge_base_role_at_least(
    principal: AuthenticatedPrincipal,
    organization_id: UUID,
    knowledge_base_id: UUID,
    minimum_role: str,
) -> bool:
    role = principal.knowledge_base_roles.get((organization_id, knowledge_base_id))
    if role not in KNOWLEDGE_BASE_ROLE_ORDER or minimum_role not in KNOWLEDGE_BASE_ROLE_ORDER:
        return False
    return KNOWLEDGE_BASE_ROLE_ORDER[role] >= KNOWLEDGE_BASE_ROLE_ORDER[minimum_role]
