from __future__ import annotations

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request

from enterprise_knowledge_copilot.config import Settings

router = APIRouter(prefix="/api/v1")


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.get("/status")
def get_status(*, settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }
