from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.api.deps import get_current_user
from backend.app.api.v1.assets import serialize_asset_detail
from backend.app.db.session import get_db
from backend.app.models import Asset, AssetTag, User
from backend.app.schemas.ai import AiAnalyzeResponse
from backend.app.services.ai_analysis_service import apply_ai_analysis

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/assets/{asset_id}/analyze", response_model=AiAnalyzeResponse)
def analyze_asset(
    asset_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AiAnalyzeResponse:
    asset = db.scalar(
        select(Asset)
        .options(selectinload(Asset.tags).selectinload(AssetTag.tag))
        .where(Asset.id == asset_id, Asset.user_id == current_user.id)
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    tags, description = apply_ai_analysis(db, asset=asset)
    asset = db.scalar(
        select(Asset)
        .options(selectinload(Asset.tags).selectinload(AssetTag.tag))
        .where(Asset.id == asset_id, Asset.user_id == current_user.id)
    )
    return AiAnalyzeResponse(
        asset=serialize_asset_detail(asset),
        tags=tags,
        description=description,
        source="local-heuristic",
    )
