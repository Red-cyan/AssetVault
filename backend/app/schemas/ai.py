from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.asset import AssetDetail


class AiAnalyzeResponse(BaseModel):
    asset: AssetDetail
    tags: list[str]
    description: str
    source: Literal["openai-compatible", "local-heuristic"]
    model: str | None
    elapsed_ms: int


class AiApplyRequest(BaseModel):
    tags: list[str] = Field(min_length=1, max_length=10)
    description: str = Field(min_length=1, max_length=2000)
    source: Literal["openai-compatible", "local-heuristic"]
