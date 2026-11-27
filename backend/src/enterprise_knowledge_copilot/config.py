from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_assignment=True,
    )

    app_name: str = "Enterprise Knowledge Copilot API"
    environment: str = "local"
    debug: bool = False
    api_prefix: str = "/api/v1"
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
    )
    log_level: str = "INFO"
    request_id_header: str = "X-Request-ID"
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )
    redis_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDIS_URL", "redis_url"),
    )
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "llm_api_key"),
    )
    auth_mode: str = "bearer"
    development_auth_enabled: bool = False
    development_auth_header: str = "X-Development-Subject"
    development_auth_subject: str = "dev|admin"
    development_auth_username: str = "admin"
    development_auth_password: str = "admin"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    auth_cookie_name: str = "ekc_session"
    auth_cookie_secure: bool = True
    csrf_cookie_name: str = "ekc_csrf"
    csrf_header_name: str = "X-CSRF-Token"

    @field_validator("auth_mode")
    @classmethod
    def validate_auth_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"bearer", "cookie"}:
            raise ValueError("auth_mode must be 'bearer' or 'cookie'.")
        return normalized

    @field_validator("auth_cookie_secure")
    @classmethod
    def validate_cookie_security(cls, value: bool, info: Any) -> bool:
        # The complete environment check is in validate_development_auth.
        return value

    @field_validator("database_url", "redis_url")
    @classmethod
    def validate_required_url(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("This setting is required and cannot be blank.")
        return value.strip()

    @model_validator(mode="after")
    def validate_development_auth(self) -> Settings:
        if self.development_auth_enabled:
            if self.environment.strip().lower() in {"production", "prod"}:
                raise ValueError("Development authentication cannot be enabled in production.")
        return self

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            origins = [origin.strip() for origin in value.split(",")]
            return [origin for origin in origins if origin]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        raise TypeError("CORS origins must be a comma-delimited string or list of strings.")
