from datetime import datetime

from pydantic import BaseModel


class TaskRead(BaseModel):
    id: str
    type: str
    status: str
    progress: int
    total: int
    processed: int
    message: str | None
    error: str | None
    payload: dict | None
    result: dict | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}
