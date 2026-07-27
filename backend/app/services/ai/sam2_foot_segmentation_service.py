from functools import cached_property
from typing import Any

from PIL import Image

from app.core.config import settings
from app.services.ai.contracts import (
    SegmentedFoot,
    FootSegmentationService,
    SegmentationResult,
)
from app.services.ai.foot_candidate_selection_service import FootCandidateSelectionService
from app.services.ai.foot_region_refinement_service import FootRegionRefinementService


class SAM2FootSegmentationService(FootSegmentationService):
    """SAM 2-backed foot segmentation service.

    SAM 2 is class-agnostic. This service uses SAM 2 masks as the source of truth for
    object boundaries, then filters plausible foot candidates by size, confidence, and
    shape. A later classifier can be added without changing the validation API.
    """

    def __init__(
        self,
        model_id: str | None = None,
        device: str | None = None,
        min_mask_area_ratio: float | None = None,
        edge_margin_ratio: float | None = None,
        min_confidence: float | None = None,
    ):
        self.model_id = model_id or settings.sam2_model_id
        self.device = device or settings.sam2_device
        self.min_mask_area_ratio = min_mask_area_ratio or settings.sam2_min_mask_area_ratio
        self.edge_margin_ratio = edge_margin_ratio or settings.sam2_edge_margin_ratio
        self.min_confidence = min_confidence or settings.sam2_min_confidence
        self.candidate_selection_service = FootCandidateSelectionService(
            edge_margin_ratio=self.edge_margin_ratio
        )
        self.region_refinement_service = FootRegionRefinementService()

    @cached_property
    def _pipeline(self) -> Any:
        try:
            import torch
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError(
                "SAM 2 dependencies are not installed. Install torch and transformers."
            ) from exc

        device = self._resolve_device(torch)
        return pipeline("mask-generation", model=self.model_id, device=device)

    def segment(self, image: Image.Image) -> SegmentationResult:
        normalized = image.convert("RGB")
        raw_result = self._pipeline(normalized)
        masks = self._extract_masks(raw_result)
        selection = self.candidate_selection_service.select(masks, normalized.size)
        primary = self._refine_selected(selection.selected, normalized.size)

        return SegmentationResult(
            mask_uri=None,
            confidence_score=primary.confidence_score if primary else None,
            model_name=self.model_id,
            foot_count=1 if primary else 0,
            foot_bbox=primary.bbox if primary else None,
            edge_contact_detected=primary.touches_frame_edge if primary else False,
            feet=[primary] if primary else [],
        )

    def _refine_selected(
        self,
        selected: SegmentedFoot | None,
        image_size: tuple[int, int],
    ) -> SegmentedFoot | None:
        if selected is None or selected.mask is None:
            return selected
        try:
            refinement = self.region_refinement_service.refine(selected.mask, selected.bbox)
        except Exception as exc:
            diagnostics = dict(selected.diagnostics or {})
            diagnostics["refinement"] = {
                "refinement_confidence": 0.0,
                "issues": [f"refinement failed: {exc}"],
                "used_original_mask": True,
            }
            return SegmentedFoot(
                bbox=selected.bbox,
                confidence_score=selected.confidence_score,
                touches_frame_edge=selected.touches_frame_edge,
                area_pixels=selected.area_pixels,
                mask=selected.mask,
                diagnostics=diagnostics,
            )

        diagnostics = {
            "original_candidate": dict(selected.diagnostics or {}),
            "refinement": refinement.to_metadata(),
        }
        return SegmentedFoot(
            bbox=refinement.refined_bbox,
            confidence_score=selected.confidence_score,
            touches_frame_edge=self._touches_frame_edge(refinement.refined_bbox, image_size),
            area_pixels=int(refinement.refined_mask.sum()),
            mask=refinement.refined_mask,
            diagnostics=diagnostics,
        )

    def _resolve_device(self, torch_module: Any) -> int | str:
        if self.device == "cpu":
            return -1
        if self.device.startswith("cuda"):
            if torch_module.cuda.is_available():
                return 0
            return -1
        if self.device == "mps":
            if getattr(torch_module.backends, "mps", None) and torch_module.backends.mps.is_available():
                return "mps"
            return -1
        if torch_module.cuda.is_available():
            return 0
        return -1

    def _extract_masks(self, raw_result: Any) -> list[dict[str, Any]]:
        if isinstance(raw_result, dict):
            masks = self._first_present(raw_result, ("masks", "mask", "segmentation"), [])
            scores = self._first_present(raw_result, ("scores", "iou_scores", "stability_score"), [])
            masks = self._as_sequence(masks)
            scores = self._as_sequence(scores)
            return [
                {"mask": mask, "score": self._score_to_float(scores[index]) if index < len(scores) else None}
                for index, mask in enumerate(masks)
            ]

        if isinstance(raw_result, list):
            extracted = []
            for item in raw_result:
                if isinstance(item, dict):
                    mask = self._first_present(item, ("mask", "segmentation"))
                    score = self._first_present(item, ("score", "stability_score", "iou_score"))
                    extracted.append(
                        {
                            "mask": mask,
                            "score": self._score_to_float(score),
                        }
                    )
            return extracted

        return []

    def _first_present(
        self, mapping: dict[str, Any], keys: tuple[str, ...], default: Any = None
    ) -> Any:
        for key in keys:
            if key in mapping and mapping[key] is not None:
                return mapping[key]
        return default

    def _as_sequence(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if hasattr(value, "detach"):
            return list(value)
        if isinstance(value, list | tuple):
            return list(value)
        return [value]

    def _score_to_float(self, score: Any) -> float | None:
        if score is None:
            return None
        if hasattr(score, "detach"):
            score = score.detach().cpu()
            if hasattr(score, "numel") and score.numel() == 1:
                return float(score.item())
        try:
            return float(score)
        except (TypeError, ValueError):
            return None

    def _touches_frame_edge(self, bbox: Any, image_size: tuple[int, int]) -> bool:
        width, height = image_size
        margin_x = int(width * self.edge_margin_ratio)
        margin_y = int(height * self.edge_margin_ratio)
        return (
            bbox.x <= margin_x
            or bbox.y <= margin_y
            or bbox.x + bbox.width >= width - margin_x
            or bbox.y + bbox.height >= height - margin_y
        )
