from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_runtime_schema(engine: Engine) -> None:
    if not engine.url.drivername.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "assets" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("assets")}
    with engine.begin() as connection:
        if "file_hash" not in columns:
            connection.execute(text("ALTER TABLE assets ADD COLUMN file_hash VARCHAR(80)"))
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_assets_file_hash ON assets (file_hash)")
            )
