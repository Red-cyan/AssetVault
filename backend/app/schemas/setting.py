from datetime import datetime

from pydantic import BaseModel, Field


class SettingsRead(BaseModel):
    cache_dir: str
    theme: str
    ai_base_url: str
    ai_api_key_configured: bool
    ai_chat_model: str
    ai_embedding_model: str
    thumbnail_quality: int


class SettingsUpdate(BaseModel):
    cache_dir: str | None = None
    theme: str | None = None
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_chat_model: str | None = None
    ai_embedding_model: str | None = None
    thumbnail_quality: int | None = Field(default=None, ge=40, le=95)


class AiConnectionTestResult(BaseModel):
    configured: bool
    message: str


class DatabaseBackupResult(BaseModel):
    path: str
    size_bytes: int
    created_at: datetime
