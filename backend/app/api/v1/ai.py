from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.api.deps import get_current_user
from backend.app.api.v1.assets import serialize_asset_detail
from backend.app.db.session import get_db
from backend.app.models import Asset, AssetTag, User
from backend.app.schemas.ai import AiAnalyzeResponse, AiApplyRequest
from backend.app.services.ai_analysis_service import (
    AiAnalysisError,
    AnalysisResult,
    apply_analysis_result,
    generate_ai_analysis,
)

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

    try:
        result = generate_ai_analysis(db, asset=asset)
    except AiAnalysisError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    return AiAnalyzeResponse(
        asset=serialize_asset_detail(asset),
        tags=result.tags,
        description=result.description,
        source=result.source,
        model=result.model,
        elapsed_ms=result.elapsed_ms,
    )


@router.post("/assets/{asset_id}/apply", response_model=AiAnalyzeResponse)
def apply_asset_analysis(
    asset_id: str,
    payload: AiApplyRequest,
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

    result = AnalysisResult(
        tags=payload.tags,
        description=payload.description,
        source=payload.source,
    )
    apply_analysis_result(db, asset=asset, result=result)
    asset = db.scalar(
        select(Asset)
        .options(selectinload(Asset.tags).selectinload(AssetTag.tag))
        .where(Asset.id == asset_id, Asset.user_id == current_user.id)
    )
    return AiAnalyzeResponse(
        asset=serialize_asset_detail(asset),
        tags=result.tags,
        description=result.description,
        source=result.source,
        model=None,
        elapsed_ms=0,
    )
