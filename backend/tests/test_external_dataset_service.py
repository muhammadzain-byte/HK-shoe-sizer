from __future__ import annotations

import json
from pathlib import Path

from app.services.external_dataset_service import ExternalDatasetService


def test_registry_loads() -> None:
    entries = ExternalDatasetService().load_registry()

    assert len(entries) >= 5


def test_all_required_dataset_entries_exist() -> None:
    ids = {entry.id for entry in ExternalDatasetService().load_registry()}

    assert {
        "focus_synfoot2_foot3d",
        "found_synfoot",
        "find_foot3d",
        "footgait3d",
        "generated_foot_masks_from_focus",
    }.issubset(ids)


def test_dataset_ids_are_unique() -> None:
    entries = ExternalDatasetService().load_registry()
    ids = [entry.id for entry in entries]

    assert len(ids) == len(set(ids))


def test_focus_entry_includes_links() -> None:
    entry = ExternalDatasetService().get_dataset_entry("focus_synfoot2_foot3d")

    assert entry.repo_url == "https://github.com/OllieBoyne/FOCUS"
    assert entry.project_url == "https://www.ollieboyne.com/FOCUS/"
    assert entry.paper_url == "https://arxiv.org/abs/2502.06367"


def test_found_entry_includes_links() -> None:
    entry = ExternalDatasetService().get_dataset_entry("found_synfoot")

    assert entry.repo_url == "https://github.com/OllieBoyne/FOUND"
    assert entry.project_url == "https://www.ollieboyne.com/FOUND/"
    assert entry.paper_url == "https://arxiv.org/abs/2310.18279"


def test_footgait3d_entry_includes_huggingface_link() -> None:
    entry = ExternalDatasetService().get_dataset_entry("footgait3d")

    assert entry.project_url == "https://huggingface.co/datasets/ljw285/FootGait3D"


def test_service_lists_datasets() -> None:
    datasets = ExternalDatasetService().list_supported_datasets()

    assert {item["id"] for item in datasets} >= {"focus_synfoot2_foot3d", "found_synfoot"}


def test_inspect_missing_dataset_returns_clear_issues_not_crash(tmp_path: Path) -> None:
    service = _empty_focus_service(tmp_path)
    result = service.inspect_dataset("focus_synfoot2_foot3d")

    assert result.dataset_id == "focus_synfoot2_foot3d"
    assert "Dataset not downloaded. Use print-download-instructions." in result.issues


def test_manifest_generation_works_with_zero_files(tmp_path: Path) -> None:
    service = _empty_focus_service(tmp_path)
    manifest = service.generate_manifest("focus_synfoot2_foot3d")

    assert manifest.dataset_id == "focus_synfoot2_foot3d"
    assert manifest.sample_count == 0
    assert manifest.research_use_only is True


def test_create_common_manifest_writes_metadata_file() -> None:
    output_path = ExternalDatasetService().create_common_manifest("focus_synfoot2_foot3d")

    assert output_path.exists()
    assert output_path.name == "focus_synfoot2_foot3d_manifest.json"


def _empty_focus_service(root: Path) -> ExternalDatasetService:
    registry_dir = root / "datasets/external"
    registry_dir.mkdir(parents=True, exist_ok=True)
    entry = ExternalDatasetService().get_dataset_entry("focus_synfoot2_foot3d").model_dump(mode="json")
    entry["local_raw_dir"] = "datasets/external/focus/raw"
    entry["local_processed_dir"] = "datasets/external/focus/processed"
    (registry_dir / "registry.json").write_text(json.dumps({"datasets": [entry]}), encoding="utf-8")
    return ExternalDatasetService(project_root=root)
