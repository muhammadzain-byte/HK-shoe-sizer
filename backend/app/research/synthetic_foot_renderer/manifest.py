from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


DATASET_ID = "generated_foot_masks_from_focus"


def write_generated_manifest(project_root: Path, samples: list[dict[str, Any]], issues: list[str] | None = None) -> dict[str, Any]:
    class_counts = Counter(sample.get("quality_label", "unknown") for sample in samples)
    manifest = {
        "dataset_id": DATASET_ID,
        "source_dataset_id": "focus_synfoot2_foot3d",
        "source_url": "generated_from_local_focus_meshes",
        "paper_url": "https://arxiv.org/abs/2502.06367",
        "license_status": "unknown",
        "sample_count": len(samples),
        "mask_sample_count": sum(1 for sample in samples if sample.get("mask_path")),
        "class_counts": dict(sorted(class_counts.items())),
        "label_types": ["image", "mask", "quality_label"],
        "synthetic_research_only": True,
        "not_accuracy_evidence": True,
        "research_use_only": True,
        "issues": issues or [],
        "samples": samples,
    }
    local_manifest_dir = project_root / "datasets/external/generated_foot_masks/manifests"
    common_manifest_dir = project_root / "datasets/external/common/manifests"
    local_manifest_dir.mkdir(parents=True, exist_ok=True)
    common_manifest_dir.mkdir(parents=True, exist_ok=True)
    for path in [
        local_manifest_dir / "generated_foot_masks_manifest.json",
        local_manifest_dir / f"{DATASET_ID}_manifest.json",
        common_manifest_dir / f"{DATASET_ID}_manifest.json",
    ]:
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
