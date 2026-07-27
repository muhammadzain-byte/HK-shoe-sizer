from __future__ import annotations

import json
from pathlib import Path

from scripts.build_research_splits import build_splits


def write_manifest(root: Path, labels: list[str], count: int = 5) -> None:
    path = root / "datasets/external/common/manifests"
    path.mkdir(parents=True, exist_ok=True)
    samples = [
        {
            "sample_id": f"sample_{idx}",
            "dataset_id": "found_synfoot",
            "available_labels": labels,
            "research_use_only": True,
        }
        for idx in range(count)
    ]
    (path / "found_synfoot_manifest.json").write_text(
        json.dumps({"dataset_id": "found_synfoot", "sample_count": count, "samples": samples}),
        encoding="utf-8",
    )


def test_splits_are_deterministic(tmp_path: Path) -> None:
    write_manifest(tmp_path, ["image", "mask"], count=10)

    first = build_splits("found_synfoot", "segmentation_baseline", 0.8, 0.1, 0.1, project_root=tmp_path)
    second = build_splits("found_synfoot", "segmentation_baseline", 0.8, 0.1, 0.1, project_root=tmp_path)

    assert first == second
    assert first["sample_count"] == 10
    assert len(first["test"]) >= 1


def test_split_builder_rejects_missing_labels(tmp_path: Path) -> None:
    write_manifest(tmp_path, ["image"], count=10)

    result = build_splits("found_synfoot", "segmentation_baseline", 0.8, 0.1, 0.1, project_root=tmp_path)

    assert result["sample_count"] == 0
    assert result["issues"]


def test_mesh_reconstruction_split_uses_mesh_labels(tmp_path: Path) -> None:
    write_manifest(tmp_path, ["mesh"], count=9)

    result = build_splits("found_synfoot", "mesh_reconstruction_research", 0.8, 0.1, 0.1, project_root=tmp_path)

    assert result["sample_count"] == 9
    assert len(result["train"]) == 7
    assert len(result["val"]) == 1
    assert len(result["test"]) == 1
    assert result["issues"] == []
