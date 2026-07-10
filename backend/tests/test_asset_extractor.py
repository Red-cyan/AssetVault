import json
import struct
from pathlib import Path

from backend.app.models import Asset
from backend.app.services.asset_extractor import (
    extract_asset_metadata,
    get_format_extractor_name,
)
from backend.app.services.embedding_service import build_asset_embedding_text
from backend.app.services.file_type_service import get_asset_type


def _pmx_text(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<i", len(encoded)) + encoded


def test_pmx_header_provides_explicit_semantic_text(tmp_path: Path) -> None:
    source = tmp_path / "character.pmx"
    source.write_bytes(
        b"PMX "
        + struct.pack("<f", 2.1)
        + bytes([8, 1, 0, 4, 4, 4, 4, 4, 4])
        + _pmx_text("初音未来")
        + _pmx_text("Hatsune Miku")
        + _pmx_text("演唱会人物模型")
        + _pmx_text("")
    )

    result = extract_asset_metadata(source)

    assert result.status == "structured"
    assert result.extractor == "pmx-header"
    assert result.metadata["model_name"] == "初音未来"
    assert result.semantic_eligible is True
    assert "演唱会人物模型" in (result.semantic_text or "")


def test_vmd_structure_does_not_guess_motion_semantics(tmp_path: Path) -> None:
    source = tmp_path / "motion.vmd"
    signature = b"Vocaloid Motion Data 0002".ljust(30, b"\x00")
    model_name = b"Miku".ljust(20, b"\x00")
    bone_frame = b"Center".ljust(15, b"\x00") + struct.pack("<I", 90) + bytes(92)
    morph_frame = b"Smile".ljust(15, b"\x00") + struct.pack("<If", 120, 0.8)
    camera_frame = struct.pack("<I", 180) + bytes(57)
    source.write_bytes(
        signature
        + model_name
        + struct.pack("<I", 1)
        + bone_frame
        + struct.pack("<I", 1)
        + morph_frame
        + struct.pack("<I", 1)
        + camera_frame
    )

    result = extract_asset_metadata(source)

    assert result.status == "structured"
    assert result.extractor == "vmd-structure-v2"
    assert result.metadata["target_model"] == "Miku"
    assert result.metadata["bone_keyframe_count"] == 1
    assert result.metadata["morph_keyframe_count"] == 1
    assert result.metadata["camera_keyframe_count"] == 1
    assert result.metadata["duration_seconds"] == 6.0
    assert result.metadata["bone_names"] == ["Center"]
    assert result.metadata["morph_names"] == ["Smile"]
    assert result.semantic_eligible is False
    assert "Smile" in (result.semantic_text or "")


def test_obj_extracts_geometry_names_and_material_dependencies(tmp_path: Path) -> None:
    texture = tmp_path / "textures" / "stage.png"
    texture.parent.mkdir()
    texture.write_bytes(b"png")
    (tmp_path / "stage.mtl").write_text(
        "newmtl LEDMaterial\nmap_Kd textures/stage.png\n",
        encoding="utf-8",
    )
    source = tmp_path / "stage.obj"
    source.write_text(
        "\n".join(
            [
                "mtllib stage.mtl",
                "o ConcertStage",
                "g MainPlatform",
                "usemtl LEDMaterial",
                "v 0 0 0",
                "v 1 0 0",
                "v 0 1 0",
                "vt 0 0",
                "vn 0 0 1",
                "f 1/1/1 2/1/1 3/1/1",
            ]
        ),
        encoding="utf-8",
    )

    result = extract_asset_metadata(source)

    assert result.extractor == "obj-structure-v1"
    assert result.metadata["vertex_count"] == 3
    assert result.metadata["face_count"] == 1
    assert result.metadata["objects"] == ["ConcertStage"]
    assert result.metadata["materials"] == ["LEDMaterial"]
    assert str(texture.resolve()) in result.metadata["dependencies"]
    assert result.metadata["missing_dependencies"] == []
    assert result.semantic_eligible is False
    assert "ConcertStage" in (result.semantic_text or "")


def test_gltf_and_glb_extract_scene_structure_and_dependencies(tmp_path: Path) -> None:
    document = {
        "asset": {
            "version": "2.0",
            "generator": "AssetVault Test",
            "extras": {"description": "赛博朋克舞台"},
        },
        "scenes": [{"name": "Concert"}],
        "nodes": [{"name": "LED Wall"}],
        "meshes": [{"name": "Main Stage"}],
        "materials": [{"name": "Neon"}],
        "animations": [{"name": "Screen Loop"}],
        "images": [{"uri": "textures/neon.png"}],
        "buffers": [{"uri": "stage.bin", "byteLength": 16}],
    }
    gltf = tmp_path / "stage.gltf"
    gltf.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

    gltf_result = extract_asset_metadata(gltf)

    assert gltf_result.metadata["mesh_count"] == 1
    assert gltf_result.metadata["animation_count"] == 1
    assert gltf_result.metadata["materials_names"] == ["Neon"]
    assert str((tmp_path / "stage.bin").resolve()) in gltf_result.metadata["dependencies"]
    assert str((tmp_path / "stage.bin").resolve()) in gltf_result.metadata[
        "missing_dependencies"
    ]
    assert gltf_result.semantic_eligible is True

    json_chunk = json.dumps(document, ensure_ascii=False).encode("utf-8")
    json_chunk += b" " * (-len(json_chunk) % 4)
    total_length = 12 + 8 + len(json_chunk)
    glb = tmp_path / "stage.glb"
    glb.write_bytes(
        struct.pack("<4sII", b"glTF", 2, total_length)
        + struct.pack("<II", len(json_chunk), 0x4E4F534A)
        + json_chunk
    )

    glb_result = extract_asset_metadata(glb)
    assert glb_result.status == "structured"
    assert glb_result.metadata["format"] == "glb"
    assert glb_result.metadata["nodes_names"] == ["LED Wall"]


def test_uproject_extracts_engine_modules_and_description(tmp_path: Path) -> None:
    source = tmp_path / "Concert.uproject"
    source.write_text(
        json.dumps(
            {
                "FileVersion": 3,
                "EngineAssociation": "5.5",
                "Description": "赛博朋克演唱会工程",
                "Modules": [{"Name": "Concert"}],
                "Plugins": [{"Name": "Niagara"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = extract_asset_metadata(source)

    assert result.metadata["engine_association"] == "5.5"
    assert result.metadata["modules"] == ["Concert"]
    assert result.metadata["plugins"] == ["Niagara"]
    assert result.semantic_eligible is True


def test_container_headers_remain_metadata_only(tmp_path: Path) -> None:
    fbx = tmp_path / "model.fbx"
    fbx.write_bytes(b"Kaydara FBX Binary  \x00\x1a\x00" + struct.pack("<I", 7500))
    blend = tmp_path / "scene.blend"
    blend.write_bytes(b"BLENDER-v300")

    fbx_result = extract_asset_metadata(fbx)
    blend_result = extract_asset_metadata(blend)

    assert fbx_result.metadata == {"format": "fbx", "container": "binary", "version": 7500}
    assert blend_result.metadata["version"] == "3.00"
    assert fbx_result.semantic_eligible is False
    assert blend_result.semantic_eligible is False


def test_embedding_requires_semantic_evidence() -> None:
    asset = Asset(
        name="dance.vmd",
        stem="dance",
        extension="vmd",
        asset_type="motion",
        path="E:/assets/dance.vmd",
        size_bytes=100,
        semantic_eligible=False,
    )

    assert build_asset_embedding_text(asset) is None

    asset.description = "用户确认的街舞动作"
    text = build_asset_embedding_text(asset)
    assert text is not None
    assert "用户确认的街舞动作" in text
    assert "E:/assets" not in text


def test_project_and_opaque_extensions_are_indexed_as_files() -> None:
    assert get_asset_type(Path("Demo.uproject")) == "project"
    assert get_asset_type(Path("archive.casc")) == "opaque"
    assert get_format_extractor_name(Path("model.obj")) == "obj-structure-v1"
    assert get_format_extractor_name(Path("scene.glb")) == "gltf-structure-v1"
