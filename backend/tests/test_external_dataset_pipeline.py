from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from scripts.run_external_dataset_pipeline import run_pipeline


def write_registry(root: Path) -> None:
    registry = root / "datasets/external"
    registry.mkdir(parents=True, exist_ok=True)
    (registry / "registry.json").write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "id": "found_synfoot",
                        "name": "FOUND / SynFoot",
                        "repo_url": "https://github.com/OllieBoyne/FOUND",
                        "project_url": "https://www.ollieboyne.com/FOUND/",
                        "paper_url": "https://arxiv.org/abs/2310.18279",
                        "dataset_type": ["synthetic_rgb", "masks"],
                        "intended_use": ["research"],
                        "not_for": ["production_accuracy_claims"],
                        "download_policy": "manual_or_explicit_script_only",
                        "license_review_required": True,
                        "local_raw_dir": "datasets/external/found/raw",
                        "local_processed_dir": "datasets/external/found/processed",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def create_fake_image_mask(root: Path, idx: int) -> None:
    raw = root / "datasets/external/found/raw"
    raw.mkdir(parents=True, exist_ok=True)
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[8:58, 20:44] = 255
    cv2.imwrite(str(raw / f"sample{idx:03d}.jpg"), image)
    cv2.imwrite(str(raw / f"sample{idx:03d}_mask.png"), mask)


def test_end_to_end_pipeline_exits_gracefully_when_dataset_missing(tmp_path: Path) -> None:
    write_registry(tmp_path)

    result = run_pipeline("found_synfoot", "mask_quality", project_root=tmp_path)

    assert result["status"] == "waiting_for_dataset_files"
    assert result["research_only"] is True


def test_end_to_end_pipeline_works_on_small_fake_dataset(tmp_path: Path) -> None:
    write_registry(tmp_path)
    for idx in range(4):
        create_fake_image_mask(tmp_path, idx)

    result = run_pipeline("found_synfoot", "mask_quality", accept_license=True, explicit=True, limit=4, project_root=tmp_path)

    assert result["conversion"]["converted_sample_count"] == 4
    assert result["training"]["status"] in {"trained", "rule_based_fallback"}
