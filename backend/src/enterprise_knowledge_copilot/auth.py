from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from enterprise_knowledge_copilot.config import Settings
from enterprise_knowledge_copilot.db.models import (
    KnowledgeBaseMembership,
    OrganizationMembership,
    User,
)


class AuthenticationError(Exception):
    pass


class ExpiredAuthenticationError(AuthenticationError):
    pass


class InvalidAuthenticationError(AuthenticationError):
    pass


class AuthorizationError(Exception):
    pass


@dataclass(frozen=True)
class IdentityClaims:
    subject: str
    expires_at: datetime | None = None
    issuer: str | None = None
    audience: str | tuple[str, ...] | None = None


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    subject: str
    user_id: UUID | None = None
    organization_roles: Mapping[UUID, str] = field(default_factory=dict)
    knowledge_base_roles: Mapping[tuple[UUID, UUID], str] = field(default_factory=dict)

    @property
    def organizations(self) -> Mapping[UUID, str]:
        return self.organization_roles


class IdentityProvider(Protocol):
    def validate(self, credential: str) -> IdentityClaims:
        ...


class OIDCIdentityProvider:
    """OIDC-compatible provider boundary.

    Production deployments supply issuer/audience and an identity-validation callback
    through application state. This adapter deliberately does not accept or trust
    organization, user ID, or role claims.
    """

    def __init__(
        self,
        *,
        issuer: str | None = None,
        audience: str | None = None,
        jwks_url: str | None = None,
        validator: Callable[[str], Mapping[str, Any]] | None = None,
    ) -> None:
        self.issuer = issuer
        self.audience = audience
        self.jwks_url = jwks_url
        self._validator = validator

    def validate(self, credential: str) -> IdentityClaims:
        if not credential or not credential.strip():
            raise InvalidAuthenticationError("Missing credentials.")
        if self._validator is None:
            raise InvalidAuthenticationError("OIDC validation is not configured.")
        try:
            payload = self._validator(credential)
            subject = payload.get("sub")
            if not isinstance(subject, str) or not subject.strip():
                raise InvalidAuthenticationError("Identity subject is missing.")
            expires_at: datetime | None = None
            exp = payload.get("exp")
            if exp is not None:
                expires_at = datetime.fromtimestamp(float(exp), tz=UTC)
            if expires_at is not None and expires_at <= datetime.now(tz=UTC):
                raise ExpiredAuthenticationError("Authentication has expired.")
            return IdentityClaims(
                subject=subject,
                expires_at=expires_at,
                issuer=str(payload["iss"]) if isinstance(payload.get("iss"), str) else self.issuer,
                audience=self.audience,
            )
        except (AuthenticationError, InvalidAuthenticationError):
            raise
        except (TypeError, ValueError, OverflowError) as exc:
            raise InvalidAuthenticationError("Malformed authentication credentials.") from exc


class DevelopmentIdentityAdapter:
    def __init__(
        self,
        *,
        enabled: bool = False,
        environment: str = "local",
        header_name: str = "X-Development-Subject",
    ) -> None:
        if enabled and environment.strip().lower() in {"production", "prod"}:
            raise RuntimeError("Development authentication cannot be enabled in production.")
        self.enabled = enabled
        self.environment = environment
        self.header_name = header_name

    def validate_request(self, request: Request) -> IdentityClaims:
        if not self.enabled:
            raise InvalidAuthenticationError("Development authentication is disabled.")
        subject = request.headers.get(self.header_name)
        if not subject:
            subject = request.headers.get("X-Development-User")
        if not subject:
            subject = request.headers.get("X-Dev-User")
        if not subject:
            cookie = request.cookies.get("ekc_session")
            if cookie and cookie.startswith("development:"):
                subject = cookie.removeprefix("development:")
        if not subject:
            raise InvalidAuthenticationError("Development identity header is missing.")
        return IdentityClaims(subject=subject.strip())

    def validate(self, credential: str) -> IdentityClaims:
        if not self.enabled:
            raise InvalidAuthenticationError("Development authentication is disabled.")
        if not credential or not credential.strip():
            raise InvalidAuthenticationError("Development identity is missing.")
        return IdentityClaims(subject=credential.strip())


DevelopmentIdentityProvider = DevelopmentIdentityAdapter


def resolve_principal(session: Session, claims: IdentityClaims) -> AuthenticatedPrincipal:
    user = session.scalar(
        select(User).where(User.identity_provider_subject == claims.subject)
    )
    if user is None:
        raise AuthenticationError("Authenticated identity has no application user.")

    organization_roles = {
        membership.organization_id: membership.role
        for membership in session.scalars(
            select(OrganizationMembership).where(OrganizationMembership.user_id == user.id)
        )
    }
    knowledge_base_roles = {
        (membership.organization_id, membership.knowledge_base_id): membership.role
        for membership in session.scalars(
            select(KnowledgeBaseMembership).where(KnowledgeBaseMembership.user_id == user.id)
        )
    }
    return AuthenticatedPrincipal(
        subject=claims.subject,
        user_id=user.id,
        organization_roles=organization_roles,
        knowledge_base_roles=knowledge_base_roles,
    )


