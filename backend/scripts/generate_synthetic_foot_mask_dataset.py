from __future__ import annotations

import argparse
import json
import sys
import shutil
from pathlib import Path
from typing import Any

import cv2
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.research.synthetic_foot_renderer.augmentation import QUALITY_LABELS, augment_mask  # noqa: E402
from app.research.synthetic_foot_renderer.manifest import DATASET_ID, write_generated_manifest  # noqa: E402
from app.research.synthetic_foot_renderer.mesh_loader import load_mesh_points  # noqa: E402
from app.research.synthetic_foot_renderer.projection_renderer import render_top_down, rgb_from_mask  # noqa: E402


def generate_dataset(
    source: str = "focus_synfoot2_foot3d",
    count: int = 1000,
    seed: int = 42,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    root = project_root / "datasets/external/generated_foot_masks"
    image_dir = root / "images"
    mask_dir = root / "masks"
    metadata_dir = root / "metadata"
    report_dir = root / "reports"
    for folder in [image_dir, mask_dir, metadata_dir, report_dir]:
        folder.mkdir(parents=True, exist_ok=True)
    _clear_payload_dirs([image_dir, mask_dir, metadata_dir])

    mesh_samples = _load_mesh_samples(project_root, source)
    issues: list[str] = []
    if not mesh_samples:
        issues.append("No FOCUS mesh samples found. Generate/convert the FOCUS manifest first.")
        manifest = write_generated_manifest(project_root, [], issues)
        report = _report(source, 0, 0, manifest, issues)
        _write_report(report_dir, report)
        return report

    base_renders = _render_source_assets(project_root, mesh_samples, seed, issues)
    if not base_renders:
        issues.append("No usable FOCUS mesh renders could be created.")
        manifest = write_generated_manifest(project_root, [], issues[:50])
        report = _report(source, len(mesh_samples), 0, manifest, issues[:50])
        _write_report(report_dir, report)
        return report

    samples: list[dict[str, Any]] = []
    source_assets_used: set[str] = set()
    index = 0
    attempts = 0
    max_attempts = max(count * 3, len(mesh_samples))
    while len(samples) < count and attempts < max_attempts:
        attempts += 1
        mesh_sample, base_mask = base_renders[index % len(base_renders)]
        label = QUALITY_LABELS[index % len(QUALITY_LABELS)]
        index += 1
        mask, augmentations = augment_mask(base_mask, label)
        if mask.max() == 0:
            issues.append(f"{mesh_sample['sample_id']}: augmentation {label} produced an empty mask.")
            continue
        image = rgb_from_mask(mask)
        generated_id = f"focus_{len(samples):05d}_{_safe_id(mesh_sample['sample_id'])}_{label}"
        image_path = image_dir / f"{generated_id}.png"
        mask_path = mask_dir / f"{generated_id}_mask.png"
        metadata_path = metadata_dir / f"{generated_id}.json"
        cv2.imwrite(str(image_path), image)
        cv2.imwrite(str(mask_path), mask)
        sample = {
            "sample_id": generated_id,
            "dataset_id": DATASET_ID,
            "source_asset": mesh_sample["mesh_path"],
            "image_path": _rel(project_root, image_path),
            "mask_path": _rel(project_root, mask_path),
            "quality_label": label,
            "render_type": "mesh_projection",
            "view": "top_down",
            "synthetic_research_only": True,
            "not_accuracy_evidence": True,
            "available_labels": ["image", "mask", "quality_label"],
            "research_tasks": ["mask_quality", "segmentation_baseline"],
            "augmentations": augmentations,
            "research_use_only": True,
        }
        metadata_path.write_text(json.dumps(sample, indent=2), encoding="utf-8")
        samples.append(sample)
        source_assets_used.add(mesh_sample["mesh_path"])

    manifest = write_generated_manifest(project_root, samples, issues[:50])
    report = _report(source, len(mesh_samples), len(source_assets_used), manifest, issues[:50])
    _write_report(report_dir, report)
    return report


def _render_source_assets(
    project_root: Path,
    mesh_samples: list[dict[str, Any]],
    seed: int,
    issues: list[str],
) -> list[tuple[dict[str, Any], np.ndarray]]:
    rendered: list[tuple[dict[str, Any], np.ndarray]] = []
    for idx, mesh_sample in enumerate(mesh_samples):
        mesh_path = _resolve(project_root, mesh_sample["mesh_path"])
        load_result = load_mesh_points(mesh_path)
        if load_result.issues or load_result.points.shape[0] < 3:
            issues.extend([f"{mesh_sample['sample_id']}: {issue}" for issue in load_result.issues])
            continue
        render = render_top_down(load_result.points, seed=seed + idx)
        if render.issues or render.mask.max() == 0:
            issues.extend([f"{mesh_sample['sample_id']}: {issue}" for issue in render.issues])
            continue
        rendered.append((mesh_sample, render.mask))
    return rendered


def _load_mesh_samples(project_root: Path, source: str) -> list[dict[str, Any]]:
    manifest_path = project_root / "datasets/external/common/manifests" / f"{source}_manifest.json"
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = []
    for sample in manifest.get("samples") or []:
        if sample.get("mesh_path") and "mesh" in (sample.get("available_labels") or []):
            samples.append({"sample_id": str(sample.get("sample_id")), "mesh_path": str(sample.get("mesh_path"))})
    return samples


def _clear_payload_dirs(folders: list[Path]) -> None:
    for folder in folders:
        for path in folder.glob("*"):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)


def _report(source: str, source_found: int, source_used: int, manifest: dict[str, Any], issues: list[str]) -> dict[str, Any]:
    class_counts = manifest.get("class_counts") or {}
    return {
        "dataset_id": DATASET_ID,
        "source_dataset_id": source,
        "source_assets_found": source_found,
        "source_assets_used": source_used,
        "generated_sample_count": manifest.get("sample_count", 0),
        "mask_sample_count": manifest.get("mask_sample_count", 0),
        "class_counts": class_counts,
        "manifest_path": "datasets/external/generated_foot_masks/manifests/generated_foot_masks_manifest.json",
        "common_manifest_path": "datasets/external/common/manifests/generated_foot_masks_from_focus_manifest.json",
        "synthetic_research_only": True,
        "not_accuracy_evidence": True,
        "production_enabled": False,
        "issues": issues,
        "class_count_total": int(sum(class_counts.values())) if class_counts else 0,
    }


def _write_report(report_dir: Path, report: dict[str, Any]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "generation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def _resolve(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _rel(project_root: Path, value: Path) -> str:
    return value.relative_to(project_root).as_posix()


def _safe_id(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")[:80]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic RGB/mask foot dataset from FOCUS mesh samples.")
    parser.add_argument("--source", default="focus_synfoot2_foot3d")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(generate_dataset(args.source, args.count, args.seed), indent=2))


if __name__ == "__main__":
    main()
