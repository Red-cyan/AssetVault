from collections.abc import Callable, Iterator
from datetime import datetime
from mimetypes import guess_type
from os import walk
from pathlib import Path
from threading import Lock

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
MAX_FILE_ATTEMPTS = 2
MAX_RECORDED_FAILURES = 100

_active_folder_scans: set[str] = set()
_active_folder_scans_lock = Lock()


def iter_supported_files(
    root: Path,
    *,
    on_error: Callable[[OSError], None] | None = None,
) -> Iterator[Path]:
    for dirpath, dirnames, filenames in walk(root, onerror=on_error):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIR_NAMES]
        current_dir = Path(dirpath)
        for filename in filenames:
            path = current_dir / filename
            if get_asset_type(path):
                yield path


def count_supported_files(root: Path) -> int:
    return sum(1 for _ in iter_supported_files(root))


def try_start_folder_scan(folder_id: str) -> bool:
    with _active_folder_scans_lock:
        if folder_id in _active_folder_scans:
            return False
        _active_folder_scans.add(folder_id)
        return True


def finish_folder_scan(folder_id: str) -> None:
    with _active_folder_scans_lock:
        _active_folder_scans.discard(folder_id)


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


def _task_was_canceled(db: Session, task: Task) -> bool:
    db.expire(task, ["status"])
    return task.status == "canceled"


def _index_file(
    db: Session,
    *,
    path: Path,
    user_id: str,
    folder_id: str,
) -> str:
    stat = path.stat()
    modified_at = datetime.fromtimestamp(stat.st_mtime)
    resolved_path = str(path.resolve())
    existing = db.scalar(
        select(Asset).where(Asset.user_id == user_id, Asset.path == resolved_path)
    )
    restored = existing is not None and not existing.exists_on_disk
    unchanged = (
        existing is not None
        and existing.size_bytes == stat.st_size
        and existing.file_modified_at == modified_at
        and existing.file_hash is not None
    )

    if existing is None:
        asset = Asset(user_id=user_id, folder_id=folder_id, path=resolved_path)
        db.add(asset)
        outcome = "imported"
    else:
        asset = existing
        outcome = "restored" if restored else ("unchanged" if unchanged else "updated")

    asset.folder_id = folder_id
    asset.exists_on_disk = True
    asset.missing_since = None
    if unchanged:
        return outcome

    asset.name = path.name
    asset.stem = path.stem
    asset.extension = path.suffix.lower().lstrip(".")
    asset.asset_type = get_asset_type(path) or "other"
    asset.size_bytes = stat.st_size
    asset.mime_type = guess_type(path.name)[0]
    asset.file_hash = calculate_file_fingerprint(path)
    asset.file_created_at = datetime.fromtimestamp(stat.st_ctime)
    asset.file_modified_at = modified_at
    asset.indexed_at = datetime.now()

    db.flush()
    if asset.asset_type == "image":
        thumbnail_path = generate_image_thumbnail(asset.id, path)
        if thumbnail_path:
            asset.thumbnail_path = thumbnail_path
    elif asset.asset_type == "video":
        thumbnail_path = generate_video_thumbnail(asset.id, path)
        if thumbnail_path:
            asset.thumbnail_path = thumbnail_path
    return outcome


def _mark_task_failed(db: Session, task: Task, error: str) -> None:
    task.status = "failed"
    task.error = error
    task.message = "Scan failed"
    task.finished_at = datetime.now()
    db.commit()


def scan_folder(db: Session, *, task_id: str, user_id: str, folder_id: str) -> None:
    task = db.get(Task, task_id)
    folder = db.get(Folder, folder_id)
    if task is None or folder is None:
        return
    if task.status == "canceled":
        return
    if not try_start_folder_scan(folder_id):
        _mark_task_failed(db, task, "Another scan is already running for this folder")
        return

    try:
        task.status = "running"
        task.started_at = datetime.now()
        task.message = "Scanning files"
        db.commit()

        root = Path(folder.path)
        if not root.exists() or not root.is_dir():
            _mark_task_failed(db, task, "Folder does not exist or is not a directory")
            return

        task.total = count_supported_files(root)
        db.commit()

        counters = {"imported": 0, "updated": 0, "unchanged": 0, "restored": 0}
        failures: list[dict[str, str | int]] = []
        failed_count = 0

        def record_walk_error(error: OSError) -> None:
            nonlocal failed_count
            failed_count += 1
            if len(failures) < MAX_RECORDED_FAILURES:
                failures.append(
                    {
                        "path": error.filename or str(root),
                        "error": str(error),
                        "retry_count": 0,
                    }
                )

        for index, path in enumerate(
            iter_supported_files(root, on_error=record_walk_error), start=1
        ):
            if _task_was_canceled(db, task):
                task.message = "Scan canceled"
                task.finished_at = datetime.now()
                task.result = {
                    **counters,
                    "failed": failed_count,
                    "failures": failures,
                    "total": task.total,
                }
                db.commit()
                return

            last_error: Exception | None = None
            for _attempt in range(MAX_FILE_ATTEMPTS):
                try:
                    with db.begin_nested():
                        outcome = _index_file(
                            db,
                            path=path,
                            user_id=user_id,
                            folder_id=folder_id,
                        )
                    counters[outcome] += 1
                    last_error = None
                    break
                except Exception as error:
                    last_error = error

            if last_error is not None:
                failed_count += 1
                if len(failures) < MAX_RECORDED_FAILURES:
                    failures.append(
                        {
                            "path": str(path),
                            "error": str(last_error),
                            "retry_count": MAX_FILE_ATTEMPTS - 1,
                        }
                    )

            task.processed = index
            task.progress = int(index / max(task.total, 1) * 100)
            if index % 25 == 0:
                db.commit()

        if _task_was_canceled(db, task):
            task.message = "Scan canceled"
            task.finished_at = datetime.now()
            task.result = {
                **counters,
                "failed": failed_count,
                "failures": failures,
                "total": task.total,
            }
            db.commit()
            return

        now = datetime.now()
        folder_assets = db.scalars(
            select(Asset).where(
                Asset.user_id == user_id,
                Asset.folder_id == folder_id,
                Asset.is_deleted.is_(False),
            )
        )
        missing_marked = 0
        for asset in folder_assets:
            if Path(asset.path).exists():
                continue
            if asset.exists_on_disk:
                missing_marked += 1
                asset.missing_since = now
            asset.exists_on_disk = False

        folder.last_scanned_at = now
        task.status = "success"
        task.progress = 100
        task.message = (
            f"Scan completed, imported {counters['imported']}, updated {counters['updated']}, "
            f"unchanged {counters['unchanged']}, restored {counters['restored']}, "
            f"missing {missing_marked}, failed {failed_count}"
        )
        task.result = {
            **counters,
            "missing_marked": missing_marked,
            "failed": failed_count,
            "failures": failures,
            "total": task.total,
        }
        task.finished_at = datetime.now()
        db.commit()
    except Exception as error:
        db.rollback()
        task = db.get(Task, task_id)
        if task is not None and task.status != "canceled":
            _mark_task_failed(db, task, str(error))
    finally:
        finish_folder_scan(folder_id)
