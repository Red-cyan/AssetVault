from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import get_settings
from backend.app.models import Asset, AssetEmbedding, AssetTag
from backend.app.services.embedding_service import encode_texts


@dataclass(frozen=True)
class InterpretedQuery:
    keywords: list[str]
    asset_types: list[str]


QUERY_SYNONYMS = {
    "演唱会": ["演唱会", "concert", "stage", "舞台", "演出"],
    "舞台": ["stage", "舞台", "演出"],
    "人物": ["character", "girl", "人物", "角色", "少女"],
    "角色": ["character", "人物", "角色"],
    "少女": ["girl", "少女", "人物"],
    "动作": ["motion", "dance", "vmd", "动作", "舞蹈"],
    "舞蹈": ["dance", "motion", "动作", "舞蹈"],
    "镜头": ["camera", "镜头"],
    "模型": ["model", "pmx", "fbx", "glb", "blend", "模型"],
    "视频": ["video", "mp4", "webm", "视频"],
    "贴图": ["texture", "png", "jpg", "贴图"],
    "音乐": ["music", "bgm", "音乐"],
    "道路": ["road", "道路", "场景"],
    "载具": ["vehicle", "car", "载具"],
    "hdr": ["hdr", "环境光"],
}

TYPE_HINTS = {
    "图片": "image",
    "图": "image",
    "视频": "video",
    "模型": "model",
    "pmx": "model",
    "fbx": "model",
    "glb": "model",
    "动作": "motion",
    "vmd": "motion",
    "ue": "ue",
    "uasset": "ue",
}


def interpret_query(query: str) -> InterpretedQuery:
    normalized = query.lower()
    keywords: list[str] = []
    asset_types: list[str] = []

    for trigger, expansions in QUERY_SYNONYMS.items():
        if trigger.lower() in normalized:
            keywords.extend(expansions)

    for trigger, asset_type in TYPE_HINTS.items():
        if trigger.lower() in normalized:
            asset_types.append(asset_type)

    for token in normalized.replace("，", " ").replace(",", " ").split():
        if len(token) >= 2:
            keywords.append(token)

    if not keywords:
        keywords.append(normalized)

    return InterpretedQuery(
        keywords=deduplicate(keywords)[:16],
        asset_types=deduplicate(asset_types),
    )


def deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = item.strip()
        if not value or value.lower() in seen:
            continue
        seen.add(value.lower())
        result.append(value)
    return result


def score_asset(asset: Asset, keywords: list[str], asset_types: list[str]) -> int:
    haystack = " ".join(
        [
            asset.name or "",
            asset.path or "",
            asset.description or "",
            asset.author or "",
            asset.extension or "",
            asset.asset_type or "",
            " ".join(link.tag.name for link in asset.tags if link.tag),
        ]
    ).lower()
    score = 0
    for keyword in keywords:
        if keyword.lower() in haystack:
            score += 8
    if asset.asset_type in asset_types:
        score += 6
    if asset.is_favorite:
        score += 2
    if asset.rating:
        score += asset.rating
    return score


def natural_language_search(
    db: Session,
    *,
    user_id: str,
    query: str,
    limit: int,
) -> tuple[list[Asset], int, list[str], str]:
    interpreted = interpret_query(query)
    assets = list(
        db.scalars(
        select(Asset)
        .options(selectinload(Asset.tags).selectinload(AssetTag.tag))
        .where(Asset.user_id == user_id, Asset.is_deleted.is_(False))
        ).unique()
    )

    keyword_scored = [
        (asset, score_asset(asset, interpreted.keywords, interpreted.asset_types))
        for asset in assets
    ]
    keyword_scored = [(asset, score) for asset, score in keyword_scored if score > 0]
    keyword_scored.sort(
        key=lambda item: (
            item[1],
            item[0].file_modified_at or item[0].indexed_at,
        ),
        reverse=True,
    )
    settings = get_settings()
    embedding_count = db.scalar(
        select(func.count(AssetEmbedding.asset_id)).where(
            AssetEmbedding.user_id == user_id,
            AssetEmbedding.model == settings.embedding_model,
        )
    ) or 0
    if embedding_count == 0:
        items = [asset for asset, _score in keyword_scored[:limit]]
        return items, len(keyword_scored), interpreted.keywords, "keyword"

    query_vector = encode_texts([query])[0]
    distance = AssetEmbedding.embedding.cosine_distance(query_vector)
    vector_rows = list(
        db.execute(
            select(AssetEmbedding.asset_id, distance.label("distance"))
            .where(
                AssetEmbedding.user_id == user_id,
                AssetEmbedding.model == settings.embedding_model,
            )
            .order_by(distance)
            .limit(max(limit * 4, 100))
        )
    )

    keyword_ranks = {asset.id: rank for rank, (asset, _score) in enumerate(keyword_scored, 1)}
    vector_ranks = {asset_id: rank for rank, (asset_id, _distance) in enumerate(vector_rows, 1)}
    asset_by_id = {asset.id: asset for asset in assets}
    candidate_ids = set(keyword_ranks) | set(vector_ranks)

    def reciprocal_rank(asset_id: str) -> float:
        keyword_score = 1 / (60 + keyword_ranks[asset_id]) if asset_id in keyword_ranks else 0
        vector_score = 1 / (60 + vector_ranks[asset_id]) if asset_id in vector_ranks else 0
        return keyword_score * 0.45 + vector_score * 0.55

    ranked_ids = sorted(candidate_ids, key=reciprocal_rank, reverse=True)
    items = [asset_by_id[asset_id] for asset_id in ranked_ids[:limit] if asset_id in asset_by_id]
    return items, len(candidate_ids), interpreted.keywords, "hybrid-bge-m3"


def find_similar_assets(
    db: Session,
    *,
    user_id: str,
    asset_id: str,
    limit: int,
) -> list[Asset] | None:
    settings = get_settings()
    source = db.get(AssetEmbedding, asset_id)
    if source is None or source.user_id != user_id or source.model != settings.embedding_model:
        return None

    distance = AssetEmbedding.embedding.cosine_distance(source.embedding)
    similar_ids = list(
        db.scalars(
            select(AssetEmbedding.asset_id)
            .join(Asset, Asset.id == AssetEmbedding.asset_id)
            .where(
                AssetEmbedding.user_id == user_id,
                AssetEmbedding.model == settings.embedding_model,
                AssetEmbedding.asset_id != asset_id,
                Asset.is_deleted.is_(False),
            )
            .order_by(distance)
            .limit(limit)
        )
    )
    if not similar_ids:
        return []
    assets = list(
        db.scalars(
            select(Asset)
            .options(selectinload(Asset.tags).selectinload(AssetTag.tag))
            .where(Asset.id.in_(similar_ids))
        ).unique()
    )
    asset_by_id = {asset.id: asset for asset in assets}
    return [asset_by_id[item_id] for item_id in similar_ids if item_id in asset_by_id]
