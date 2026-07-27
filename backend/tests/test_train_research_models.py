from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from app.services.external_dataset_service import ExternalDatasetService
from scripts.train_research_models import train_research_model


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


def create_fake_image_mask(root: Path) -> None:
    raw = root / "datasets/external/found/raw"
    raw.mkdir(parents=True, exist_ok=True)
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[8:58, 20:44] = 255
    cv2.imwrite(str(raw / "sample001.jpg"), image)
    cv2.imwrite(str(raw / "sample001_mask.png"), mask)


def test_mask_quality_training_skips_safely_when_no_data(tmp_path: Path) -> None:
    write_registry(tmp_path)

    result = train_research_model("mask_quality", "found_synfoot", project_root=tmp_path)

    assert result["status"] == "skipped"
    assert "No mask samples available." in result["reason"]


def test_mask_quality_training_produces_report_when_fake_data_exists(tmp_path: Path) -> None:
    write_registry(tmp_path)
    create_fake_image_mask(tmp_path)
    service = ExternalDatasetService(project_root=tmp_path)
    service.convert_dataset("found_synfoot")

    result = train_research_model("mask_quality", "found_synfoot", project_root=tmp_path)

    assert result["status"] in {"trained", "rule_based_fallback"}
    assert (tmp_path / "artifacts/training/mask_quality/training_report.json").exists()
    assert (tmp_path / "models/research/model_registry.json").exists()


def test_mesh_reconstruction_placeholder_reports_ready_when_mesh_labels_exist(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "datasets/external/common/manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "focus_synfoot2_foot3d_manifest.json").write_text(
        json.dumps(
            {
                "dataset_id": "focus_synfoot2_foot3d",
                "sample_count": 3,
                "samples": [
                    {
                        "sample_id": f"mesh_{idx}",
                        "dataset_id": "focus_synfoot2_foot3d",
                        "available_labels": ["mesh"],
                        "research_use_only": True,
                    }
                    for idx in range(3)
                ],
            }
        ),
        encoding="utf-8",
    )

    result = train_research_model("mesh_reconstruction_research", "focus_synfoot2_foot3d", project_root=tmp_path)

    assert result["ready"] is True
    assert result["trained"] is False
    assert result["sample_count"] == 3
    assert result["production_enabled"] is False
    assert (tmp_path / "artifacts/training/mesh_reconstruction_research/training_readiness_report.json").exists()
