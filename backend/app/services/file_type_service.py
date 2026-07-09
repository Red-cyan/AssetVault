from pathlib import Path

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "bmp", "tiff", "hdr", "exr"}
VIDEO_EXTENSIONS = {"mp4", "mov", "mkv", "avi", "webm"}
MODEL_EXTENSIONS = {"pmx", "pmd", "fbx", "obj", "glb", "gltf", "blend"}
MOTION_EXTENSIONS = {"vmd", "vpd"}
UE_EXTENSIONS = {"uasset"}

SUPPORTED_EXTENSIONS = (
    IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | MODEL_EXTENSIONS | MOTION_EXTENSIONS | UE_EXTENSIONS
)


def get_asset_type(path: Path) -> str | None:
    extension = path.suffix.lower().lstrip(".")
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if extension in VIDEO_EXTENSIONS:
        return "video"
    if extension in MODEL_EXTENSIONS:
        return "model"
    if extension in MOTION_EXTENSIONS:
        return "motion"
    if extension in UE_EXTENSIONS:
        return "ue"
    return None
