from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.api.v1.assets import list_assets
from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal, get_db
from backend.app.models import Asset, AssetEmbedding, Task, User
from backend.app.schemas.asset import AssetListResponse
from backend.app.schemas.search import (
    EmbeddingIndexStatus,
    EmbeddingReindexRequest,
    NaturalLanguageSearchRequest,
    NaturalLanguageSearchResponse,
    SimilarAssetsResponse,
)
from backend.app.schemas.task import TaskRead
from backend.app.services.embedding_service import EmbeddingModelError, index_user_assets
from backend.app.services.search_service import find_similar_assets, natural_language_search

router = APIRouter(prefix="/search", tags=["search"])


def run_embedding_task(task_id: str, user_id: str, force: bool) -> None:
    db = SessionLocal()
    try:
        index_user_assets(db, task_id=task_id, user_id=user_id, force=force)
    finally:
        db.close()


def create_embedding_task(db: Session, *, user_id: str, force: bool) -> Task:
    active_task = db.scalar(
        select(Task).where(
            Task.user_id == user_id,
            Task.type == "embedding",
            Task.status.in_(("pending", "running")),
        )
    )
    if active_task is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Embedding task already active: {active_task.id}",
        )
    task = Task(
        user_id=user_id,
        type="embedding",
        status="pending",
        payload={"force": force, "model": get_settings().embedding_model},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("", response_model=AssetListResponse)
def search_assets(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query(min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=60, ge=1, le=200),
) -> AssetListResponse:
    return list_assets(db=db, current_user=current_user, page=page, page_size=page_size, q=q)


@router.post("/natural-language", response_model=NaturalLanguageSearchResponse)
def search_natural_language(
    payload: NaturalLanguageSearchRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NaturalLanguageSearchResponse:
    try:
        items, total, keywords, mode = natural_language_search(
            db,
            user_id=current_user.id,
            query=payload.query,
            limit=payload.limit,
        )
    except EmbeddingModelError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    return NaturalLanguageSearchResponse(
        items=items,
        total=total,
        query=payload.query,
        interpreted_keywords=keywords,
        mode=mode,
    )


@router.get("/embeddings/status", response_model=EmbeddingIndexStatus)
def embedding_index_status(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> EmbeddingIndexStatus:
    settings = get_settings()
    indexed_assets = db.scalar(
        select(func.count(AssetEmbedding.asset_id)).where(
            AssetEmbedding.user_id == current_user.id,
            AssetEmbedding.model == settings.embedding_model,
        )
    ) or 0
    total_assets = db.scalar(
        select(func.count(Asset.id)).where(
            Asset.user_id == current_user.id,
            Asset.is_deleted.is_(False),
        )
    ) or 0
    eligible_assets = db.scalar(
        select(func.count(Asset.id)).where(
            Asset.user_id == current_user.id,
            Asset.is_deleted.is_(False),
            or_(
                and_(Asset.description.is_not(None), Asset.description != ""),
                and_(Asset.author.is_not(None), Asset.author != ""),
                Asset.semantic_eligible.is_(True),
                Asset.tags.any(),
            ),
        )
    ) or 0
    return EmbeddingIndexStatus(
        indexed_assets=indexed_assets,
        eligible_assets=eligible_assets,
        total_assets=total_assets,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
    )


@router.post(
    "/embeddings/reindex",
    response_model=TaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def reindex_embeddings(
    payload: EmbeddingReindexRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Task:
    task = create_embedding_task(db, user_id=current_user.id, force=payload.force)
    background_tasks.add_task(run_embedding_task, task.id, current_user.id, payload.force)
    return task


@router.get("/similar/{asset_id}", response_model=SimilarAssetsResponse)
def similar_assets(
    asset_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=12, ge=1, le=50),
) -> SimilarAssetsResponse:
    items = find_similar_assets(
        db,
        user_id=current_user.id,
        asset_id=asset_id,
        limit=limit,
    )
    if items is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Asset has no current embedding; rebuild the semantic index first",
        )
    return SimilarAssetsResponse(
        source_asset_id=asset_id,
        items=items,
        total=len(items),
        model=get_settings().embedding_model,
    )
