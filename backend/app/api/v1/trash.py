from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.models import Asset, AssetTag, User
from backend.app.schemas.asset import AssetListResponse, AssetRead, TrashSummaryResponse

router = APIRouter(prefix="/trash", tags=["trash"])


@router.get("/assets", response_model=AssetListResponse)
def list_trash_assets(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AssetListResponse:
    stmt = (
        select(Asset)
        .where(Asset.user_id == current_user.id, Asset.is_deleted.is_(True))
        .order_by(Asset.deleted_at.desc())
    )
    items = list(db.scalars(stmt))
    total = len(items)
    return AssetListResponse(items=items, total=total, page=1, page_size=total or 1)


@router.post("/assets/{asset_id}/restore", response_model=AssetRead)
def restore_asset(
    asset_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.user_id != current_user.id or not asset.is_deleted:
        raise HTTPException(status_code=404, detail="Trash asset not found")
    asset.is_deleted = False
    asset.deleted_at = None
    db.commit()
    db.refresh(asset)
    return asset


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def purge_asset(
    asset_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.user_id != current_user.id or not asset.is_deleted:
        raise HTTPException(status_code=404, detail="Trash asset not found")
    db.execute(delete(AssetTag).where(AssetTag.asset_id == asset_id))
    db.delete(asset)
    db.commit()


@router.delete("/assets", response_model=TrashSummaryResponse)
def empty_trash(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TrashSummaryResponse:
    ids = list(
        db.scalars(
            select(Asset.id).where(
                Asset.user_id == current_user.id,
                Asset.is_deleted.is_(True),
            )
        )
    )
    if not ids:
        return TrashSummaryResponse(deleted_count=0, purged_count=0)
    db.execute(delete(AssetTag).where(AssetTag.asset_id.in_(ids)))
    db.execute(delete(Asset).where(Asset.id.in_(ids)))
    db.commit()
    remaining = db.scalar(
        select(func.count(Asset.id)).where(
            Asset.user_id == current_user.id,
            Asset.is_deleted.is_(True),
        )
    ) or 0
    return TrashSummaryResponse(deleted_count=remaining, purged_count=len(ids))
