from __future__ import annotations

import json
from pathlib import Path

from app.services.external_dataset_service import ExternalDatasetService
from scripts.external_dataset_manager import handle_download


def write_registry(root: Path) -> None:
    (root / "datasets/external/found/metadata").mkdir(parents=True, exist_ok=True)
    (root / "datasets/external").mkdir(parents=True, exist_ok=True)
    (root / "datasets/external/registry.json").write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "id": "found_synfoot",
                        "name": "FOUND / SynFoot",
                        "repo_url": "https://github.com/OllieBoyne/FOUND",
                        "project_url": "https://www.ollieboyne.com/FOUND/",
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


def test_download_refuses_without_explicit_flags(tmp_path: Path) -> None:
    write_registry(tmp_path)

    status = handle_download(ExternalDatasetService(project_root=tmp_path), "found_synfoot", False, False)

    assert status == 1
    assert (tmp_path / "datasets/external/found/metadata/download_attempt.json").exists()


def test_download_dry_run_does_not_write_payload(tmp_path: Path, monkeypatch) -> None:
    write_registry(tmp_path)
    from scripts import external_dataset_manager

    monkeypatch.setattr(
        external_dataset_manager,
        "discover_links",
        lambda _service, _dataset_id: {"links_found": [], "issues": []},
    )

    status = handle_download(
        ExternalDatasetService(project_root=tmp_path),
        "found_synfoot",
        True,
        True,
        dry_run=True,
    )

    assert status == 0
    assert not any((tmp_path / "datasets/external/found/raw").glob("*"))
