from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Setting

DEFAULT_SETTINGS = {
    "cache_dir": "./cache",
    "theme": "system",
    "ai_base_url": "https://api.openai.com/v1",
    "ai_api_key": "",
    "ai_chat_model": "gpt-4o-mini",
    "thumbnail_quality": 82,
}


def get_user_settings(db: Session, *, user_id: str) -> dict:
    rows = db.scalars(select(Setting).where(Setting.user_id == user_id))
    values = DEFAULT_SETTINGS.copy()
    for row in rows:
        values[row.key] = row.value.get("value")
    return values


def update_user_settings(db: Session, *, user_id: str, updates: dict) -> dict:
    for key, value in updates.items():
        if key not in DEFAULT_SETTINGS or value is None:
            continue
        setting = db.scalar(select(Setting).where(Setting.user_id == user_id, Setting.key == key))
        if setting is None:
            setting = Setting(user_id=user_id, key=key, value={"value": value})
            db.add(setting)
        else:
            setting.value = {"value": value}
    db.commit()
    return get_user_settings(db, user_id=user_id)


def public_settings(values: dict) -> dict:
    return {
        "cache_dir": values["cache_dir"],
        "theme": values["theme"],
        "ai_base_url": values["ai_base_url"],
        "ai_api_key_configured": bool(values.get("ai_api_key")),
        "ai_chat_model": values["ai_chat_model"],
        "thumbnail_quality": values["thumbnail_quality"],
    }
