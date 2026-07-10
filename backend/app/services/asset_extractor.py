from __future__ import annotations

import json
import re
import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_STRUCTURE_ITEMS = 5_000_000
VMD_FPS = 30


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


def _decode_fixed_text(value: bytes, encoding: str = "shift_jis") -> str:
    return value.split(b"\x00", 1)[0].decode(encoding, errors="replace").strip()


def _read_count(stream: BinaryIO, label: str) -> int:
    count = struct.unpack("<I", _read_exact(stream, 4))[0]
    if count > MAX_STRUCTURE_ITEMS:
        raise ValueError(f"Unreasonable {label} count: {count}")
    return count


def _limited(values: set[str], limit: int = 256) -> list[str]:
    return sorted(value for value in values if value)[:limit]


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
        model_name = _decode_fixed_text(_read_exact(stream, 20))
        bone_frames = _read_count(stream, "VMD bone keyframe")
        bone_names: set[str] = set()
        max_frame = 0
        for _ in range(bone_frames):
            bone_names.add(_decode_fixed_text(_read_exact(stream, 15)))
            frame = struct.unpack("<I", _read_exact(stream, 4))[0]
            max_frame = max(max_frame, frame)
            _read_exact(stream, 92)

        morph_frames = _read_count(stream, "VMD morph keyframe")
        morph_names: set[str] = set()
        for _ in range(morph_frames):
            morph_names.add(_decode_fixed_text(_read_exact(stream, 15)))
            frame = struct.unpack("<I", _read_exact(stream, 4))[0]
            max_frame = max(max_frame, frame)
            _read_exact(stream, 4)

        camera_frames = _read_count(stream, "VMD camera keyframe")
        for _ in range(camera_frames):
            frame = struct.unpack("<I", _read_exact(stream, 4))[0]
            max_frame = max(max_frame, frame)
            _read_exact(stream, 57)

    searchable_parts = [model_name, *_limited(bone_names), *_limited(morph_names)]

    return ExtractionResult(
        extractor="vmd-structure-v2",
        status="structured",
        metadata={
            "format": "vmd",
            "signature": signature.decode("ascii", errors="replace"),
            "target_model": model_name or None,
            "bone_keyframe_count": bone_frames,
            "morph_keyframe_count": morph_frames,
            "camera_keyframe_count": camera_frames,
            "duration_frames": max_frame,
            "duration_seconds": round(max_frame / VMD_FPS, 3),
            "bone_names": _limited(bone_names),
            "morph_names": _limited(morph_names),
        },
        # A target model and frame count do not describe what the motion means.
        semantic_text="\n".join(value for value in searchable_parts if value) or None,
        semantic_eligible=False,
    )


def _resolve_dependency(path: Path, value: str) -> str:
    dependency = Path(value.replace("\\", "/"))
    try:
        return str((path.parent / dependency).resolve())
    except (OSError, RuntimeError):
        return str(path.parent / dependency)


def _parse_mtl_dependencies(obj_path: Path, libraries: set[str]) -> set[str]:
    dependencies: set[str] = set()
    texture_directives = {
        "map_ka",
        "map_kd",
        "map_ks",
        "map_d",
        "map_bump",
        "bump",
        "disp",
        "decal",
        "refl",
    }
    for library in libraries:
        mtl_path = obj_path.parent / Path(library.replace("\\", "/"))
        dependencies.add(_resolve_dependency(obj_path, library))
        try:
            usable_mtl = mtl_path.is_file() and mtl_path.stat().st_size <= MAX_TEXT_BYTES
        except OSError:
            usable_mtl = False
        if not usable_mtl:
            continue
        for line in mtl_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2 and parts[0].lower() in texture_directives:
                # Texture options may precede the final path; the last token is the common case.
                texture_path = parts[1].split()[-1]
                dependencies.add(_resolve_dependency(mtl_path, texture_path))
    return dependencies


def extract_obj(path: Path) -> ExtractionResult:
    counts = {"vertex": 0, "texture_coordinate": 0, "normal": 0, "face": 0}
    objects: set[str] = set()
    groups: set[str] = set()
    materials: set[str] = set()
    libraries: set[str] = set()
    with path.open("r", encoding="utf-8-sig", errors="replace") as stream:
        for line in stream:
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            directive, _, content = value.partition(" ")
            content = content.strip()
            if directive == "v":
                counts["vertex"] += 1
            elif directive == "vt":
                counts["texture_coordinate"] += 1
            elif directive == "vn":
                counts["normal"] += 1
            elif directive == "f":
                counts["face"] += 1
            elif directive == "o" and content:
                objects.add(content)
            elif directive == "g" and content:
                groups.add(content)
            elif directive == "usemtl" and content:
                materials.add(content)
            elif directive == "mtllib" and content:
                libraries.update(content.split())

    if not any(counts.values()) and not objects:
        raise ValueError("OBJ contains no recognizable geometry")
    dependencies = _parse_mtl_dependencies(path, libraries)
    missing_dependencies = [item for item in dependencies if not Path(item).exists()]
    searchable_parts = [*objects, *groups, *materials, *(Path(item).name for item in dependencies)]
    return ExtractionResult(
        extractor="obj-structure-v1",
        status="structured",
        metadata={
            "format": "obj",
            "vertex_count": counts["vertex"],
            "texture_coordinate_count": counts["texture_coordinate"],
            "normal_count": counts["normal"],
            "face_count": counts["face"],
            "objects": _limited(objects),
            "groups": _limited(groups),
            "materials": _limited(materials),
            "dependencies": sorted(dependencies),
            "missing_dependencies": sorted(missing_dependencies),
        },
        semantic_text="\n".join(value for value in searchable_parts if value) or None,
        semantic_eligible=False,
    )


