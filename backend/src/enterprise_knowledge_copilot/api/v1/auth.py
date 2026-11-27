from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response

from enterprise_knowledge_copilot.auth import AuthenticatedPrincipal, require_principal

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/me")
def auth_me(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_principal)],
) -> dict[str, Any]:
    return {
        "subject": principal.subject,
        "user_id": str(principal.user_id) if principal.user_id else None,
        "organization_roles": {
            str(organization_id): role
            for organization_id, role in principal.organization_roles.items()
        },
        "knowledge_base_roles": {
            f"{organization_id}:{knowledge_base_id}": role
            for (organization_id, knowledge_base_id), role in principal.knowledge_base_roles.items()
        },
    }


@router.post("/logout")
def auth_logout(
    request: Request,
    response: Response,
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_principal)],
) -> dict[str, bool]:
    settings = request.app.state.settings
    response.delete_cookie(
        settings.auth_cookie_name,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )
    response.delete_cookie(settings.csrf_cookie_name, samesite="lax")
    return {"logged_out": True}
