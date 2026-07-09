from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.app.api.deps import get_current_user
from backend.app.db.session import get_db
from backend.app.models import Asset, AssetTag, Tag, User
from backend.app.schemas.asset import (
    AssetBatchUpdate,
    AssetBatchUpdateResponse,
    AssetCleanupResponse,
    AssetDetail,
    AssetFolderGroup,
    AssetListResponse,
    AssetRead,
    AssetUpdate,
    DuplicateAssetResponse,
    MissingAssetScanResponse,
    TrashSummaryResponse,
)
from backend.app.schemas.tag import AssetTagsUpdate, TagRead
from backend.app.services.asset_scanner import cleanup_excluded_assets, cleanup_missing_assets
from backend.app.services.duplicate_service import find_duplicate_groups, refresh_missing_hashes
from backend.app.services.missing_asset_service import scan_missing_assets

router = APIRouter(prefix="/assets", tags=["assets"])

PRIMARY_ASSET_TYPES = {"model", "motion", "ue"}
SUPPORT_ASSET_TYPES = {"image", "video"}


def path_prefix_filter(directory_path: str):
    normalized = directory_path.rstrip("\\/")
    return or_(
        Asset.path == normalized,
        Asset.path.ilike(f"{normalized}/%"),
        Asset.path.ilike(f"{normalized}\\%"),
    )


def resolve_asset_group(asset: Asset) -> tuple[str, str]:
    asset_path = Path(asset.path)
    folder = asset.folder
    if folder is None:
        group_path = asset_path.parent
        return group_path.name or str(group_path), str(group_path)

    root = Path(folder.path)
    try:
        relative_parts = asset_path.relative_to(root).parts
    except ValueError:
        group_path = asset_path.parent
        return group_path.name or str(group_path), str(group_path)

    if len(relative_parts) <= 1:
        return folder.name, folder.path

    group_path = root / relative_parts[0]
    return group_path.name or str(group_path), str(group_path)


def serialize_asset_detail(asset: Asset) -> AssetDetail:
    data = AssetRead.model_validate(asset).model_dump()
    data["tags"] = [TagRead.model_validate(link.tag) for link in asset.tags]
    return AssetDetail(**data)


def get_owned_active_assets(db: Session, *, user_id: str, asset_ids: list[str]) -> list[Asset]:
    unique_ids = list(dict.fromkeys(asset_ids))
    return list(
        db.scalars(
            select(Asset).where(
                Asset.user_id == user_id,
                Asset.id.in_(unique_ids),
                Asset.is_deleted.is_(False),
            )
        )
    )


def get_or_create_tags(db: Session, *, user_id: str, tag_names: list[str]) -> list[Tag]:
    names = sorted({name.strip() for name in tag_names if name.strip()})
    if not names:
        return []
    existing_tags = list(
        db.scalars(select(Tag).where(Tag.user_id == user_id, Tag.name.in_(names)))
    )
    existing_names = {tag.name for tag in existing_tags}
    created_tags: list[Tag] = []
    for name in names:
        if name in existing_names:
            continue
        tag = Tag(user_id=user_id, name=name)
        db.add(tag)
        created_tags.append(tag)
    db.flush()
    return existing_tags + created_tags


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
    exists_on_disk: bool | None = None,
    scope: Literal["primary", "support", "all"] = "primary",
    directory_path: str | None = None,
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
    elif scope == "primary":
        filters.append(Asset.asset_type.in_(PRIMARY_ASSET_TYPES))
    elif scope == "support":
        filters.append(Asset.asset_type.in_(SUPPORT_ASSET_TYPES))
    if favorite is not None:
        filters.append(Asset.is_favorite == favorite)
    if exists_on_disk is not None:
        filters.append(Asset.exists_on_disk == exists_on_disk)
    if directory_path:
        filters.append(path_prefix_filter(directory_path))
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


