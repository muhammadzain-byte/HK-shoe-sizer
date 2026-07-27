from __future__ import annotations

import json
from pathlib import Path

from app.services.external_dataset_service import ExternalDatasetService
from scripts.external_dataset_manager import extract_dataset


def write_registry(root: Path) -> None:
    (root / "datasets/external/found/raw").mkdir(parents=True, exist_ok=True)
    (root / "datasets/external/found/metadata").mkdir(parents=True, exist_ok=True)
    (root / "datasets/external/registry.json").write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "id": "found_synfoot",
                        "name": "FOUND / SynFoot",
                        "repo_url": None,
                        "project_url": None,
                        "paper_url": "https://arxiv.org/abs/2310.18279",
                        "dataset_type": ["synthetic_rgb"],
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


def test_extract_skips_if_no_archive_exists(tmp_path: Path) -> None:
    write_registry(tmp_path)

    result = extract_dataset(ExternalDatasetService(project_root=tmp_path), "found_synfoot", explicit=True)

    assert result["extracted"] is False
    assert "No supported archives found." in result["issues"]
    assert (tmp_path / "datasets/external/found/metadata/extraction_report.json").exists()
