from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.security import hash_password, verify_password
from backend.app.db.session import get_db
from backend.app.models import User
from backend.app.schemas.user import PasswordChangeRequest, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserRead)
def update_me(
    payload: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if payload.email is not None:
        existing = db.scalar(
            select(User).where(User.email == payload.email, User.id != current_user.id)
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail="Email already exists")
        current_user.email = payload.email
    if payload.display_name is not None:
        current_user.display_name = payload.display_name
    db.commit()
    db.refresh(current_user)
    return current_user


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
