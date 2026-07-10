from __future__ import annotations

import json
import re
import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

MAX_TEXT_BYTES = 2 * 1024 * 1024


@dataclass(slots=True)
class ExtractionResult:
    extractor: str
    status: str = "metadata_only"
    metadata: dict = field(default_factory=dict)
    semantic_text: str | None = None
    semantic_eligible: bool = False
    error: str | None = None


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    value = stream.read(size)
    if len(value) != size:
        raise ValueError("Unexpected end of file")
    return value


def _read_pmx_text(stream: BinaryIO, encoding: str) -> str:
    length = struct.unpack("<i", _read_exact(stream, 4))[0]
    if length < 0 or length > MAX_TEXT_BYTES:
        raise ValueError("Invalid PMX text length")
    return _read_exact(stream, length).decode(encoding, errors="replace").strip("\x00\r\n ")


def extract_pmx(path: Path) -> ExtractionResult:
    with path.open("rb") as stream:
        if _read_exact(stream, 4) != b"PMX ":
            raise ValueError("Invalid PMX signature")
        version = struct.unpack("<f", _read_exact(stream, 4))[0]
        header_size = _read_exact(stream, 1)[0]
        header = _read_exact(stream, header_size)
        if not header:
            raise ValueError("Missing PMX global settings")
        if header[0] not in {0, 1}:
            raise ValueError("Unsupported PMX text encoding")
        encoding = "utf-16-le" if header[0] == 0 else "utf-8"
        names = [_read_pmx_text(stream, encoding) for _ in range(4)]

    name_local, name_universal, comment_local, comment_universal = names
    semantic_parts = [
        value
        for value in (name_local, name_universal, comment_local, comment_universal)
        if value
    ]
    return ExtractionResult(
        extractor="pmx-header",
        status="structured",
        metadata={
            "format": "pmx",
            "version": round(version, 2),
            "text_encoding": encoding,
            "model_name": name_local or None,
            "model_name_universal": name_universal or None,
            "comment": comment_local or None,
            "comment_universal": comment_universal or None,
        },
        semantic_text="\n".join(semantic_parts) or None,
        semantic_eligible=bool(semantic_parts),
    )


def extract_vmd(path: Path) -> ExtractionResult:
    with path.open("rb") as stream:
        signature = _read_exact(stream, 30).rstrip(b"\x00")
        if not signature.startswith(b"Vocaloid Motion Data"):
            raise ValueError("Invalid VMD signature")
        model_name = _read_exact(stream, 20).split(b"\x00", 1)[0].decode(
            "shift_jis", errors="replace"
        )
        bone_frames = struct.unpack("<I", _read_exact(stream, 4))[0]

    return ExtractionResult(
        extractor="vmd-header",
        status="structured",
        metadata={
            "format": "vmd",
            "signature": signature.decode("ascii", errors="replace"),
            "target_model": model_name or None,
            "bone_keyframe_count": bone_frames,
        },
        # A target model and frame count do not describe what the motion means.
        semantic_eligible=False,
    )


def extract_fbx(path: Path) -> ExtractionResult:
    with path.open("rb") as stream:
        prefix = stream.read(MAX_TEXT_BYTES)
    binary_signature = b"Kaydara FBX Binary  \x00\x1a\x00"
    metadata: dict = {"format": "fbx"}
    if prefix.startswith(binary_signature):
        if len(prefix) < 27:
            raise ValueError("Incomplete binary FBX header")
        metadata.update(
            container="binary",
            version=struct.unpack("<I", prefix[23:27])[0],
        )
    else:
        text = prefix.decode("utf-8", errors="replace")
        if "FBXHeaderExtension" not in text and not text.lstrip().startswith("; FBX"):
            raise ValueError("Invalid FBX signature")
        version_match = re.search(r"FBXVersion:\s*(\d+)", text)
        creator_match = re.search(r'Creator:\s*"([^"]+)"', text)
        metadata.update(
            container="ascii",
            version=int(version_match.group(1)) if version_match else None,
            creator=creator_match.group(1) if creator_match else None,
        )
    return ExtractionResult(extractor="fbx-header", status="structured", metadata=metadata)


def extract_blend(path: Path) -> ExtractionResult:
    with path.open("rb") as stream:
        header = _read_exact(stream, 12)
    if not header.startswith(b"BLENDER"):
        raise ValueError("Invalid Blend signature")
    if header[7:8] not in {b"_", b"-"} or header[8:9] not in {b"v", b"V"}:
        raise ValueError("Invalid Blend header settings")
    pointer_size = 8 if header[7:8] == b"-" else 4
    byte_order = "little" if header[8:9] == b"v" else "big"
    version_bytes = header[9:12]
    version = f"{version_bytes[0:1].decode()}.{version_bytes[1:3].decode()}"
    return ExtractionResult(
        extractor="blend-header",
        status="structured",
        metadata={
            "format": "blend",
            "version": version,
            "pointer_size": pointer_size,
            "byte_order": byte_order,
        },
    )


def extract_uproject(path: Path) -> ExtractionResult:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("UProject root must be a JSON object")
    modules = [
        item.get("Name")
        for item in data.get("Modules", [])
        if isinstance(item, dict) and item.get("Name")
    ]
    plugins = [
        item.get("Name")
        for item in data.get("Plugins", [])
        if isinstance(item, dict) and item.get("Name")
    ]
    description = str(data.get("Description") or "").strip()
    friendly_name = str(data.get("FriendlyName") or "").strip()
    category = str(data.get("Category") or "").strip()
    semantic_parts = [value for value in (friendly_name, description, category) if value]
    return ExtractionResult(
        extractor="uproject-json",
        status="structured",
        metadata={
            "format": "uproject",
            "engine_association": data.get("EngineAssociation"),
            "file_version": data.get("FileVersion"),
            "category": category or None,
            "description": description or None,
            "modules": modules,
            "plugins": plugins,
        },
        semantic_text="\n".join(semantic_parts) or None,
        semantic_eligible=bool(friendly_name or description),
    )


Extractor = Callable[[Path], ExtractionResult]
EXTRACTORS: dict[str, Extractor] = {
    "pmx": extract_pmx,
    "vmd": extract_vmd,
    "fbx": extract_fbx,
    "blend": extract_blend,
    "blender": extract_blend,
    "uproject": extract_uproject,
}
EXTRACTOR_NAMES = {
    "pmx": "pmx-header",
    "vmd": "vmd-header",
    "fbx": "fbx-header",
    "blend": "blend-header",
    "blender": "blend-header",
    "uproject": "uproject-json",
}


def has_format_extractor(path: Path) -> bool:
    return path.suffix.lower().lstrip(".") in EXTRACTORS


def extract_asset_metadata(path: Path) -> ExtractionResult:
    extension = path.suffix.lower().lstrip(".")
    extractor = EXTRACTORS.get(extension)
    if extractor is None:
        return ExtractionResult(
            extractor="generic",
            metadata={
                "format": extension or "unknown",
                "inspection": "unsupported",
                "opaque": extension in {"casc", "uasset"},
            },
        )
    try:
        return extractor(path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, struct.error) as error:
        return ExtractionResult(
            extractor=EXTRACTOR_NAMES[extension],
            status="failed",
            metadata={"format": extension},
            error=str(error),
        )