def _read_gltf_document(path: Path) -> dict:
    if path.suffix.lower() == ".gltf":
        if path.stat().st_size > MAX_JSON_BYTES:
            raise ValueError("glTF JSON document is too large")
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    else:
        with path.open("rb") as stream:
            magic, version, total_length = struct.unpack("<4sII", _read_exact(stream, 12))
            if magic != b"glTF" or version != 2 or total_length != path.stat().st_size:
                raise ValueError("Invalid GLB 2.0 header")
            chunk_length, chunk_type = struct.unpack("<II", _read_exact(stream, 8))
            if chunk_type != 0x4E4F534A or chunk_length > MAX_JSON_BYTES:
                raise ValueError("GLB has no supported JSON chunk")
            json_text = _read_exact(stream, chunk_length).decode("utf-8").rstrip("\x00 \t\r\n")
            data = json.loads(json_text)
    if not isinstance(data, dict) or not isinstance(data.get("asset"), dict):
        raise ValueError("glTF root or asset metadata is invalid")
    return data


def _named_values(data: dict, key: str) -> list[str]:
    values = data.get(key, [])
    if not isinstance(values, list):
        return []
    return [
        str(item["name"]).strip()
        for item in values
        if isinstance(item, dict) and item.get("name")
    ][:256]


def _gltf_dependencies(path: Path, data: dict) -> list[str]:
    dependencies: set[str] = set()
    for key in ("buffers", "images"):
        values = data.get(key, [])
        if not isinstance(values, list):
            continue
        for item in values:
            uri = item.get("uri") if isinstance(item, dict) else None
            if isinstance(uri, str) and uri and not uri.startswith("data:"):
                dependencies.add(_resolve_dependency(path, uri))
    return sorted(dependencies)


def extract_gltf(path: Path) -> ExtractionResult:
    data = _read_gltf_document(path)
    asset_info = data["asset"]
    names = {
        key: _named_values(data, key)
        for key in ("scenes", "nodes", "meshes", "materials", "animations")
    }
    dependencies = _gltf_dependencies(path, data)
    missing_dependencies = [item for item in dependencies if not Path(item).exists()]
    extras = asset_info.get("extras") if isinstance(asset_info.get("extras"), dict) else {}
    description = str(extras.get("description") or extras.get("title") or "").strip()
    searchable_parts = [
        description,
        *(name for values in names.values() for name in values),
        *(Path(item).name for item in dependencies),
    ]
    return ExtractionResult(
        extractor="gltf-structure-v1",
        status="structured",
        metadata={
            "format": path.suffix.lower().lstrip("."),
            "version": asset_info.get("version"),
            "generator": asset_info.get("generator"),
            "scene_count": len(data.get("scenes", [])),
            "node_count": len(data.get("nodes", [])),
            "mesh_count": len(data.get("meshes", [])),
            "material_count": len(data.get("materials", [])),
            "animation_count": len(data.get("animations", [])),
            **{f"{key}_names": values for key, values in names.items()},
            "dependencies": dependencies,
            "missing_dependencies": missing_dependencies,
        },
        semantic_text="\n".join(value for value in searchable_parts if value) or None,
        semantic_eligible=bool(description),
    )


def extract_fbx(path: Path) -> ExtractionResult:
    with path.open("rb") as stream:
        prefix = stream.read(MAX_TEXT_BYTES)
    binary_signature = b"Kaydara FBX Binary  \x00\x1a\x00"
    metadata: dict = {"format": "fbx"}
    searchable_names: list[str] = []
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
        searchable_names = re.findall(
            r'(?:Model|Material):\s*\d+,\s*"(?:Model|Material)::([^"]+)"', text
        )[:256]
        metadata.update(
            container="ascii",
            version=int(version_match.group(1)) if version_match else None,
            creator=creator_match.group(1) if creator_match else None,
            object_names=searchable_names,
        )
    return ExtractionResult(
        extractor="fbx-structure-v2",
        status="structured",
        metadata=metadata,
        semantic_text="\n".join(searchable_names) or None,
    )


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
    searchable_parts = [*semantic_parts, *modules, *plugins]
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
        semantic_text="\n".join(searchable_parts) or None,
        semantic_eligible=bool(friendly_name or description),
    )


Extractor = Callable[[Path], ExtractionResult]
EXTRACTORS: dict[str, Extractor] = {
    "pmx": extract_pmx,
    "vmd": extract_vmd,
    "fbx": extract_fbx,
    "obj": extract_obj,
    "gltf": extract_gltf,
    "glb": extract_gltf,
    "blend": extract_blend,
    "blender": extract_blend,
    "uproject": extract_uproject,
}
EXTRACTOR_NAMES = {
    "pmx": "pmx-header",
    "vmd": "vmd-structure-v2",
    "fbx": "fbx-structure-v2",
    "obj": "obj-structure-v1",
    "gltf": "gltf-structure-v1",
    "glb": "gltf-structure-v1",
    "blend": "blend-header",
    "blender": "blend-header",
    "uproject": "uproject-json",
}


def has_format_extractor(path: Path) -> bool:
    return path.suffix.lower().lstrip(".") in EXTRACTORS


def get_format_extractor_name(path: Path) -> str | None:
    return EXTRACTOR_NAMES.get(path.suffix.lower().lstrip("."))


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
