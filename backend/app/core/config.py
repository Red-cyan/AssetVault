from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AssetVault"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "change-me-in-production-use-env-for-real-deployments"
    access_token_expire_minutes: int = 60 * 24
    database_url: str = "sqlite:///./assetvault.db"
    thumbnail_dir: Path = Path("./cache/thumbnails")
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    allowed_origin_regex: str = r"http://(localhost|127\.0\.0\.1):\d+"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ASSETVAULT_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
