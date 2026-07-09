from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.models import Asset, Folder, Tag, User
from backend.app.schemas.stats import ExtensionStat, StatsOverview, TypeStat

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview", response_model=StatsOverview)
def overview(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StatsOverview:
    total_assets = db.scalar(
        select(func.count(Asset.id)).where(
            Asset.user_id == current_user.id,
            Asset.is_deleted.is_(False),
        )
    ) or 0
    total_size_bytes = db.scalar(
        select(func.coalesce(func.sum(Asset.size_bytes), 0)).where(
            Asset.user_id == current_user.id,
            Asset.is_deleted.is_(False),
        )
    ) or 0
    favorite_count = db.scalar(
        select(func.count(Asset.id)).where(
            Asset.user_id == current_user.id,
            Asset.is_favorite.is_(True),
            Asset.is_deleted.is_(False),
        )
    ) or 0
    tag_count = db.scalar(select(func.count(Tag.id)).where(Tag.user_id == current_user.id)) or 0
    folder_count = db.scalar(
        select(func.count(Folder.id)).where(Folder.user_id == current_user.id)
    ) or 0
    recent_since = datetime.utcnow() - timedelta(days=7)
    recent_assets_7d = db.scalar(
        select(func.count(Asset.id)).where(
            Asset.user_id == current_user.id,
            Asset.indexed_at >= recent_since,
            Asset.is_deleted.is_(False),
        )
    ) or 0

    type_rows = db.execute(
        select(
            Asset.asset_type,
            func.count(Asset.id),
            func.coalesce(func.sum(Asset.size_bytes), 0),
        )
        .where(Asset.user_id == current_user.id, Asset.is_deleted.is_(False))
        .group_by(Asset.asset_type)
        .order_by(func.count(Asset.id).desc())
    )
    extension_rows = db.execute(
        select(Asset.extension, func.count(Asset.id))
        .where(Asset.user_id == current_user.id, Asset.is_deleted.is_(False))
        .group_by(Asset.extension)
        .order_by(func.count(Asset.id).desc())
        .limit(12)
    )

    return StatsOverview(
        total_assets=total_assets,
        total_size_bytes=total_size_bytes,
        favorite_count=favorite_count,
        tag_count=tag_count,
        folder_count=folder_count,
        recent_assets_7d=recent_assets_7d,
        type_stats=[
            TypeStat(asset_type=asset_type, count=count, size_bytes=size_bytes)
            for asset_type, count, size_bytes in type_rows
        ],
        top_extensions=[
            ExtensionStat(extension=extension or "unknown", count=count)
            for extension, count in extension_rows
        ],
    )
