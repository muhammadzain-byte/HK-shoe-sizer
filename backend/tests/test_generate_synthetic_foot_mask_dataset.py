from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_synthetic_foot_mask_dataset import generate_dataset


def write_focus_manifest(root: Path) -> None:
    raw = root / "datasets/external/focus/raw/sample_001"
    raw.mkdir(parents=True, exist_ok=True)
    mesh = raw / "mesh.obj"
    mesh.write_text(
        "\n".join(["v -1 -2 0", "v 1 -2 0", "v 1 2 0", "v -1 2 0", "v 0 2.5 0", "f 1 2 3"]),
        encoding="utf-8",
    )
    manifest_dir = root / "datasets/external/common/manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "focus_synfoot2_foot3d_manifest.json").write_text(
        json.dumps(
            {
                "dataset_id": "focus_synfoot2_foot3d",
                "sample_count": 1,
                "samples": [
                    {
                        "sample_id": "sample_001_mesh",
                        "dataset_id": "focus_synfoot2_foot3d",
                        "mesh_path": mesh.relative_to(root).as_posix(),
                        "available_labels": ["mesh"],
                        "research_use_only": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_generator_creates_image_mask_metadata_and_manifest(tmp_path: Path) -> None:
    write_focus_manifest(tmp_path)

    report = generate_dataset("focus_synfoot2_foot3d", 14, 42, project_root=tmp_path)

    assert report["generated_sample_count"] == 14
    assert report["mask_sample_count"] == 14
    assert "valid" in report["class_counts"]
    assert "toe_cropped" in report["class_counts"]
    assert len(list((tmp_path / "datasets/external/generated_foot_masks/images").glob("*.png"))) == 14
    assert len(list((tmp_path / "datasets/external/generated_foot_masks/masks").glob("*_mask.png"))) == 14
    assert (tmp_path / "datasets/external/generated_foot_masks/manifests/generated_foot_masks_manifest.json").exists()
    assert (tmp_path / "datasets/external/common/manifests/generated_foot_masks_from_focus_manifest.json").exists()


def test_generator_fails_safely_without_mesh_assets(tmp_path: Path) -> None:
    report = generate_dataset("focus_synfoot2_foot3d", 10, 42, project_root=tmp_path)

    assert report["generated_sample_count"] == 0
    assert report["issues"]
