from datetime import datetime
from pathlib import Path
from shutil import copy2

from fastapi import HTTPException

from backend.app.core.config import get_settings


def resolve_sqlite_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise HTTPException(status_code=400, detail="当前仅支持 SQLite 数据库备份。")
    raw_path = database_url.removeprefix("sqlite:///")
    if raw_path in {":memory:", ""}:
        raise HTTPException(status_code=400, detail="内存数据库无法备份。")
    return Path(raw_path).resolve()


def backup_database() -> dict:
    settings = get_settings()
    source = resolve_sqlite_path(settings.database_url)
    if not source.exists():
        raise HTTPException(status_code=404, detail="数据库文件不存在，无法备份。")

    backup_dir = Path("./backups").resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"assetvault-{timestamp}.db"
    copy2(source, target)
    return {
        "path": str(target),
        "size_bytes": target.stat().st_size,
        "created_at": datetime.utcnow(),
    }