def get_db_session(request: Request) -> Session:
    session = getattr(request.app.state, "db_session", None)
    if session is None:
        raise RuntimeError("Database session is not configured.")
    return session


def _extract_credential(request: Request, settings: Settings) -> str:
    if settings.auth_mode == "cookie":
        cookie = request.cookies.get(settings.auth_cookie_name)
        if cookie:
            return cookie
    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, _, credential = authorization.partition(" ")
        if scheme.lower() == "bearer" and credential.strip():
            return credential.strip()
    raise InvalidAuthenticationError("Missing authentication credentials.")


def get_current_principal(
    request: Request,
    session: Session | None = None,
) -> AuthenticatedPrincipal:
    settings: Settings = request.app.state.settings

    try:
        identity_provider = getattr(request.app.state, "identity_provider", None)
        if identity_provider is None:
            if settings.development_auth_enabled:
                identity_provider = DevelopmentIdentityAdapter(
                    enabled=True,
                    environment=settings.environment,
                    header_name=settings.development_auth_header,
                )
            else:
                identity_provider = OIDCIdentityProvider(
                    issuer=settings.oidc_issuer,
                    audience=settings.oidc_audience,
                    jwks_url=settings.oidc_jwks_url,
                )

        if isinstance(identity_provider, DevelopmentIdentityAdapter):
            claims = identity_provider.validate_request(request)
        else:
            credential = _extract_credential(request, settings)
            claims = identity_provider.validate(credential)

        if session is None:
            session = getattr(request.app.state, "db_session", None)
        if callable(session):
            session = session()
        if session is None:
            raise AuthenticationError("Authenticated principal could not be resolved.")
        if not isinstance(session, Session):
            raise AuthenticationError("Authenticated principal could not be resolved.")
        return resolve_principal(session, claims)
    except ExpiredAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication has expired.",
        ) from exc
    except (InvalidAuthenticationError, AuthenticationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        ) from exc


def require_principal(request: Request) -> AuthenticatedPrincipal:
    return get_current_principal(request)


PrincipalDependency = Depends(require_principal)
OIDCIdentityProviderInterface = IdentityProvider
OIDCProvider = OIDCIdentityProvider
AuthenticatedIdentity = AuthenticatedPrincipal


def require_organization_role(*allowed_roles: str) -> Callable[[Request], AuthenticatedPrincipal]:
    allowed = frozenset(allowed_roles)

    def dependency(request: Request, organization_id: UUID | None = None) -> AuthenticatedPrincipal:
        principal = require_principal(request)
        if organization_id is None:
            organization_id = getattr(request.state, "organization_id", None)
        if organization_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
        if principal.organization_roles.get(organization_id) not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
        return principal

    return dependency


def require_knowledge_base_role(*allowed_roles: str) -> Callable[..., AuthenticatedPrincipal]:
    allowed = frozenset(allowed_roles)

    def dependency(
        request: Request,
        knowledge_base_id: UUID | None = None,
    ) -> AuthenticatedPrincipal:
        principal = require_principal(request)
        if knowledge_base_id is None:
            knowledge_base_id = getattr(request.state, "knowledge_base_id", None)
        if knowledge_base_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
        organization_id = getattr(request.state, "organization_id", None)
        for (org_id, kb_id), role in principal.knowledge_base_roles.items():
            if kb_id == knowledge_base_id and (
                organization_id is None or org_id == organization_id
            ):
                if role in allowed:
                    return principal
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    return dependency


def has_organization_role(
    principal: AuthenticatedPrincipal,
    organization_id: UUID,
    *roles: str,
) -> bool:
    return principal.organization_roles.get(organization_id) in frozenset(roles)


def has_knowledge_base_role(
    principal: AuthenticatedPrincipal,
    organization_id: UUID,
    knowledge_base_id: UUID,
    *roles: str,
) -> bool:
    return (
        principal.knowledge_base_roles.get((organization_id, knowledge_base_id))
        in frozenset(roles)
    )


def validate_csrf(request: Request) -> None:
    settings: Settings = request.app.state.settings
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie = request.cookies.get(settings.csrf_cookie_name)
    header = request.headers.get(settings.csrf_header_name)
    if not cookie or not header or cookie != header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed.")


def require_csrf(request: Request) -> None:
    validate_csrf(request)
