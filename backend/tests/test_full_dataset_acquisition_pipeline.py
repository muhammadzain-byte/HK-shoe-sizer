from __future__ import annotations

import json
from pathlib import Path

from scripts.run_external_dataset_pipeline import run_pipeline


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


def test_full_pipeline_produces_report_when_dataset_missing(tmp_path: Path) -> None:
    write_registry(tmp_path)

    result = run_pipeline("found_synfoot", "mask_quality", safe_auto=True, project_root=tmp_path)

    assert result["manual_required"] is True
    assert result["production_enabled"] is False
    assert (tmp_path / "artifacts/external_dataset_pipeline/found_synfoot_full_pipeline_report.json").exists()
