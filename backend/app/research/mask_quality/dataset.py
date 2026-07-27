from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2

from app.research.mask_quality.features import (
    extract_mask_quality_features,
    feature_vector,
    generate_synthetic_negatives,
)


def load_mask_quality_dataset(
    manifest_path: Path,
    project_root: Path,
    limit: int | None = None,
) -> tuple[list[list[float]], list[str], list[dict[str, Any]]]:
    if not manifest_path.exists():
        return [], [], []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    features: list[list[float]] = []
    labels: list[str] = []
    rows: list[dict[str, Any]] = []
    samples = manifest.get("samples") or []
    generated_labels = bool(manifest.get("synthetic_research_only")) and manifest.get("dataset_id") == "generated_foot_masks_from_focus"
    if limit is not None:
        samples = samples[:limit]
    for sample in samples:
        mask_path = sample.get("mask_path")
        if not mask_path:
            continue
        resolved = _resolve(project_root, mask_path)
        mask = cv2.imread(str(resolved), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            continue
        valid_features = extract_mask_quality_features(mask)
        features.append(feature_vector(valid_features))
        sample_label = str(sample.get("quality_label") or "valid")
        labels.append(sample_label)
        rows.append({"sample_id": sample.get("sample_id"), "label": sample_label, "features": valid_features})
        if generated_labels:
            continue
        for label, negative in generate_synthetic_negatives(mask):
            negative_features = extract_mask_quality_features(negative)
            features.append(feature_vector(negative_features))
            labels.append(label)
            rows.append({"sample_id": sample.get("sample_id"), "label": label, "features": negative_features})
    return features, labels, rows


def _resolve(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path
