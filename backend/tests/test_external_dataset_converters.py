from __future__ import annotations

import json
from pathlib import Path

from app.services.external_dataset_converters.base import ExternalDatasetConverter
from app.services.external_dataset_converters.focus_converter import FocusDatasetConverter
from app.services.external_dataset_converters.found_converter import FoundDatasetConverter
from app.services.external_dataset_service import ExternalDatasetService
from scripts.evaluate_external_dataset_masks import evaluate_masks


def test_converter_base_interface_works() -> None:
    service = ExternalDatasetService()
    entry = service.get_dataset_entry("focus_synfoot2_foot3d")
    converter = ExternalDatasetConverter(entry, service.project_root)

    manifest = converter.generate_manifest()

    assert manifest.dataset_id == entry.id
    assert manifest.research_use_only is True


def test_focus_converter_returns_zero_sample_manifest_when_raw_empty(tmp_path: Path) -> None:
    service = ExternalDatasetService()
    entry = service.get_dataset_entry("focus_synfoot2_foot3d").model_copy(
        update={
            "local_raw_dir": "datasets/external/focus/raw",
            "local_processed_dir": "datasets/external/focus/processed",
        }
    )
    converter = FocusDatasetConverter(entry, tmp_path)

    manifest = converter.generate_manifest()

    assert manifest.sample_count == 0
    assert "Dataset not downloaded. Use print-download-instructions." in manifest.issues


def test_found_converter_returns_zero_sample_manifest_when_raw_empty(tmp_path: Path) -> None:
    service = ExternalDatasetService()
    entry = service.get_dataset_entry("found_synfoot").model_copy(
        update={
            "local_raw_dir": "datasets/external/found/raw",
            "local_processed_dir": "datasets/external/found/processed",
        }
    )
    converter = FoundDatasetConverter(entry, tmp_path)

    manifest = converter.generate_manifest()

    assert manifest.sample_count == 0
    assert "Dataset not downloaded. Use print-download-instructions." in manifest.issues


def test_generic_mesh_filenames_keep_parent_context(tmp_path: Path) -> None:
    service = ExternalDatasetService()
    entry = service.get_dataset_entry("focus_synfoot2_foot3d").model_copy(
        update={
            "local_raw_dir": "datasets/external/focus/raw",
            "local_processed_dir": "datasets/external/focus/processed",
        }
    )
    raw = tmp_path / "datasets/external/focus/raw"
    (raw / "FOUND/0035").mkdir(parents=True, exist_ok=True)
    (raw / "FOUND/0036").mkdir(parents=True, exist_ok=True)
    (raw / "FOUND/0035/mesh.obj").write_text("o foot_35\n", encoding="utf-8")
    (raw / "FOUND/0036/mesh.obj").write_text("o foot_36\n", encoding="utf-8")
    converter = FocusDatasetConverter(entry, tmp_path)

    manifest = converter.generate_manifest()
    sample_ids = {sample.sample_id for sample in manifest.samples}

    assert manifest.sample_count == 2
    assert "found_0035_mesh" in sample_ids
    assert "found_0036_mesh" in sample_ids


def test_converter_ignores_macos_archive_sidecars(tmp_path: Path) -> None:
    service = ExternalDatasetService()
    entry = service.get_dataset_entry("focus_synfoot2_foot3d").model_copy(
        update={
            "local_raw_dir": "datasets/external/focus/raw",
            "local_processed_dir": "datasets/external/focus/processed",
        }
    )
    raw = tmp_path / "datasets/external/focus/raw"
    (raw / "FOUND/0035").mkdir(parents=True, exist_ok=True)
    (raw / "__MACOSX/FOUND/0035").mkdir(parents=True, exist_ok=True)
    (raw / "FOUND/0035/mesh.obj").write_text("o foot_35\n", encoding="utf-8")
    (raw / "FOUND/0035/.DS_Store").write_text("ignored\n", encoding="utf-8")
    (raw / "__MACOSX/FOUND/0035/._mesh.obj").write_text("ignored\n", encoding="utf-8")
    converter = FocusDatasetConverter(entry, tmp_path)

    manifest = converter.generate_manifest()

    assert manifest.sample_count == 1
    assert manifest.file_inventory["meshes"] == 1


def test_evaluation_script_exits_gracefully_when_manifest_empty(tmp_path: Path) -> None:
    manifest_path = tmp_path / "empty_manifest.json"
    manifest_path.write_text(
        json.dumps({"dataset_id": "found_synfoot", "samples": []}),
        encoding="utf-8",
    )

    result = evaluate_masks("found_synfoot", manifest_path)

    assert result["evaluated_count"] == 0
    assert "Manifest has no samples." in result["issues"]
