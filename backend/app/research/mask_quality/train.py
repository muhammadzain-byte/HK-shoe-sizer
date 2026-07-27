from __future__ import annotations

import json
import pickle
from collections import Counter
from pathlib import Path
from typing import Any

from app.research.mask_quality.dataset import load_mask_quality_dataset
from app.research.mask_quality.features import schema_payload
from app.research.mask_quality.model import CentroidMaskQualityModel, RuleBasedMaskQualityModel


def train_mask_quality_model(
    dataset_id: str,
    manifest_path: Path,
    project_root: Path,
    limit: int | None = None,
) -> dict[str, Any]:
    model_dir = project_root / "models/research/mask_quality"
    artifact_dir = project_root / "artifacts/training/mask_quality"
    model_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    features, labels, rows = load_mask_quality_dataset(manifest_path, project_root, limit=limit)
    feature_schema_path = model_dir / "feature_schema.json"
    feature_schema_path.write_text(json.dumps(schema_payload(), indent=2), encoding="utf-8")
    if not features:
        report = {
            "task": "mask_quality",
            "dataset_id": dataset_id,
            "trained": False,
            "status": "skipped",
            "reason": "No mask samples available.",
            "research_only": True,
        }
        _write_report(artifact_dir, report, {})
        (artifact_dir / "training_skipped_report.json").write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )
        return report

    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    class_counts = Counter(labels)
    try:
        model = CentroidMaskQualityModel.fit(features, labels)
        model_path = model_dir / "mask_quality_model.joblib"
        with model_path.open("wb") as handle:
            pickle.dump(model, handle)
        predictions = model.predict(features)
        model_type = "CentroidMaskQualityModel"
        trained = True
    except Exception as exc:
        model = RuleBasedMaskQualityModel()
        model_path = model_dir / "mask_quality_model.joblib"
        with model_path.open("wb") as handle:
            pickle.dump(model, handle)
        predictions = model.predict(features)
        model_type = "RuleBasedMaskQualityModel"
        trained = False
        fallback_reason = str(exc)
    confusion = _confusion(labels, predictions)
    report = {
        "task": "mask_quality",
        "dataset_id": dataset_id,
        "trained": trained,
        "status": "trained" if trained else "rule_based_fallback",
        "model_type": model_type,
        "model_path": str(model_path),
        "feature_schema_path": str(feature_schema_path),
        "sample_count": len(features),
        "source_sample_count": len(rows),
        "class_counts": dict(sorted(class_counts.items())),
        "trained_on": dataset_id,
        "synthetic_research_only": bool(manifest.get("synthetic_research_only")),
        "not_accuracy_evidence": bool(manifest.get("not_accuracy_evidence")),
        "research_only": True,
        "production_enabled": False,
    }
    if not trained:
        report["reason"] = f"Centroid training failed; wrote rule baseline. {fallback_reason}"
    _write_report(artifact_dir, report, confusion)
    return report


def _confusion(labels: list[str], predictions: list[str]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    for actual, predicted in zip(labels, predictions, strict=False):
        matrix.setdefault(actual, {})
        matrix[actual][predicted] = matrix[actual].get(predicted, 0) + 1
    return matrix


def _write_report(artifact_dir: Path, report: dict[str, Any], confusion: dict[str, Any]) -> None:
    (artifact_dir / "training_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (artifact_dir / "confusion_matrix.json").write_text(json.dumps(confusion, indent=2), encoding="utf-8")
