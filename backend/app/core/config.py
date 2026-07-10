from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AssetVault"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "change-me-in-production-use-env-for-real-deployments"
    access_token_expire_minutes: int = 60 * 24
    database_url: str = (
        "postgresql+psycopg://assetvault:assetvault@127.0.0.1:5432/assetvault"
    )
    thumbnail_dir: Path = Path("./cache/thumbnails")
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimensions: int = 1024
    embedding_device: str = "cpu"
    embedding_batch_size: int = 16
    model_cache_dir: Path = Path("./cache/models")
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    allowed_origin_regex: str = r"http://(localhost|127\.0\.0\.1):\d+"
    auth_mode: Literal["local", "password"] = "local"
    local_user_id: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ASSETVAULT_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
