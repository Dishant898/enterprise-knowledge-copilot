from __future__ import annotations

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request

from enterprise_knowledge_copilot.api.v1.auth import router as auth_router
from enterprise_knowledge_copilot.api.v1.knowledge_bases import router as knowledge_bases_router
from enterprise_knowledge_copilot.config import Settings

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(knowledge_bases_router)


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.get("/status")
def get_status(*, settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }
