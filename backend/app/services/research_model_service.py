from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import Any


class ResearchModelService:
    """Loads research models only for explicit debug use."""

    def __init__(self, project_root: Path | None = None, enabled: bool | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.enabled = (
            enabled
            if enabled is not None
            else os.getenv("ENABLE_RESEARCH_MODELS", "false").lower() == "true"
        )

    def is_enabled(self) -> bool:
        return bool(self.enabled)

    def load_registry(self) -> dict[str, Any]:
        path = self.project_root / "models/research/model_registry.json"
        if not path.exists():
            return {"models": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def score_mask_quality_debug(self, feature_vector: list[float]) -> dict[str, Any]:
        if not self.enabled:
            return {
                "enabled": False,
                "research_mask_quality_score": None,
                "issues": ["Research models are disabled."],
                "hard_gate_override": False,
            }
        model_path = self.project_root / "models/research/mask_quality/mask_quality_model.joblib"
        if not model_path.exists():
            return {
                "enabled": True,
                "research_mask_quality_score": None,
                "issues": ["Research mask quality model artifact is missing."],
                "hard_gate_override": False,
            }
        try:
            try:
                from joblib import load

                model = load(model_path)
            except Exception:
                with model_path.open("rb") as handle:
                    model = pickle.load(handle)
            prediction = model.predict([feature_vector])[0]
        except Exception as exc:
            return {
                "enabled": True,
                "research_mask_quality_score": None,
                "issues": [f"Research model could not score: {exc}"],
                "hard_gate_override": False,
            }
        return {
            "enabled": True,
            "research_mask_quality_score": 1.0 if prediction == "valid" else 0.0,
            "prediction": prediction,
            "issues": [],
            "hard_gate_override": False,
        }
