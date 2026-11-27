from __future__ import annotations

import contextvars
import json
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from enterprise_knowledge_copilot.api.v1.router import router
from enterprise_knowledge_copilot.config import Settings
from enterprise_knowledge_copilot.db.session import configure_database, get_session_factory

_REQUEST_ID_CTX: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)
_SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "api-key",
    "token",
    "secret",
    "password",
    "cookie",
    "set-cookie",
}
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _redact_sensitive_data(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_sensitive_data(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_sensitive_data(item) for item in value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key in ("request_id", "method", "path", "status_code"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(_redact_sensitive_data(payload), separators=(",", ":"), default=str)


def _request_id_from_header(header_value: str | None) -> str:
    if header_value and _VALID_REQUEST_ID.fullmatch(header_value):
        return header_value
    return uuid.uuid4().hex


def _default_dependency_checks(settings: Settings) -> dict[str, bool]:
    return {
        "database": bool(settings.database_url),
        "redis": bool(settings.redis_url),
    }


def create_app(settings: Settings | None = None, *, enable_routers: bool = True) -> FastAPI:
    resolved_settings = settings or Settings()
    app = FastAPI(
        title=resolved_settings.app_name,
        version="1.0.0",
        description="API foundation for enterprise knowledge workflows.",
        debug=resolved_settings.debug,
    )
    app.state.settings = resolved_settings
    app.state.dependency_checks = lambda: _default_dependency_checks(resolved_settings)

    if resolved_settings.database_url:
        try:
            configure_database(resolved_settings.database_url)
            app.state.db_session = get_session_factory()
        except Exception:
            app.state.db_session = None

    logger = logging.getLogger("enterprise_knowledge_copilot")
    logger.setLevel(getattr(logging, resolved_settings.log_level.upper(), logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.propagate = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def csrf_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if (
            resolved_settings.auth_mode == "cookie"
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.cookies.get(resolved_settings.auth_cookie_name)
        ):
            cookie = request.cookies.get(resolved_settings.csrf_cookie_name)
            header = request.headers.get(resolved_settings.csrf_header_name)
            if not cookie or not header or cookie != header:
                request_id = getattr(request.state, "request_id", "unknown")
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "csrf_validation_failed",
                            "message": "CSRF validation failed.",
                            "request_id": request_id,
                        }
                    },
                )
        return await call_next(request)

    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming_id = request.headers.get(resolved_settings.request_id_header)
        request_id = _request_id_from_header(incoming_id)
        request.state.request_id = request_id
        token = _REQUEST_ID_CTX.set(request_id)
        try:
            response = await call_next(request)
            response.headers[resolved_settings.request_id_header] = request_id
            return response
        finally:
            _REQUEST_ID_CTX.reset(token)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", _REQUEST_ID_CTX.get() or "unknown")
        logger.warning(
            "http_exception",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "http_error",
                    "message": exc.detail,
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", _REQUEST_ID_CTX.get() or "unknown")
        logger.warning(
            "validation_exception",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 422,
            },
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, _exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", _REQUEST_ID_CTX.get() or "unknown")
        logger.exception(
            "unhandled_exception",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
            },
            exc_info=_exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected error occurred.",
                    "request_id": request_id,
                }
            },
        )

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready() -> JSONResponse:
        dependencies = app.state.dependency_checks()
        ready = all(dependencies.values())
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ok" if ready else "degraded",
                "dependencies": dependencies,
            },
        )

    if enable_routers:
        app.include_router(router)

    return app
