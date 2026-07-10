from argparse import ArgumentParser
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, select

from backend.app import models  # noqa: F401
from backend.app.core.config import get_settings
from backend.app.db.base import Base

TABLE_ORDER = [
    "users",
    "folders",
    "settings",
    "tags",
    "tasks",
    "assets",
    "asset_tags",
    "projects",
    "project_assets",
]


def migrate(sqlite_path: Path) -> dict[str, int]:
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite source does not exist: {sqlite_path}")

    destination_url = get_settings().database_url
    if not destination_url.startswith("postgresql"):
        raise SystemExit("ASSETVAULT_DATABASE_URL must point to PostgreSQL")

    source_engine = create_engine(f"sqlite:///{sqlite_path.resolve().as_posix()}")
    destination_engine = create_engine(destination_url, pool_pre_ping=True)
    source_metadata = MetaData()
    source_metadata.reflect(bind=source_engine)

    with destination_engine.begin() as destination:
        existing_users = destination.scalar(
            select(func.count()).select_from(Base.metadata.tables["users"])
        )
        if existing_users:
            raise SystemExit("PostgreSQL destination is not empty; migration was not run")

        counts: dict[str, int] = {}
        with source_engine.connect() as source:
            for table_name in TABLE_ORDER:
                source_table = source_metadata.tables.get(table_name)
                destination_table = Base.metadata.tables[table_name]
                if source_table is None:
                    counts[table_name] = 0
                    continue
                rows = [dict(row._mapping) for row in source.execute(select(source_table))]
                if rows:
                    destination.execute(destination_table.insert(), rows)
                counts[table_name] = len(rows)

    source_engine.dispose()
    destination_engine.dispose()
    return counts


def main() -> None:
    parser = ArgumentParser(description="Import an AssetVault SQLite database into PostgreSQL")
    parser.add_argument("sqlite_path", nargs="?", default="assetvault.db", type=Path)
    args = parser.parse_args()
    counts = migrate(args.sqlite_path)
    for table_name, count in counts.items():
        print(f"{table_name}: {count}")


if __name__ == "__main__":
    main()
