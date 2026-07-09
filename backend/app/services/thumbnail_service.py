from pathlib import Path
from shutil import which
from subprocess import run

from PIL import Image, ImageOps

from backend.app.core.config import get_settings


def generate_image_thumbnail(asset_id: str, source_path: Path) -> str | None:
    settings = get_settings()
    target_dir = settings.thumbnail_dir / "images"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{asset_id}.webp"
    try:
        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((512, 512))
            image.save(target_path, "WEBP", quality=82)
    except Exception:
        return None
    return str(target_path)


def generate_video_thumbnail(asset_id: str, source_path: Path) -> str | None:
    if which("ffmpeg") is None:
        return None

    settings = get_settings()
    target_dir = settings.thumbnail_dir / "videos"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{asset_id}.webp"
    try:
        result = run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                "00:00:01",
                "-i",
                str(source_path),
                "-frames:v",
                "1",
                "-vf",
                "scale=512:-1",
                str(target_path),
            ],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0 or not target_path.exists():
        return None
    return str(target_path)
