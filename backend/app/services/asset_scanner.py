from datetime import datetime
from mimetypes import guess_type
from os import walk
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.models import Asset, AssetTag, Folder, Task
from backend.app.services.file_type_service import get_asset_type
from backend.app.services.hash_service import calculate_file_fingerprint
from backend.app.services.thumbnail_service import (
    generate_image_thumbnail,
    generate_video_thumbnail,
)

EXCLUDED_DIR_NAMES = {
    ".git",
    ".idea",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "cache",
    "node_modules",
}


def iter_supported_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in walk(root):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIR_NAMES]
        current_dir = Path(dirpath)
        for filename in filenames:
            path = current_dir / filename
            if get_asset_type(path):
                files.append(path)
    return files


def is_excluded_path(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def cleanup_excluded_assets(db: Session, *, user_id: str) -> int:
    assets = list(db.execute(select(Asset.id, Asset.path).where(Asset.user_id == user_id)))
    excluded_ids = [asset_id for asset_id, path in assets if is_excluded_path(Path(path))]
    if not excluded_ids:
        return 0
    db.execute(delete(AssetTag).where(AssetTag.asset_id.in_(excluded_ids)))
    db.execute(delete(Asset).where(Asset.id.in_(excluded_ids)))
    db.commit()
    return len(excluded_ids)


def cleanup_missing_assets(db: Session, *, user_id: str) -> int:
    assets = list(db.execute(select(Asset.id, Asset.path).where(Asset.user_id == user_id)))
    missing_ids = [asset_id for asset_id, path in assets if not Path(path).exists()]
    if not missing_ids:
        return 0
    db.execute(delete(AssetTag).where(AssetTag.asset_id.in_(missing_ids)))
    db.execute(delete(Asset).where(Asset.id.in_(missing_ids)))
    db.commit()
    return len(missing_ids)


def scan_folder(db: Session, *, task_id: str, user_id: str, folder_id: str) -> None:
    task = db.get(Task, task_id)
    folder = db.get(Folder, folder_id)
    if task is None or folder is None:
        return

    task.status = "running"
    task.started_at = datetime.utcnow()
    task.message = "Scanning files"
    db.commit()

    root = Path(folder.path)
    if not root.exists() or not root.is_dir():
        task.status = "failed"
        task.error = "Folder does not exist or is not a directory"
        task.finished_at = datetime.utcnow()
        db.commit()
        return

    files = iter_supported_files(root)
    task.total = len(files)
    db.commit()

    imported = 0
    for index, path in enumerate(files, start=1):
        stat = path.stat()
        asset_type = get_asset_type(path)
        existing = db.scalar(
            select(Asset).where(Asset.user_id == user_id, Asset.path == str(path.resolve()))
        )
        if existing is None:
            asset = Asset(user_id=user_id, folder_id=folder_id, path=str(path.resolve()))
            db.add(asset)
            imported += 1
        else:
            asset = existing

        asset.name = path.name
        asset.stem = path.stem
        asset.extension = path.suffix.lower().lstrip(".")
        asset.asset_type = asset_type or "other"
        asset.size_bytes = stat.st_size
        asset.mime_type = guess_type(path.name)[0]
        asset.file_hash = calculate_file_fingerprint(path)
        asset.file_created_at = datetime.fromtimestamp(stat.st_ctime)
        asset.file_modified_at = datetime.fromtimestamp(stat.st_mtime)
        asset.indexed_at = datetime.utcnow()

        db.flush()
        if asset.asset_type == "image":
            thumbnail_path = generate_image_thumbnail(asset.id, path)
            if thumbnail_path:
                asset.thumbnail_path = thumbnail_path
        elif asset.asset_type == "video":
            thumbnail_path = generate_video_thumbnail(asset.id, path)
            if thumbnail_path:
                asset.thumbnail_path = thumbnail_path

        task.processed = index
        task.progress = int(index / max(task.total, 1) * 100)
        if index % 25 == 0:
            db.commit()

    folder.last_scanned_at = datetime.utcnow()
    task.status = "success"
    task.progress = 100
    task.message = f"Scan completed, imported {imported} new assets"
    task.result = {"imported": imported, "total": len(files)}
    task.finished_at = datetime.utcnow()
    db.commit()
