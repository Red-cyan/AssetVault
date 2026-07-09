import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Asset, AssetTag, Tag
from backend.app.services.settings_service import get_user_settings


@dataclass(frozen=True)
class AnalysisResult:
    tags: list[str]
    description: str
    source: str

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


def build_local_analysis(asset: Asset) -> AnalysisResult:
    tags = infer_tags(asset)
    description = infer_description(asset, tags)
    return AnalysisResult(tags=tags, description=description, source="local-heuristic")


def build_ai_prompt(asset: Asset) -> str:
    return (
        "请为数字资产管理软件生成素材标签和简介。"
        "只返回 JSON，不要返回 Markdown。JSON 字段必须是 tags 和 description。"
        "tags 是 4 到 10 个中文短标签，description 是 1 到 3 句中文简介。"
        f"\n文件名：{asset.name}"
        f"\n扩展名：{asset.extension}"
        f"\n素材类型：{asset.asset_type}"
        f"\n路径：{asset.path}"
        f"\n作者：{asset.author or '未知'}"
        f"\n已有备注：{asset.description or '无'}"
    )


def chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def parse_ai_content(content: str) -> AnalysisResult | None:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None

    raw_tags = data.get("tags")
    description = data.get("description")
    if not isinstance(raw_tags, list) or not isinstance(description, str):
        return None

    tags = deduplicate([item for item in raw_tags if isinstance(item, str)])[:10]
    description = description.strip()
    if not tags or not description:
        return None
    return AnalysisResult(tags=tags, description=description, source="openai-compatible")


def call_openai_compatible(settings: dict[str, Any], asset: Asset) -> AnalysisResult | None:
    api_key = str(settings.get("ai_api_key") or "").strip()
    base_url = str(settings.get("ai_base_url") or "").strip()
    model = str(settings.get("ai_chat_model") or "").strip()
    if not api_key or not base_url or not model:
        return None

    body = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "你是一个数字资产管理助手，擅长为 UE5、Blender、MMD 素材生成标签。",
            },
            {"role": "user", "content": build_ai_prompt(asset)},
        ],
    }
    request = Request(
        chat_completions_url(base_url),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return None

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    if not isinstance(content, str):
        return None
    return parse_ai_content(content)


def apply_ai_analysis(db: Session, *, asset: Asset) -> AnalysisResult:
    settings = get_user_settings(db, user_id=asset.user_id)
    result = call_openai_compatible(settings, asset) or build_local_analysis(asset)
    tags = result.tags
    description = result.description
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
    return result
