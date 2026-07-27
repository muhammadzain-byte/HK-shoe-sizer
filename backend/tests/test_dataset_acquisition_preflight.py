from __future__ import annotations

from pathlib import Path

from scripts.dataset_acquisition_preflight import run_preflight


def test_preflight_reports_missing_optional_tools_without_crashing(tmp_path: Path) -> None:
    (tmp_path / "datasets/external").mkdir(parents=True)

    result = run_preflight(project_root=tmp_path)

    assert "tools" in result
    assert "huggingface_hub" in result["tools"]
    assert isinstance(result["issues"], list)
    assert isinstance(result["instructions"], list)
