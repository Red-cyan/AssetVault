from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.models import User
from backend.app.schemas.setting import AiConnectionTestResult, SettingsRead, SettingsUpdate
from backend.app.services.settings_service import (
    get_user_settings,
    public_settings,
    update_user_settings,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsRead)
def read_settings(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SettingsRead:
    values = get_user_settings(db, user_id=current_user.id)
    return SettingsRead(**public_settings(values))


@router.patch("", response_model=SettingsRead)
def update_settings(
    payload: SettingsUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SettingsRead:
    updates = payload.model_dump(exclude_unset=True)
    values = update_user_settings(db, user_id=current_user.id, updates=updates)
    return SettingsRead(**public_settings(values))


@router.post("/test-ai", response_model=AiConnectionTestResult)
def test_ai_settings(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AiConnectionTestResult:
    values = get_user_settings(db, user_id=current_user.id)
    if not values.get("ai_api_key"):
        return AiConnectionTestResult(configured=False, message="AI Key 尚未配置。")
    if not values.get("ai_base_url"):
        return AiConnectionTestResult(configured=False, message="AI Base URL 尚未配置。")
    return AiConnectionTestResult(configured=True, message="AI 配置已填写，后续可接入真实调用。")
