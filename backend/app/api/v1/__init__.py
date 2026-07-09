from fastapi import APIRouter

from backend.app.api.v1 import (
    ai,
    assets,
    auth,
    folders,
    projects,
    search,
    settings,
    stats,
    tags,
    tasks,
    trash,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(folders.router)
api_router.include_router(assets.router)
api_router.include_router(ai.router)
api_router.include_router(projects.router)
api_router.include_router(tags.router)
api_router.include_router(search.router)
api_router.include_router(tasks.router)
api_router.include_router(stats.router)
api_router.include_router(settings.router)
api_router.include_router(trash.router)
