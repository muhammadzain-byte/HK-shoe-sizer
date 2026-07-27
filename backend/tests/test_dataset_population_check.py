from __future__ import annotations

import json
from pathlib import Path

from scripts.check_dataset_population import check_population


def write_registry(root: Path) -> None:
    path = root / "datasets/external"
    path.mkdir(parents=True, exist_ok=True)
    (path / "registry.json").write_text(
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


def test_empty_external_datasets_report_not_populated(tmp_path: Path) -> None:
    write_registry(tmp_path)

    result = check_population(project_root=tmp_path)

    assert result["ready_for_training"] is False
    assert result["datasets"]["found_synfoot"]["status"] == "empty"


def test_mesh_manifest_reports_training_ready_for_mesh_research(tmp_path: Path) -> None:
    write_registry(tmp_path)
    manifest_dir = tmp_path / "datasets/external/common/manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "found_synfoot_manifest.json").write_text(
        json.dumps(
            {
                "dataset_id": "found_synfoot",
                "sample_count": 4,
                "samples": [
                    {
                        "sample_id": f"mesh_{idx}",
                        "dataset_id": "found_synfoot",
                        "available_labels": ["mesh"],
                        "research_use_only": True,
                    }
                    for idx in range(4)
                ],
            }
        ),
        encoding="utf-8",
    )

    result = check_population(project_root=tmp_path)

    assert result["ready_for_training"] is True
    assert result["datasets"]["found_synfoot"]["status"] == "training_ready"
    assert result["datasets"]["found_synfoot"]["supported_training_tasks"] == ["mesh_reconstruction_research"]
