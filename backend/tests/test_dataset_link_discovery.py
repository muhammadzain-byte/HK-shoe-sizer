from __future__ import annotations

import json
from pathlib import Path

from app.services.external_dataset_service import ExternalDatasetService
from scripts import external_dataset_manager


def write_registry(root: Path) -> None:
    folder = root / "datasets/external/found/metadata"
    folder.mkdir(parents=True, exist_ok=True)
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


def test_link_discovery_creates_discovered_links_json(tmp_path: Path, monkeypatch) -> None:
    write_registry(tmp_path)

    monkeypatch.setattr(
        external_dataset_manager,
        "fetch_text",
        lambda _url: "Download data at https://drive.google.com/file/d/example/view and https://example.com/data.zip",
    )

    result = external_dataset_manager.discover_links(
        ExternalDatasetService(project_root=tmp_path),
        "found_synfoot",
    )

    assert result["links_found"]
    assert any(link["kind"] == "google_drive" for link in result["links_found"])
    assert (tmp_path / "datasets/external/found/metadata/discovered_links.json").exists()
