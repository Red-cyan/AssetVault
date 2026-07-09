from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Asset, AssetTag, Tag

TYPE_TAGS = {
    "image": ["图片", "视觉参考"],
    "video": ["视频", "动态素材"],
    "model": ["模型", "三维资产"],
    "motion": ["动作", "MMD"],
    "ue": ["UE资产", "Unreal"],
}

KEYWORD_TAGS = {
    "girl": ["人物", "少女"],
    "character": ["人物", "角色"],
    "maid": ["人物", "女仆"],
    "stage": ["舞台", "演出"],
    "concert": ["舞台", "演唱会"],
    "dance": ["动作", "舞蹈"],
    "motion": ["动作"],
    "camera": ["镜头"],
    "face": ["表情", "面部"],
    "hair": ["头发"],
    "road": ["场景", "道路"],
    "car": ["载具"],
    "vehicle": ["载具"],
    "texture": ["贴图"],
    "hdr": ["HDR", "环境光"],
    "music": ["音乐"],
    "bgm": ["音乐"],
}

EXTENSION_TAGS = {
    "pmx": ["PMX", "MMD模型"],
    "pmd": ["PMD", "MMD模型"],
    "vmd": ["VMD", "MMD动作"],
    "fbx": ["FBX"],
    "obj": ["OBJ"],
    "glb": ["GLB"],
    "gltf": ["GLTF"],
    "blend": ["Blender"],
    "uasset": ["UAsset", "UE"],
}


def deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        result.append(normalized)
    return result


def infer_tags(asset: Asset) -> list[str]:
    text = f"{asset.name} {asset.path}".lower()
    tags = TYPE_TAGS.get(asset.asset_type, ["素材"]).copy()
    tags.extend(EXTENSION_TAGS.get(asset.extension.lower(), []))
    for keyword, keyword_tags in KEYWORD_TAGS.items():
        if keyword in text:
            tags.extend(keyword_tags)

    path_parts = [part.lower() for part in Path(asset.path).parts]
    if any(part in path_parts for part in ["characters", "character", "人物", "角色"]):
        tags.append("人物")
    if any(part in path_parts for part in ["stage", "stages", "舞台"]):
        tags.append("舞台")
    if any(part in path_parts for part in ["motion", "motions", "动作"]):
        tags.append("动作")

    return deduplicate(tags)[:10]


def infer_description(asset: Asset, tags: list[str]) -> str:
    type_label = {
        "image": "图片素材",
        "video": "视频素材",
        "model": "三维模型素材",
        "motion": "动作数据素材",
        "ue": "Unreal Engine 资产",
    }.get(asset.asset_type, "数字素材")
    tag_text = "、".join(tags[:6])
    return (
        f"这是一个{type_label}，文件名为 {asset.name}，"
        f"系统根据文件类型、扩展名和路径推断其适合用于：{tag_text}。"
    )


def apply_ai_analysis(db: Session, *, asset: Asset) -> tuple[list[str], str]:
    tags = infer_tags(asset)
    description = infer_description(asset, tags)
    asset.description = description

    existing_tag_ids = {link.tag_id for link in asset.tags}
    for name in tags:
        tag = db.scalar(select(Tag).where(Tag.user_id == asset.user_id, Tag.name == name))
        if tag is None:
            tag = Tag(user_id=asset.user_id, name=name, source="ai")
            db.add(tag)
            db.flush()
        if tag.id not in existing_tag_ids:
            db.add(AssetTag(asset_id=asset.id, tag_id=tag.id))
            existing_tag_ids.add(tag.id)

    db.commit()
    return tags, description
