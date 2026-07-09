from pydantic import BaseModel

from backend.app.schemas.asset import AssetDetail


class AiAnalyzeResponse(BaseModel):
    asset: AssetDetail
    tags: list[str]
    description: str
    source: str
