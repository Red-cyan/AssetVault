import json
import struct
from pathlib import Path

from backend.app.models import Asset
from backend.app.services.asset_extractor import extract_asset_metadata
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
    model_name = "初音未来".encode("shift_jis").ljust(20, b"\x00")
    source.write_bytes(signature + model_name + struct.pack("<I", 128))

    result = extract_asset_metadata(source)

    assert result.status == "structured"
    assert result.metadata["target_model"] == "初音未来"
    assert result.metadata["bone_keyframe_count"] == 128
    assert result.semantic_eligible is False
    assert result.semantic_text is None


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
