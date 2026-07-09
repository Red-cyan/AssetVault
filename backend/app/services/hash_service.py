from hashlib import sha256
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


def calculate_file_fingerprint(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None

    size = path.stat().st_size
    digest = sha256()
    digest.update(str(size).encode("utf-8"))

    try:
        with path.open("rb") as file:
            digest.update(file.read(CHUNK_SIZE))
            if size > CHUNK_SIZE:
                file.seek(max(size - CHUNK_SIZE, 0))
                digest.update(file.read(CHUNK_SIZE))
    except OSError:
        return None
    return f"quick-sha256:{digest.hexdigest()}"
