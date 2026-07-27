from app.research.synthetic_foot_renderer.augmentation import QUALITY_LABELS

VALID_LABEL = "valid"
DAMAGED_LABELS = [label for label in QUALITY_LABELS if label != VALID_LABEL]

__all__ = ["DAMAGED_LABELS", "QUALITY_LABELS", "VALID_LABEL"]
