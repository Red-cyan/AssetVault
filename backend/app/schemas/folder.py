from datetime import datetime

from pydantic import BaseModel, Field


class FolderCreate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    path: str


class FolderRead(BaseModel):
    id: str
    name: str
    path: str
    is_active: bool
    last_scanned_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
