from datetime import datetime

from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str | None = Field(default=None, max_length=24)


class TagRead(BaseModel):
    id: str
    name: str
    color: str | None
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AssetTagsUpdate(BaseModel):
    tag_names: list[str] = Field(default_factory=list)
    tag_ids: list[str] = Field(default_factory=list)
