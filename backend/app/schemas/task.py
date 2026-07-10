from datetime import UTC, datetime

from pydantic import BaseModel, field_serializer


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
    attempts: int
    max_attempts: int
    available_at: datetime
    heartbeat_at: datetime | None
    worker_id: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @field_serializer(
        "created_at",
        "available_at",
        "started_at",
        "finished_at",
        "heartbeat_at",
        when_used="json",
    )
    def serialize_utc_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        timezone_value = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return timezone_value.astimezone(UTC).isoformat()

    model_config = {"from_attributes": True}
