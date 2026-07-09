from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.api.v1.assets import list_assets
from backend.app.db.session import get_db
from backend.app.models import User
from backend.app.schemas.asset import AssetListResponse

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
