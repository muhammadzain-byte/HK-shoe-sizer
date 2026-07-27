from __future__ import annotations

from pathlib import Path
from typing import Any

from app.research.mask_quality.dataset import load_mask_quality_dataset


def evaluate_mask_quality_model(
    manifest_path: Path,
    project_root: Path,
    limit: int | None = None,
) -> dict[str, Any]:
    features, labels, _rows = load_mask_quality_dataset(manifest_path, project_root, limit=limit)
    return {
        "task": "mask_quality",
        "evaluated": bool(features),
        "sample_count": len(features),
        "label_count": len(set(labels)),
        "research_only": True,
    }
