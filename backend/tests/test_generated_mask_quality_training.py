from __future__ import annotations

from pathlib import Path

from scripts.build_research_splits import build_splits
from scripts.generate_synthetic_foot_mask_dataset import generate_dataset
from scripts.train_research_models import train_research_model
from tests.test_generate_synthetic_foot_mask_dataset import write_focus_manifest


def test_split_builder_accepts_generated_dataset(tmp_path: Path) -> None:
    write_focus_manifest(tmp_path)
    generate_dataset("focus_synfoot2_foot3d", 28, 42, project_root=tmp_path)

    result = build_splits("generated_foot_masks_from_focus", "mask_quality", 0.8, 0.1, 0.1, project_root=tmp_path)

    assert result["sample_count"] == 28
    assert result["issues"] == []


def test_mask_quality_training_works_on_generated_masks_and_keeps_production_disabled(tmp_path: Path) -> None:
    write_focus_manifest(tmp_path)
    generate_dataset("focus_synfoot2_foot3d", 28, 42, project_root=tmp_path)

    result = train_research_model("mask_quality", "generated_foot_masks_from_focus", project_root=tmp_path)

    assert result["status"] in {"trained", "rule_based_fallback"}
    assert result["trained_on"] == "generated_foot_masks_from_focus"
    assert result["synthetic_research_only"] is True
    assert result["not_accuracy_evidence"] is True
    assert result["production_enabled"] is False
    assert result["class_counts"]
    registry = (tmp_path / "models/research/model_registry.json").read_text(encoding="utf-8")
    assert "mask_quality_research_generated_focus_v1" in registry
    assert '"production_enabled": false' in registry
