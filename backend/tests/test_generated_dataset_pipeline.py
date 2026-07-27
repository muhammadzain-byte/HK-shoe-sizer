from __future__ import annotations

from pathlib import Path

from scripts.check_dataset_population import check_population
from scripts.generate_synthetic_foot_mask_dataset import generate_dataset
from scripts.run_synthetic_dataset_pipeline import run_pipeline
from tests.test_generate_synthetic_foot_mask_dataset import write_focus_manifest


def test_generated_dataset_is_recognized_by_population_checker(tmp_path: Path) -> None:
    write_focus_manifest(tmp_path)
    generate_dataset("focus_synfoot2_foot3d", 14, 42, project_root=tmp_path)

    result = check_population(project_root=tmp_path)
    generated = result["datasets"]["generated_foot_masks_from_focus"]

    assert generated["status"] == "training_ready"
    assert generated["mask_sample_count"] == 14
    assert generated["synthetic_research_only"] is True
    assert generated["not_accuracy_evidence"] is True


def test_full_synthetic_pipeline_writes_final_report(tmp_path: Path) -> None:
    write_focus_manifest(tmp_path)

    report = run_pipeline("focus_synfoot2_foot3d", 28, train_mask_quality=True, project_root=tmp_path)

    assert report["generated_sample_count"] == 28
    assert report["mask_sample_count"] == 28
    assert report["split_status"] == "ready"
    assert report["training_status"] in {"trained", "rule_based_fallback"}
    assert report["production_enabled"] is False
    assert (tmp_path / "artifacts/external_dataset_pipeline/generated_foot_masks_pipeline_report.json").exists()
