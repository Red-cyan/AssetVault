from pydantic import BaseModel


class TypeStat(BaseModel):
    asset_type: str
    count: int
    size_bytes: int


class ExtensionStat(BaseModel):
    extension: str
    count: int


class StatsOverview(BaseModel):
    total_assets: int
    total_size_bytes: int
    favorite_count: int
    tag_count: int
    folder_count: int
    recent_assets_7d: int
    type_stats: list[TypeStat]
    top_extensions: list[ExtensionStat]
