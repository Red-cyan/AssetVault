from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.core.config import get_settings

router = APIRouter(tags=["runtime"])


class RuntimeInfo(BaseModel):
    auth_mode: Literal["local", "password"]
    authentication_required: bool


@router.get("/runtime", response_model=RuntimeInfo)
def runtime_info() -> RuntimeInfo:
    auth_mode = get_settings().auth_mode
    return RuntimeInfo(
        auth_mode=auth_mode,
        authentication_required=auth_mode == "password",
    )
