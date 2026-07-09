from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_TABLES = (
    "project_assets",
    "asset_tags",
    "projects",
    "assets",
    "tags",
    "folders",
    "tasks",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clear AssetVault library index data without touching source asset files.",
    )
    parser.add_argument(
        "--database",
        default="assetvault.db",
        help="Path to the SQLite database file. Defaults to ./assetvault.db.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Run without interactive confirmation.",
    )
    return parser.parse_args()


def existing_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "select name from sqlite_master where type = 'table'",
    ).fetchall()
    return {row[0] for row in rows}


def table_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'select count(*) from "{table}"').fetchone()[0])


def backup_database(database_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(f"{database_path.stem}.before-clear-{timestamp}.bak")
    shutil.copy2(database_path, backup_path)
    return backup_path


def main() -> None:
    args = parse_args()
    database_path = Path(args.database).resolve()
    if not database_path.exists():
        raise SystemExit(f"Database not found: {database_path}")

    with sqlite3.connect(database_path) as connection:
        tables = existing_tables(connection)
        target_tables = [table for table in DEFAULT_TABLES if table in tables]
        counts_before = {table: table_count(connection, table) for table in target_tables}

        print(f"Database: {database_path}")
        print("Tables to clear:")
        for table, count in counts_before.items():
            print(f"  {table}: {count}")

        if not args.yes:
            confirmation = input("Type CLEAR to remove these index records: ").strip()
            if confirmation != "CLEAR":
                raise SystemExit("Aborted.")

        backup_path = backup_database(database_path)

        connection.execute("pragma foreign_keys = off")
        try:
            for table in target_tables:
                connection.execute(f'delete from "{table}"')
            connection.commit()
        finally:
            connection.execute("pragma foreign_keys = on")

        counts_after = {table: table_count(connection, table) for table in target_tables}

    print(f"Backup: {backup_path}")
    print("Tables after clear:")
    for table, count in counts_after.items():
        print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
