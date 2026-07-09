from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.schemas.tag import TagRead


class AssetRead(BaseModel):
    id: str
    name: str
    stem: str
    extension: str
    asset_type: str
    path: str
    size_bytes: int
    mime_type: str | None
    file_hash: str | None
    thumbnail_path: str | None
    thumbnail_url: str | None
    description: str | None
    author: str | None
    rating: int
    is_favorite: bool
    last_opened_at: datetime | None
    file_created_at: datetime | None
    file_modified_at: datetime | None
    indexed_at: datetime

    model_config = {"from_attributes": True}


class AssetDetail(AssetRead):
    tags: list[TagRead] = Field(default_factory=list)


class AssetUpdate(BaseModel):
    description: str | None = None
    author: str | None = None
    rating: int | None = Field(default=None, ge=0, le=5)
    is_favorite: bool | None = None


class AssetListResponse(BaseModel):
    items: list[AssetRead]
    total: int
    page: int
    page_size: int


class AssetCleanupResponse(BaseModel):
    excluded_removed: int
    missing_removed: int


class DuplicateAssetGroup(BaseModel):
    file_hash: str
    size_bytes: int
    count: int
    items: list[AssetRead]


class DuplicateAssetResponse(BaseModel):
    groups: list[DuplicateAssetGroup]
    total_groups: int
    total_assets: int
    hashed_assets: int
