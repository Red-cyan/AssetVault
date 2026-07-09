from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from backend.app.models import Asset, AssetTag, Tag


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
) -> tuple[list[Asset], int, list[str]]:
    interpreted = interpret_query(query)
    patterns = [f"%{keyword}%" for keyword in interpreted.keywords]

    stmt = (
        select(Asset)
        .options(selectinload(Asset.tags).selectinload(AssetTag.tag))
        .outerjoin(AssetTag, AssetTag.asset_id == Asset.id)
        .outerjoin(Tag, Tag.id == AssetTag.tag_id)
        .where(Asset.user_id == user_id)
    )

    conditions = []
    for pattern in patterns:
        conditions.append(Asset.name.ilike(pattern))
        conditions.append(Asset.path.ilike(pattern))
        conditions.append(Asset.description.ilike(pattern))
        conditions.append(Asset.extension.ilike(pattern))
        conditions.append(Tag.name.ilike(pattern))
    if interpreted.asset_types:
        conditions.append(Asset.asset_type.in_(interpreted.asset_types))
    if conditions:
        stmt = stmt.where(or_(*conditions))

    candidates = list(db.scalars(stmt.distinct()).unique())
    scored = [
        (asset, score_asset(asset, interpreted.keywords, interpreted.asset_types))
        for asset in candidates
    ]
    scored = [(asset, score) for asset, score in scored if score > 0]
    scored.sort(
        key=lambda item: (
            item[1],
            item[0].file_modified_at or item[0].indexed_at,
        ),
        reverse=True,
    )
    items = [asset for asset, _score in scored[:limit]]
    return items, len(scored), interpreted.keywords
