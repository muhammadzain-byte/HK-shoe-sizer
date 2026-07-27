from __future__ import annotations

from pathlib import Path

from scripts.train_research_models import train_research_model


def test_smoke_dataset_can_be_generated_and_trained(tmp_path: Path) -> None:
    result = train_research_model(
        "mask_quality",
        "smoke_test",
        project_root=tmp_path,
        allow_smoke_data=True,
    )

    assert result["smoke_only"] is True
    assert "Smoke model trained only to verify code path" in result["message"]
    assert (tmp_path / "datasets/external/common/smoke_test/metadata.json").exists()
    assert (tmp_path / "artifacts/training/mask_quality/training_report.json").exists()
