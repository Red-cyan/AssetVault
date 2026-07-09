from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

DEMO_FILES = {
    "characters/anime_blue_hair_twin_tail_jk.png": "image",
    "characters/mmd_character_sample.pmx": "placeholder",
    "stages/concert_stage_led_screen.png": "image",
    "stages/white_performance_stage.obj": "obj",
    "motions/dance_motion_pop.vmd": "placeholder",
    "textures/fabric_blue_pattern.png": "image",
    "hdr/concert_hall_light_probe.hdr": "placeholder",
    "ue/ue5_stage_prop.uasset": "placeholder",
    "blender/lighting_setup.blend": "placeholder",
}


def create_image(path: Path, title: str, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (960, 540), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((48, 48, 912, 492), outline=(255, 255, 255), width=6)
    draw.rectangle((90, 350, 870, 430), fill=(20, 20, 24))
    draw.text((108, 374), title, fill=(255, 255, 255))
    image.save(path)


def create_obj(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# AssetVault demo OBJ",
                "o White_Performance_Stage",
                "v -1.0 0.0 -1.0",
                "v 1.0 0.0 -1.0",
                "v 1.0 0.0 1.0",
                "v -1.0 0.0 1.0",
                "v -1.0 0.25 -1.0",
                "v 1.0 0.25 -1.0",
                "v 1.0 0.25 1.0",
                "v -1.0 0.25 1.0",
                "f 1 2 3 4",
                "f 5 8 7 6",
            ]
        ),
        encoding="utf-8",
    )


def create_placeholder(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (
            "AssetVault demo placeholder\n"
            f"name={path.name}\n"
            f"type={label}\n"
            "This file is only used for scanning and metadata demos.\n"
        ).encode()
    )


def create_demo_assets(output_dir: Path, *, force: bool) -> list[Path]:
    created: list[Path] = []
    image_specs = {
        "characters/anime_blue_hair_twin_tail_jk.png": (
            "Anime Blue Hair Twin Tail JK",
            (58, 128, 204),
        ),
        "stages/concert_stage_led_screen.png": (
            "Concert Stage LED Screen",
            (82, 58, 150),
        ),
        "textures/fabric_blue_pattern.png": (
            "Fabric Blue Pattern Texture",
            (32, 118, 104),
        ),
    }

    for relative_path, kind in DEMO_FILES.items():
        path = output_dir / relative_path
        if path.exists() and not force:
            continue
        if kind == "image":
            title, color = image_specs[relative_path]
            create_image(path, title, color)
        elif kind == "obj":
            create_obj(path)
        else:
            create_placeholder(path, kind)
        created.append(path)
    return created


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create demo assets for AssetVault.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("demo-assets"),
        help="Target directory. Defaults to ./demo-assets.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing demo files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output.resolve()
    created = create_demo_assets(output_dir, force=args.force)
    print(f"Demo asset directory: {output_dir}")
    print(f"Created or updated files: {len(created)}")
    for path in created:
        print(f"- {path.relative_to(output_dir)}")


if __name__ == "__main__":
    main()
