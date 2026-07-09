from datetime import datetime

from pydantic import BaseModel


class UserRead(BaseModel):
    id: str
    username: str
    email: str | None
    display_name: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
