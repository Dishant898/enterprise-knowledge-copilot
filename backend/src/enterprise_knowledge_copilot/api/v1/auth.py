from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from enterprise_knowledge_copilot.auth import AuthenticatedPrincipal, require_principal

router = APIRouter(prefix="/auth", tags=["authentication"])


class DevelopmentLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)


@router.post("/login/development")
def development_login(
    request: Request,
    response: Response,
    payload: DevelopmentLoginRequest,
) -> dict[str, str]:
    settings = request.app.state.settings
    if not settings.development_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Development login is not available.",
        )
    if (
        payload.username != settings.development_auth_username
        or payload.password != settings.development_auth_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    response.set_cookie(
        settings.auth_cookie_name,
        value=f"development:{settings.development_auth_subject}",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=60 * 60 * 8,
    )
    return {"subject": settings.development_auth_subject}


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
