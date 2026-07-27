from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.external_dataset_service import ExternalDatasetService  # noqa: E402


TRAINING_TASK_LABELS = {
    "mask_quality": {"image", "mask"},
    "segmentation_baseline": {"image", "mask"},
    "landmark_research": {"image", "keypoints"},
    "surface_normal_research": {"image", "normal"},
    "point_cloud_research": {"point_cloud"},
    "mesh_reconstruction_research": {"mesh"},
}


def check_population(project_root: Path | None = None) -> dict[str, Any]:
    service = ExternalDatasetService(project_root=project_root)
    external_root = service.project_root / "datasets/external"
    datasets: dict[str, Any] = {}
    issues: list[str] = []
    instructions: list[str] = []
    ready_for_training = False

    for entry in service.load_registry():
        inspection = service.inspect_dataset(entry.id)
        manifest_path = service.manifest_path(entry.id)
        manifest = _load_manifest(manifest_path)
        sample_count = int((manifest or {}).get("sample_count") or 0)
        converted_count = _converted_count(service.project_root, entry.id)
        supported_tasks = _supported_tasks(manifest or {})
        mask_sample_count = _mask_sample_count(manifest or {})
        status = _status(
            inspection.raw_file_count,
            inspection.processed_file_count,
            manifest_path.exists(),
            sample_count,
            converted_count,
            supported_tasks,
        )
        if status == "training_ready":
            ready_for_training = True
        datasets[entry.id] = {
            "raw_file_count": inspection.raw_file_count,
            "processed_file_count": inspection.processed_file_count,
            "manifest_exists": manifest_path.exists(),
            "sample_count": sample_count,
            "mask_sample_count": mask_sample_count,
            "converted_sample_count": converted_count,
            "supported_training_tasks": supported_tasks,
            "status": status,
            "synthetic_research_only": bool((manifest or {}).get("synthetic_research_only")),
            "not_accuracy_evidence": bool((manifest or {}).get("not_accuracy_evidence")),
        }
        if status == "empty":
            instructions.append(f"{entry.id}: download or place files under {entry.local_raw_dir}.")
        issues.extend(inspection.issues)

    return {
        "external_root_exists": external_root.exists(),
        "datasets": datasets,
        "ready_for_training": ready_for_training,
        "issues": sorted(set(issues)),
        "instructions": instructions,
    }


def _load_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _converted_count(project_root: Path, dataset_id: str) -> int:
    root = project_root / "datasets/external/common/processed" / dataset_id
    if not root.exists():
        return 0
    return len([path for path in root.glob("*.json") if path.is_file()])


def _supported_tasks(manifest: dict[str, Any]) -> list[str]:
    tasks = set()
    for sample in manifest.get("samples") or []:
        labels = set(sample.get("available_labels") or [])
        for task, required in TRAINING_TASK_LABELS.items():
            if required.issubset(labels):
                tasks.add(task)
    return sorted(tasks)


def _mask_sample_count(manifest: dict[str, Any]) -> int:
    explicit = manifest.get("mask_sample_count")
    if explicit is not None:
        return int(explicit)
    return sum(1 for sample in manifest.get("samples") or [] if sample.get("mask_path"))


def _status(
    raw_count: int,
    processed_count: int,
    manifest_exists: bool,
    sample_count: int,
    converted_count: int,
    tasks: list[str],
) -> str:
    if tasks and manifest_exists and sample_count > 0:
        return "training_ready"
    if converted_count > 0:
        return "converted"
    if manifest_exists and sample_count > 0:
        return "manifest_ready"
    if raw_count > 0 or processed_count > 0:
        return "downloaded"
    return "empty"


def main() -> None:
    print(json.dumps(check_population(), indent=2))


if __name__ == "__main__":
    main()
