from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.schemas.asset import AssetRead


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    cover_asset_id: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    cover_asset_id: str | None = None


class ProjectRead(BaseModel):
    id: str
    name: str
    description: str | None
    cover_asset_id: str | None
    created_at: datetime
    updated_at: datetime
    asset_count: int = 0

    model_config = {"from_attributes": True}


class ProjectAssetAdd(BaseModel):
    asset_id: str
    role: str = Field(default="other", max_length=40)


class ProjectAssetRead(BaseModel):
    role: str
    created_at: datetime
    asset: AssetRead


class ProjectDetail(ProjectRead):
    assets: list[ProjectAssetRead] = Field(default_factory=list)
