from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.api.v1.assets import list_assets
from backend.app.db.session import get_db
from backend.app.models import User
from backend.app.schemas.asset import AssetListResponse
from backend.app.schemas.search import (
    NaturalLanguageSearchRequest,
    NaturalLanguageSearchResponse,
)
from backend.app.services.search_service import natural_language_search

router = APIRouter(prefix="/search", tags=["search"])


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
    items, total, keywords = natural_language_search(
        db,
        user_id=current_user.id,
        query=payload.query,
        limit=payload.limit,
    )
    return NaturalLanguageSearchResponse(
        items=items,
        total=total,
        query=payload.query,
        interpreted_keywords=keywords,
    )
