from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app import models  # noqa: F401
from backend.app.api.v1 import (
    ai,
    assets,
    auth,
    folders,
    projects,
    search,
    stats,
    tags,
    tasks,
    trash,
    users,
)
from backend.app.api.v1 import settings as settings_api
from backend.app.core.config import get_settings
from backend.app.db.base import Base
from backend.app.db.session import engine
from backend.app.services.schema_service import ensure_runtime_schema


def create_app() -> FastAPI:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)

    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_origin_regex=settings.allowed_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router, prefix=settings.api_v1_prefix)
    app.include_router(users.router, prefix=settings.api_v1_prefix)
    app.include_router(folders.router, prefix=settings.api_v1_prefix)
    app.include_router(assets.router, prefix=settings.api_v1_prefix)
    app.include_router(ai.router, prefix=settings.api_v1_prefix)
    app.include_router(projects.router, prefix=settings.api_v1_prefix)
    app.include_router(tags.router, prefix=settings.api_v1_prefix)
    app.include_router(search.router, prefix=settings.api_v1_prefix)
    app.include_router(tasks.router, prefix=settings.api_v1_prefix)
    app.include_router(stats.router, prefix=settings.api_v1_prefix)
    app.include_router(settings_api.router, prefix=settings.api_v1_prefix)
    app.include_router(trash.router, prefix=settings.api_v1_prefix)
    settings.thumbnail_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/thumbnails", StaticFiles(directory=settings.thumbnail_dir), name="thumbnails")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
