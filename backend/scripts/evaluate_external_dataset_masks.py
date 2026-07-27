from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def evaluate_masks(dataset_id: str, manifest_path: Path, limit: int = 10) -> dict[str, Any]:
    if not manifest_path.exists():
        return _write_result(
            dataset_id,
            {
                "dataset_id": dataset_id,
                "sample_count": 0,
                "evaluated_count": 0,
                "issues": ["Manifest not found."],
                "mask_stats": [],
            },
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = manifest.get("samples") or []
    if not samples:
        return _write_result(
            dataset_id,
            {
                "dataset_id": dataset_id,
                "sample_count": 0,
                "evaluated_count": 0,
                "issues": ["Manifest has no samples."],
                "mask_stats": [],
            },
        )

    stats = []
    issues: list[str] = []
    for sample in samples[:limit]:
        mask_path = sample.get("mask_path")
        if not mask_path:
            continue
        resolved = _resolve(mask_path)
        if not resolved.exists():
            issues.append(f"Mask not found: {mask_path}")
            continue
        mask = cv2.imread(str(resolved), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            issues.append(f"Mask could not be read: {mask_path}")
            continue
        stats.append(_mask_stats(sample.get("sample_id", resolved.stem), mask))

    return _write_result(
        dataset_id,
        {
            "dataset_id": dataset_id,
            "sample_count": len(samples),
            "evaluated_count": len(stats),
            "issues": issues,
            "mask_stats": stats,
        },
    )


def _mask_stats(sample_id: str, mask: np.ndarray) -> dict[str, Any]:
    binary = (mask > 0).astype(np.uint8)
    area = int(np.count_nonzero(binary))
    image_area = int(binary.size)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours or area == 0:
        return {
            "sample_id": sample_id,
            "mask_area_ratio": 0.0,
            "bbox_aspect_ratio": 0.0,
            "toe_region_complexity": 0.0,
            "contour_point_count": 0,
            "rectangularity": 0.0,
            "solidity": 0.0,
        }
    contour = max(contours, key=cv2.contourArea)
    x, y, width, height = cv2.boundingRect(contour)
    bbox_area = max(width * height, 1)
    hull = cv2.convexHull(contour)
    hull_area = max(float(cv2.contourArea(hull)), 1.0)
    return {
        "sample_id": sample_id,
        "mask_area_ratio": round(area / max(image_area, 1), 6),
        "bbox_aspect_ratio": round(height / max(width, 1), 4),
        "toe_region_complexity": 0.0,
        "contour_point_count": int(len(contour)),
        "rectangularity": round(area / bbox_area, 4),
        "solidity": round(area / hull_area, 4),
    }


def _write_result(dataset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    output_dir = PROJECT_ROOT / "datasets/external/common/reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{dataset_id}_mask_stats.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate basic mask stats from an external dataset manifest.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(evaluate_masks(args.dataset, Path(args.manifest), args.limit), indent=2))


if __name__ == "__main__":
    main()
