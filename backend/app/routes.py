"""REST endpoints: health checks plus one router per feature, mounted under `/api`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .admin import admin_router
from .auth import auth_router
from .chat import chat_router, global_chat_router, messages_router
from .config import settings
from .dashboard import dashboard_router
from .database import get_db
from .groups import groups_router
from .notes import notes_router, subjects_router
from .schemas import HealthResponse

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    """Liveness probe that also verifies the database connection."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return HealthResponse(
        status="ok",
        database="ok",
        environment=settings.environment,
        version=settings.app_version,
    )

router.include_router(auth_router)
router.include_router(subjects_router)
router.include_router(notes_router)
router.include_router(groups_router)
router.include_router(messages_router)
router.include_router(global_chat_router)
router.include_router(chat_router)
router.include_router(dashboard_router)
router.include_router(admin_router)
