from pydantic import BaseModel, Field

from backend.app.schemas.asset import AssetRead


class NaturalLanguageSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=60, ge=1, le=100)


class NaturalLanguageSearchResponse(BaseModel):
    items: list[AssetRead]
    total: int
    query: str
    interpreted_keywords: list[str]
    mode: str = "local-semantic"