@router.get("/folder-groups", response_model=list[AssetFolderGroup])
def list_asset_folder_groups(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AssetFolderGroup]:
    assets = list(
        db.scalars(
            select(Asset)
            .options(selectinload(Asset.folder))
            .where(Asset.user_id == current_user.id, Asset.is_deleted.is_(False))
        )
    )
    groups: dict[str, dict[str, int | str]] = {}
    for asset in assets:
        name, path = resolve_asset_group(asset)
        group = groups.setdefault(
            path,
            {
                "name": name,
                "path": path,
                "total_count": 0,
                "primary_count": 0,
                "support_count": 0,
                "size_bytes": 0,
            },
        )
        group["total_count"] = int(group["total_count"]) + 1
        group["size_bytes"] = int(group["size_bytes"]) + asset.size_bytes
        if asset.asset_type in PRIMARY_ASSET_TYPES:
            group["primary_count"] = int(group["primary_count"]) + 1
        if asset.asset_type in SUPPORT_ASSET_TYPES:
            group["support_count"] = int(group["support_count"]) + 1

    return [
        AssetFolderGroup(**group)
        for group in sorted(
            groups.values(),
            key=lambda item: (-int(item["primary_count"]), str(item["name"]).lower()),
        )
    ]


@router.patch("/batch", response_model=AssetBatchUpdateResponse)
def batch_update_assets(
    payload: AssetBatchUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AssetBatchUpdateResponse:
    assets = get_owned_active_assets(db, user_id=current_user.id, asset_ids=payload.asset_ids)
    if not assets:
        raise HTTPException(status_code=404, detail="No matching assets found")

    updated_count = 0
    tagged_count = 0
    trashed_count = 0

    if payload.is_favorite is not None:
        for asset in assets:
            asset.is_favorite = payload.is_favorite
        updated_count = len(assets)

    tags = get_or_create_tags(db, user_id=current_user.id, tag_names=payload.tag_names)
    if tags:
        asset_ids = [asset.id for asset in assets]
        existing_pairs = {
            (asset_id, tag_id)
            for asset_id, tag_id in db.execute(
                select(AssetTag.asset_id, AssetTag.tag_id).where(AssetTag.asset_id.in_(asset_ids))
            )
        }
        for asset in assets:
            for tag in tags:
                if (asset.id, tag.id) not in existing_pairs:
                    db.add(AssetTag(asset_id=asset.id, tag_id=tag.id))
                    tagged_count += 1

    if payload.move_to_trash:
        now = datetime.utcnow()
        for asset in assets:
            asset.is_deleted = True
            asset.deleted_at = now
        trashed_count = len(assets)
        updated_count = max(updated_count, trashed_count)

    db.commit()
    return AssetBatchUpdateResponse(
        matched_count=len(assets),
        updated_count=updated_count,
        tagged_count=tagged_count,
        trashed_count=trashed_count,
    )


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


@router.post("/missing/scan", response_model=MissingAssetScanResponse)
def scan_missing_assets_endpoint(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MissingAssetScanResponse:
    result = scan_missing_assets(db, user_id=current_user.id)
    return MissingAssetScanResponse(**result)


@router.get("/missing", response_model=AssetListResponse)
def list_missing_assets(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AssetListResponse:
    items = list(
        db.scalars(
            select(Asset)
            .where(
                Asset.user_id == current_user.id,
                Asset.is_deleted.is_(False),
                Asset.exists_on_disk.is_(False),
            )
            .order_by(Asset.missing_since.desc())
        )
    )
    return AssetListResponse(items=items, total=len(items), page=1, page_size=len(items) or 1)


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

    tags = get_or_create_tags(db, user_id=current_user.id, tag_names=payload.tag_names)
    if payload.tag_ids:
        tags.extend(
            db.scalars(
                select(Tag).where(Tag.user_id == current_user.id, Tag.id.in_(payload.tag_ids))
            )
        )

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
