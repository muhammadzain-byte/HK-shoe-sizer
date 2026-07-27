from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.research.mask_quality.train import train_mask_quality_model  # noqa: E402


PLACEHOLDER_TASKS = {
    "landmark_research": "No keypoint labels detected or training implementation is placeholder.",
    "surface_normal_research": "No surface normal training is implemented in this phase.",
    "point_cloud_research": "No point-cloud model training is implemented in this phase.",
    "mesh_reconstruction_research": "No mesh reconstruction model training is implemented in this phase.",
}

PLACEHOLDER_TASK_LABELS = {
    "landmark_research": {"image", "keypoints"},
    "surface_normal_research": {"image", "normal"},
    "point_cloud_research": {"point_cloud"},
    "mesh_reconstruction_research": {"mesh"},
}


def train_research_model(
    task: str,
    dataset_id: str,
    *,
    limit: int | None = None,
    epochs: int = 3,
    project_root: Path = PROJECT_ROOT,
    allow_smoke_data: bool = False,
) -> dict[str, Any]:
    if dataset_id == "smoke_test":
        if not allow_smoke_data:
            return {
                "task": task,
                "dataset_id": dataset_id,
                "trained": False,
                "status": "skipped",
                "reason": "Smoke data requires --allow-smoke-data.",
                "research_only": True,
                "smoke_only": True,
            }
        create_smoke_dataset(project_root)
    manifest_path = project_root / "datasets/external/common/manifests" / f"{dataset_id}_manifest.json"
    if task == "mask_quality":
        report = train_mask_quality_model(dataset_id, manifest_path, project_root, limit=limit)
        if dataset_id == "smoke_test":
            report["smoke_only"] = True
            report["message"] = "Smoke model trained only to verify code path. Not a research model and not production evidence."
        else:
            update_model_registry(project_root, report)
        return report
    if task == "segmentation_baseline":
        return train_segmentation_baseline(dataset_id, manifest_path, limit=limit, epochs=epochs)
    if task in PLACEHOLDER_TASKS:
        return placeholder_training_readiness(task, dataset_id, manifest_path, project_root=project_root, limit=limit)
    return {
        "task": task,
        "dataset_id": dataset_id,
        "ready": False,
        "status": "unsupported",
        "reason": f"Unsupported research task: {task}",
        "research_only": True,
    }


def train_segmentation_baseline(
    dataset_id: str,
    manifest_path: Path,
    *,
    limit: int | None = None,
    epochs: int = 3,
) -> dict[str, Any]:
    try:
        import torch  # noqa: F401
    except Exception:
        return {
            "task": "segmentation_baseline",
            "dataset_id": dataset_id,
            "trained": False,
            "status": "skipped",
            "reason": "PyTorch is unavailable or not configured for this research task.",
            "research_only": True,
        }
    return {
        "task": "segmentation_baseline",
        "dataset_id": dataset_id,
        "trained": False,
        "status": "skipped",
        "reason": "Segmentation baseline training is intentionally not implemented without reviewed image/mask layout.",
        "limit": limit,
        "epochs": epochs,
        "manifest_path": str(manifest_path),
        "research_only": True,
    }


def placeholder_training_readiness(
    task: str,
    dataset_id: str,
    manifest_path: Path,
    *,
    project_root: Path = PROJECT_ROOT,
    limit: int | None = None,
) -> dict[str, Any]:
    required_labels = PLACEHOLDER_TASK_LABELS.get(task, set())
    sample_ids: list[str] = []
    issues: list[str] = []
    if not manifest_path.exists():
        issues.append("Manifest does not exist. Run external_dataset_manager.py manifest first.")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for sample in manifest.get("samples") or []:
            labels = set(sample.get("available_labels") or [])
            if required_labels.issubset(labels):
                sample_id = sample.get("sample_id")
                if sample_id:
                    sample_ids.append(str(sample_id))
        if limit is not None:
            sample_ids = sample_ids[:limit]
        if not sample_ids:
            issues.append(f"No samples with required labels for {task}.")

    ready = bool(sample_ids)
    report = {
        "task": task,
        "dataset_id": dataset_id,
        "ready": ready,
        "trained": False,
        "status": "ready_for_research_design" if ready else "placeholder",
        "sample_count": len(sample_ids),
        "required_labels": sorted(required_labels),
        "reason": PLACEHOLDER_TASKS[task],
        "issues": issues,
        "research_only": True,
        "production_enabled": False,
    }
    report_dir = project_root / "artifacts/training" / task
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "training_readiness_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def update_model_registry(project_root: Path, report: dict[str, Any]) -> None:
    registry_path = project_root / "models/research/model_registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry = {"models": []}
    if registry_path.exists():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if report.get("dataset_id") == "generated_foot_masks_from_focus" and report.get("task") == "mask_quality":
        model_id = "mask_quality_research_generated_focus_v1"
    else:
        model_id = f"{report.get('task', 'research')}_{report.get('dataset_id', 'dataset')}_latest"
    entry = {
        "id": model_id,
        "task": report.get("task"),
        "dataset_id": report.get("dataset_id"),
        "model_path": report.get("model_path", ""),
        "research_only": True,
        "synthetic_research_only": bool(report.get("synthetic_research_only")),
        "not_accuracy_evidence": bool(report.get("not_accuracy_evidence")),
        "production_enabled": False,
        "metrics": {
            "sample_count": report.get("sample_count", 0),
            "status": report.get("status"),
        },
        "created_at": datetime.now(UTC).isoformat(),
    }
    models = [model for model in registry.get("models", []) if model.get("id") != model_id]
    models.append(entry)
    registry["models"] = models
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def create_smoke_dataset(project_root: Path) -> Path:
    smoke_root = project_root / "datasets/external/common/smoke_test"
    mask_dir = smoke_root / "masks"
    mask_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for idx in range(5):
        mask = np.zeros((96, 48), dtype=np.uint8)
        cv2.ellipse(mask, (24, 48), (14 + idx, 34), 0, 0, 360, 255, -1)
        cv2.circle(mask, (16, 12), 5, 255, -1)
        cv2.circle(mask, (24, 10), 6, 255, -1)
        cv2.circle(mask, (32, 12), 5, 255, -1)
        path = mask_dir / f"smoke_{idx:03d}_mask.png"
        cv2.imwrite(str(path), mask)
        rel = path.relative_to(project_root).as_posix()
        samples.append(
            {
                "sample_id": f"smoke_{idx:03d}",
                "dataset_id": "smoke_test",
                "split": "unknown",
                "image_path": None,
                "mask_path": rel,
                "available_labels": ["mask"],
                "research_use_only": True,
                "notes": "synthetic_smoke_test_only; not_research_dataset; not_accuracy_evidence",
            }
        )
    metadata = {
        "synthetic_smoke_test_only": True,
        "not_research_dataset": True,
        "not_accuracy_evidence": True,
    }
    (smoke_root / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    manifest_dir = project_root / "datasets/external/common/manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "smoke_test_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "dataset_id": "smoke_test",
                "source_url": None,
                "paper_url": None,
                "license_status": "unknown",
                "sample_count": len(samples),
                "file_inventory": {"masks": len(samples)},
                "label_types": ["mask"],
                "research_use_only": True,
                "issues": ["Smoke data is code-path-only and not external research evidence."],
                "samples": samples,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train research-only models from external dataset manifests.")
    parser.add_argument("--task", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--allow-smoke-data", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            train_research_model(
                args.task,
                args.dataset,
                limit=args.limit,
                epochs=args.epochs,
                allow_smoke_data=args.allow_smoke_data,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
