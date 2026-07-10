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
    mode: str


class EmbeddingReindexRequest(BaseModel):
    force: bool = False


class EmbeddingIndexStatus(BaseModel):
    indexed_assets: int
    total_assets: int
    model: str
    dimensions: int


class SimilarAssetsResponse(BaseModel):
    source_asset_id: str
    items: list[AssetRead]
    total: int
    model: str
