from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.app.api.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.models import Asset, AssetTag, Tag, User
from backend.app.schemas.asset import (
    AssetCleanupResponse,
    AssetDetail,
    AssetListResponse,
    AssetRead,
    AssetUpdate,
    DuplicateAssetResponse,
    TrashSummaryResponse,
)
from backend.app.schemas.tag import AssetTagsUpdate, TagRead
from backend.app.services.asset_scanner import cleanup_excluded_assets, cleanup_missing_assets
from backend.app.services.duplicate_service import find_duplicate_groups, refresh_missing_hashes

router = APIRouter(prefix="/assets", tags=["assets"])


def serialize_asset_detail(asset: Asset) -> AssetDetail:
    data = AssetRead.model_validate(asset).model_dump()
    data["tags"] = [TagRead.model_validate(link.tag) for link in asset.tags]
    return AssetDetail(**data)


@router.get("", response_model=AssetListResponse)
def list_assets(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=60, ge=1, le=200),
    q: str | None = None,
    asset_type: str | None = Query(default=None, alias="type"),
    tag_id: str | None = None,
    favorite: bool | None = None,
    sort_by: Literal[
        "name",
        "size_bytes",
        "file_modified_at",
        "asset_type",
        "last_opened_at",
    ] = "file_modified_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> AssetListResponse:
    stmt = select(Asset).where(Asset.user_id == current_user.id, Asset.is_deleted.is_(False))
    count_stmt = select(func.count(Asset.id)).where(
        Asset.user_id == current_user.id,
        Asset.is_deleted.is_(False),
    )

    filters = []
    if q:
        pattern = f"%{q}%"
        filters.append(
            or_(
                Asset.name.ilike(pattern),
                Asset.path.ilike(pattern),
                Asset.extension.ilike(pattern),
                Asset.author.ilike(pattern),
                Asset.description.ilike(pattern),
            )
        )
    if asset_type:
        filters.append(Asset.asset_type == asset_type)
    if favorite is not None:
        filters.append(Asset.is_favorite == favorite)
    if tag_id:
        stmt = stmt.join(AssetTag, AssetTag.asset_id == Asset.id)
        count_stmt = count_stmt.join(AssetTag, AssetTag.asset_id == Asset.id)
        filters.append(AssetTag.tag_id == tag_id)

    for item in filters:
        stmt = stmt.where(item)
        count_stmt = count_stmt.where(item)

    sort_column = getattr(Asset, sort_by)
    stmt = stmt.order_by(desc(sort_column) if sort_order == "desc" else asc(sort_column))
    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return AssetListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/cleanup", response_model=AssetCleanupResponse)
def cleanup_assets(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AssetCleanupResponse:
    excluded_removed = cleanup_excluded_assets(db, user_id=current_user.id)
    missing_removed = cleanup_missing_assets(db, user_id=current_user.id)
    return AssetCleanupResponse(
        excluded_removed=excluded_removed,
        missing_removed=missing_removed,
    )


@router.get("/duplicates", response_model=DuplicateAssetResponse)
def list_duplicate_assets(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DuplicateAssetResponse:
    refresh_missing_hashes(db, user_id=current_user.id)
    groups, hashed_assets = find_duplicate_groups(db, user_id=current_user.id)
    total_assets = sum(group["count"] for group in groups)
    return DuplicateAssetResponse(
        groups=groups,
        total_groups=len(groups),
        total_assets=total_assets,
        hashed_assets=hashed_assets,
    )


@router.get("/{asset_id}", response_model=AssetDetail)
def get_asset(
    asset_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AssetDetail:
    asset = db.scalar(
        select(Asset)
        .options(selectinload(Asset.tags).selectinload(AssetTag.tag))
        .where(
            Asset.id == asset_id,
            Asset.user_id == current_user.id,
            Asset.is_deleted.is_(False),
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return serialize_asset_detail(asset)


@router.patch("/{asset_id}", response_model=AssetRead)
def update_asset(
    asset_id: str,
    payload: AssetUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.user_id != current_user.id or asset.is_deleted:
        raise HTTPException(status_code=404, detail="Asset not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(asset, field, value)
    db.commit()
    db.refresh(asset)
    return asset


@router.post("/{asset_id}/open", response_model=AssetRead)
def mark_opened(
    asset_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.user_id != current_user.id or asset.is_deleted:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset.last_opened_at = datetime.utcnow()
    db.commit()
    db.refresh(asset)
    return asset


@router.post("/{asset_id}/tags", response_model=AssetDetail)
def update_asset_tags(
    asset_id: str,
    payload: AssetTagsUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AssetDetail:
    asset = db.scalar(
        select(Asset)
        .options(selectinload(Asset.tags).selectinload(AssetTag.tag))
        .where(
            Asset.id == asset_id,
            Asset.user_id == current_user.id,
            Asset.is_deleted.is_(False),
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    tags: list[Tag] = []
    if payload.tag_ids:
        tags.extend(
            db.scalars(
                select(Tag).where(Tag.user_id == current_user.id, Tag.id.in_(payload.tag_ids))
            )
        )
    for name in {item.strip() for item in payload.tag_names if item.strip()}:
        tag = db.scalar(select(Tag).where(Tag.user_id == current_user.id, Tag.name == name))
        if tag is None:
            tag = Tag(user_id=current_user.id, name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)

    existing_tag_ids = {link.tag_id for link in asset.tags}
    for tag in tags:
        if tag.id not in existing_tag_ids:
            db.add(AssetTag(asset_id=asset.id, tag_id=tag.id))
    db.commit()
    db.refresh(asset)
    asset = db.scalar(
        select(Asset)
        .options(selectinload(Asset.tags).selectinload(AssetTag.tag))
        .where(Asset.id == asset_id)
    )
    return serialize_asset_detail(asset)


@router.delete("/{asset_id}", response_model=TrashSummaryResponse)
def move_asset_to_trash(
    asset_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TrashSummaryResponse:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.user_id != current_user.id or asset.is_deleted:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset.is_deleted = True
    asset.deleted_at = datetime.utcnow()
    db.commit()
    deleted_count = db.scalar(
        select(func.count(Asset.id)).where(
            Asset.user_id == current_user.id,
            Asset.is_deleted.is_(True),
        )
    ) or 0
    return TrashSummaryResponse(deleted_count=deleted_count)
