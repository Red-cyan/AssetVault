from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Asset


def scan_missing_assets(db: Session, *, user_id: str) -> dict[str, int]:
    assets = list(
        db.scalars(
            select(Asset).where(
                Asset.user_id == user_id,
                Asset.is_deleted.is_(False),
            )
        )
    )
    missing_count = 0
    restored_count = 0
    now = datetime.utcnow()

    for asset in assets:
        exists = Path(asset.path).exists()
        if exists and not asset.exists_on_disk:
            asset.exists_on_disk = True
            asset.missing_since = None
            restored_count += 1
        elif not exists:
            if asset.exists_on_disk:
                asset.missing_since = now
            asset.exists_on_disk = False
            missing_count += 1

    db.commit()
    return {
        "checked_count": len(assets),
        "missing_count": missing_count,
        "restored_count": restored_count,
    }
