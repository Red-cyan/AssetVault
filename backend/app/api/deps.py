from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import decode_access_token, hash_password
from backend.app.db.session import get_db
from backend.app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_local_user(db: Session) -> User:
    settings = get_settings()
    if settings.local_user_id:
        user = db.get(User, settings.local_user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ASSETVAULT_LOCAL_USER_ID does not match an existing user",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The configured local workspace user is inactive",
            )
        return user

    local_user = db.scalar(select(User).where(User.username == "local"))
    if local_user is not None:
        if not local_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The local workspace user is inactive",
            )
        return local_user

    users = list(db.scalars(select(User).limit(2)))
    if len(users) == 1:
        if not users[0].is_active:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The only available local workspace user is inactive",
            )
        return users[0]
    if len(users) > 1:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Multiple users exist; set ASSETVAULT_LOCAL_USER_ID to select the local "
                "workspace"
            ),
        )

    user = User(
        username="local",
        display_name="Local Workspace",
        password_hash=hash_password("local-account-password-disabled"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if get_settings().auth_mode == "local":
        return get_local_user(db)
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user
