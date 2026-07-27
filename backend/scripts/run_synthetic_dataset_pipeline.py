from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.build_research_splits import build_splits  # noqa: E402
from scripts.check_dataset_population import check_population  # noqa: E402
from scripts.generate_synthetic_foot_mask_dataset import generate_dataset  # noqa: E402
from scripts.train_research_models import train_research_model  # noqa: E402


def run_pipeline(
    source: str = "focus_synfoot2_foot3d",
    count: int = 1000,
    *,
    train_mask_quality: bool = False,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    generation = generate_dataset(source, count, 42, project_root=project_root)
    population = check_population(project_root=project_root)
    split = build_splits(
        "generated_foot_masks_from_focus",
        "mask_quality",
        0.8,
        0.1,
        0.1,
        limit=count,
        project_root=project_root,
    )
    training: dict[str, Any] | None = None
    if train_mask_quality:
        training = train_research_model(
            "mask_quality",
            "generated_foot_masks_from_focus",
            limit=count,
            project_root=project_root,
        )
    model_artifacts = []
    if training:
        for key in ["model_path", "feature_schema_path"]:
            if training.get(key):
                model_artifacts.append(training[key])
    report = {
        "source_dataset_id": source,
        "dataset_id": "generated_foot_masks_from_focus",
        "source_assets_found": generation.get("source_assets_found", 0),
        "source_assets_used": generation.get("source_assets_used", 0),
        "generated_sample_count": generation.get("generated_sample_count", 0),
        "mask_sample_count": generation.get("mask_sample_count", 0),
        "class_counts": generation.get("class_counts", {}),
        "population_status": (population.get("datasets", {}).get("generated_foot_masks_from_focus") or {}).get("status"),
        "split_status": "ready" if split.get("sample_count", 0) > 0 and not split.get("issues") else "skipped",
        "split_sample_count": split.get("sample_count", 0),
        "training_status": (training or {}).get("status", "not_run"),
        "training_report": training,
        "model_artifacts": model_artifacts,
        "production_enabled": False,
        "synthetic_research_only": True,
        "not_accuracy_evidence": True,
        "issues": [*generation.get("issues", []), *split.get("issues", [])],
    }
    output = project_root / "artifacts/external_dataset_pipeline/generated_foot_masks_pipeline_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run generated synthetic mask dataset pipeline.")
    parser.add_argument("--source", default="focus_synfoot2_foot3d")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--train-mask-quality", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_pipeline(args.source, args.count, train_mask_quality=args.train_mask_quality), indent=2))


if __name__ == "__main__":
    main()
