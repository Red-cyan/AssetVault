from collections import defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Asset
from backend.app.services.hash_service import calculate_file_fingerprint


def refresh_missing_hashes(db: Session, *, user_id: str) -> int:
    assets = list(
        db.scalars(
            select(Asset).where(
                Asset.user_id == user_id,
                Asset.file_hash.is_(None),
                Asset.is_deleted.is_(False),
            )
        )
    )
    updated = 0
    for asset in assets:
        file_hash = calculate_file_fingerprint(Path(asset.path))
        if file_hash:
            asset.file_hash = file_hash
            updated += 1
    if updated:
        db.commit()
    return updated


def find_duplicate_groups(db: Session, *, user_id: str) -> tuple[list[dict], int]:
    hashed_assets = list(
        db.scalars(
            select(Asset).where(
                Asset.user_id == user_id,
                Asset.file_hash.is_not(None),
                Asset.is_deleted.is_(False),
            )
        )
    )
    groups: dict[tuple[str, int], list[Asset]] = defaultdict(list)
    for asset in hashed_assets:
        groups[(asset.file_hash or "", asset.size_bytes)].append(asset)

    duplicate_groups = []
    for (file_hash, size_bytes), items in groups.items():
        if len(items) < 2:
            continue
        duplicate_groups.append(
            {
                "file_hash": file_hash,
                "size_bytes": size_bytes,
                "count": len(items),
                "items": sorted(items, key=lambda item: item.path),
            }
        )

    duplicate_groups.sort(key=lambda group: (group["count"], group["size_bytes"]), reverse=True)
    return duplicate_groups, len(hashed_assets)
