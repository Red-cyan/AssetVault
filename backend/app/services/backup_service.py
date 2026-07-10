from datetime import datetime
from pathlib import Path
from subprocess import CalledProcessError, run

from fastapi import HTTPException
from sqlalchemy.engine import make_url

from backend.app.core.config import get_settings


def pg_dump_url(database_url: str) -> str:
    url = make_url(database_url)
    if not url.drivername.startswith("postgresql"):
        raise HTTPException(status_code=400, detail="仅支持 PostgreSQL 数据库备份。")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def backup_database() -> dict:
    settings = get_settings()
    database_url = pg_dump_url(settings.database_url)
    parsed_url = make_url(settings.database_url)
    backup_dir = Path("./backups").resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"assetvault-{timestamp}.dump"

    try:
        run(
            ["pg_dump", "--format=custom", f"--file={target}", database_url],
            check=True,
            capture_output=True,
            timeout=300,
        )
    except FileNotFoundError:
        try:
            with target.open("wb") as output:
                run(
                    [
                        "docker",
                        "exec",
                        "assetvault-postgres",
                        "pg_dump",
                        "-U",
                        parsed_url.username or "assetvault",
                        "-d",
                        parsed_url.database or "assetvault",
                        "--format=custom",
                    ],
                    check=True,
                    stdout=output,
                    capture_output=False,
                    timeout=300,
                )
        except (FileNotFoundError, CalledProcessError) as fallback_error:
            target.unlink(missing_ok=True)
            raise HTTPException(
                status_code=503,
                detail="未找到可用的 pg_dump 或 PostgreSQL Docker 容器。",
            ) from fallback_error
    except CalledProcessError as error:
        detail = error.stderr.decode(errors="replace").strip() or "pg_dump 执行失败"
        raise HTTPException(status_code=500, detail=detail) from error

    return {
        "path": str(target),
        "size_bytes": target.stat().st_size,
        "created_at": datetime.now(),
    }
