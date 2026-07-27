from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from PIL import Image

from app.services.ai.contracts import BoundingBox, SegmentedFoot


@dataclass(frozen=True)
class CandidateDiagnostics:
    index: int
    source_index: int
    source: str
    bbox: BoundingBox
    area_pixels: int
    area_ratio: float
    bbox_area_ratio: float
    aspect_ratio: float
    solidity: float
    elongation: float
    toe_score: float
    visible_toe_count: int
    forefoot_score: float
    heel_score: float
    ankle_rejection_score: float
    leg_rejection_score: float
    shape_score: float
    score_breakdown: dict[str, float]
    profile: dict[str, float]
    orientation: str
    sam_score: float | None
    candidate_score: float
    rejected: bool
    rejection_reason: str | None


@dataclass(frozen=True)
class FootShapeAnalysis:
    toe_score: float
    visible_toe_count: int
    forefoot_score: float
    heel_score: float
    ankle_rejection_score: float
    leg_rejection_score: float
    shape_score: float
    final_score: float
    rejection_reasons: tuple[str, ...]
    orientation: str
    profile: dict[str, float]


@dataclass(frozen=True)
class FootCandidateSelectionResult:
    selected: SegmentedFoot | None
    candidates: list[CandidateDiagnostics]
    candidate_masks: list[Any]


class FootShapeAnalyzer:
    """Scores candidate masks using toe-to-heel anatomical width profiles."""

    def analyze(
        self,
        mask: Any,
        bbox: BoundingBox,
        *,
        area_ratio: float,
        bbox_area_ratio: float,
        solidity: float,
        elongation: float,
    ) -> FootShapeAnalysis:
        top = self._analyze_orientation(
            mask,
            bbox,
            area_ratio=area_ratio,
            bbox_area_ratio=bbox_area_ratio,
            solidity=solidity,
            elongation=elongation,
            toes_at_top=True,
        )
        bottom = self._analyze_orientation(
            mask,
            bbox,
            area_ratio=area_ratio,
            bbox_area_ratio=bbox_area_ratio,
            solidity=solidity,
            elongation=elongation,
            toes_at_top=False,
        )
        return top if top.final_score >= bottom.final_score else bottom

    def _analyze_orientation(
        self,
        mask: Any,
        bbox: BoundingBox,
        *,
        area_ratio: float,
        bbox_area_ratio: float,
        solidity: float,
        elongation: float,
        toes_at_top: bool,
    ) -> FootShapeAnalysis:
        import numpy as np

        crop = mask[bbox.y : bbox.y + bbox.height, bbox.x : bbox.x + bbox.width]
        if not toes_at_top:
            crop = np.flipud(crop)

        widths, centers = self._width_profile(crop)
        active_widths = widths[widths > 0]
        if widths.size == 0 or active_widths.size == 0:
            return FootShapeAnalysis(0, 0, 0, 0, 1, 1, 0, 0, ("empty candidate",), "unknown", {})

        smooth_widths = self._smooth(widths, max(5, bbox.height // 45))
        positive_smooth = smooth_widths[smooth_widths > 0]
        max_width = max(float(positive_smooth.max()), 1.0)
        mean_width = max(float(positive_smooth.mean()), 1.0)

        toe_tip_width = self._band_percentile(smooth_widths, 0.00, 0.10, 60)
        toe_width = self._band_percentile(smooth_widths, 0.02, 0.26, 78)
        forefoot_width = self._band_percentile(smooth_widths, 0.20, 0.44, 92)
        midfoot_width = self._band_percentile(smooth_widths, 0.45, 0.68, 45)
        heel_width = self._band_percentile(smooth_widths, 0.68, 0.84, 58)
        ankle_width = self._band_percentile(smooth_widths, 0.84, 1.00, 70)
        lower_mean_width = self._band_percentile(smooth_widths, 0.72, 1.00, 55)
        width_variation = float(positive_smooth.std() / mean_width)
        center_drift = self._center_drift_score(centers, smooth_widths)
        lower_cylindrical = self._cylindrical_band_score(smooth_widths, 0.62, 1.00)

        visible_toe_count, toe_peak_strength, toe_separation = self._toe_peak_features(crop)
        toe_count_score = min(visible_toe_count / 4.0, 1.0)
        toe_presence_score = self._ramp_score(toe_width / max_width, low=0.30, high=0.68)
        toe_tip_expansion = self._ramp_score(toe_width / max(toe_tip_width, 1.0), low=1.05, high=1.55)
        toe_score = max(
            0.0,
            min(
                1.0,
                0.42 * toe_count_score
                + 0.28 * toe_peak_strength
                + 0.18 * toe_separation
                + 0.12 * max(toe_presence_score, toe_tip_expansion),
            ),
        )

        forefoot_to_midfoot = forefoot_width / max(midfoot_width, 1.0)
        forefoot_to_toe = forefoot_width / max(toe_width, 1.0)
        forefoot_to_ankle = forefoot_width / max(ankle_width, 1.0)
        forefoot_score = max(
            0.0,
            min(
                1.0,
                0.42 * self._ramp_score(forefoot_to_midfoot, low=1.04, high=1.34)
                + 0.24 * self._ramp_score(forefoot_to_toe, low=0.92, high=1.20)
                + 0.22 * self._ramp_score(forefoot_to_ankle, low=1.04, high=1.35)
                + 0.12 * self._ratio_score(forefoot_width / max_width, target=0.92, tolerance=0.34),
            ),
        )

        heel_to_forefoot = heel_width / max(forefoot_width, 1.0)
        heel_to_ankle = heel_width / max(ankle_width, 1.0)
        heel_score = max(
            0.0,
            min(
                1.0,
                0.58 * self._ratio_score(heel_to_forefoot, target=0.66, tolerance=0.30)
                + 0.26 * self._ramp_score(heel_to_ankle, low=0.88, high=1.20)
                + 0.16 * self._inverse_ramp_score(abs(heel_width - lower_mean_width) / max_width, low=0.02, high=0.20),
            ),
        )

        ankle_to_forefoot = ankle_width / max(forefoot_width, 1.0)
        ankle_rejection_score = max(
            0.0,
            min(
                1.0,
                0.52 * self._ramp_score(ankle_to_forefoot, low=0.74, high=1.02)
                + 0.28 * self._inverse_ramp_score(forefoot_to_ankle, low=1.02, high=1.35)
                + 0.20 * lower_cylindrical,
            ),
        )

        global_cylindrical = self._inverse_ramp_score(width_variation, low=0.08, high=0.25)
        missing_toe_penalty = self._inverse_ramp_score(toe_score, low=0.34, high=0.58)
        missing_waist_penalty = self._inverse_ramp_score(forefoot_to_midfoot, low=1.02, high=1.28)
        leg_rejection_score = max(
            0.0,
            min(
                1.0,
                0.36 * global_cylindrical
                + 0.25 * lower_cylindrical
                + 0.22 * missing_toe_penalty
                + 0.17 * missing_waist_penalty,
            ),
        )

        area_score = self._ratio_score(area_ratio, target=0.16, tolerance=0.20)
        bbox_score = self._ratio_score(bbox_area_ratio, target=0.22, tolerance=0.27)
        solidity_score = self._ratio_score(solidity, target=0.86, tolerance=0.28)
        elongation_score = self._ratio_score(elongation, target=2.05, tolerance=1.10)
        geometry_score = max(
            0.0,
            min(
                1.0,
                0.24 * area_score
                + 0.20 * bbox_score
                + 0.20 * solidity_score
                + 0.17 * elongation_score
                + 0.19 * center_drift,
            ),
        )

        anatomy_score = (
            0.34 * toe_score
            + 0.28 * forefoot_score
            + 0.18 * heel_score
            + 0.20 * geometry_score
        )
        rejection_penalty = 0.28 * ankle_rejection_score + 0.34 * leg_rejection_score
        final_score = max(0.0, min(0.99, anatomy_score - rejection_penalty))

        rejection_reasons = []
        if visible_toe_count < 2 or toe_score < 0.42:
            rejection_reasons.append("missing visible toe-like peaks")
        if forefoot_score < 0.34:
            rejection_reasons.append("missing forefoot expansion")
        if heel_score < 0.28:
            rejection_reasons.append("missing plausible heel taper")
        if ankle_rejection_score >= 0.68:
            rejection_reasons.append("contains ankle/lower-leg continuation")
        if leg_rejection_score >= 0.62:
            rejection_reasons.append("mostly cylindrical lower-leg shape")
        if toe_score < 0.48 and forefoot_score < 0.48:
            rejection_reasons.append("does not contain a plausible toe/forefoot region")

        profile = {
            "toe_tip_width": round(float(toe_tip_width), 4),
            "toe_width": round(float(toe_width), 4),
            "forefoot_width": round(float(forefoot_width), 4),
            "midfoot_width": round(float(midfoot_width), 4),
            "heel_width": round(float(heel_width), 4),
            "ankle_width": round(float(ankle_width), 4),
            "lower_mean_width": round(float(lower_mean_width), 4),
            "forefoot_to_midfoot": round(float(forefoot_to_midfoot), 4),
            "forefoot_to_toe": round(float(forefoot_to_toe), 4),
            "forefoot_to_ankle": round(float(forefoot_to_ankle), 4),
            "heel_to_forefoot": round(float(heel_to_forefoot), 4),
            "ankle_to_forefoot": round(float(ankle_to_forefoot), 4),
            "width_variation": round(float(width_variation), 4),
            "center_drift_score": round(float(center_drift), 4),
            "lower_cylindrical_score": round(float(lower_cylindrical), 4),
        }
        return FootShapeAnalysis(
            toe_score=toe_score,
            visible_toe_count=visible_toe_count,
            forefoot_score=forefoot_score,
            heel_score=heel_score,
            ankle_rejection_score=ankle_rejection_score,
            leg_rejection_score=leg_rejection_score,
            shape_score=geometry_score,
            final_score=final_score,
            rejection_reasons=tuple(rejection_reasons),
            orientation="toes_top" if toes_at_top else "toes_bottom",
            profile=profile,
        )

    def derive_profile_candidates(self, mask: Any) -> list[tuple[Any, str]]:
        import numpy as np

        if mask is None or not mask.any():
            return []

        derived = []
        ys, xs = np.where(mask)
        min_y, max_y = int(ys.min()), int(ys.max())
        min_x, max_x = int(xs.min()), int(xs.max())
        height = max_y - min_y + 1
        width = max_x - min_x + 1
        if height < 24 or width < 24:
            return derived

        for toes_at_top, source in ((True, "profile_foot_top"), (False, "profile_foot_bottom")):
            crop = mask[min_y : max_y + 1, min_x : max_x + 1]
            oriented = crop if toes_at_top else np.flipud(crop)
            widths, _ = self._width_profile(oriented)
            if widths.size == 0 or widths.max() <= 0:
                continue
            smooth = self._smooth(widths, max(5, height // 45))
            peak_start = int(height * 0.14)
            peak_end = max(peak_start + 1, int(height * 0.48))
            forefoot_peak = int(np.argmax(smooth[peak_start:peak_end]) + peak_start)
            search_start = min(height - 1, forefoot_peak + int(height * 0.14))
            search_end = max(search_start + 1, int(height * 0.90))
            if search_end <= search_start:
                continue
            valley = int(np.argmin(smooth[search_start:search_end]) + search_start)
            if smooth[valley] > smooth[forefoot_peak] * 0.88:
                continue

            cut_offsets = (-0.03, 0.02, 0.07)
            for offset_index, offset in enumerate(cut_offsets):
                cut = int(valley + height * offset)
                if cut < int(height * 0.48) or cut >= height - 3:
                    continue
                if toes_at_top:
                    candidate = mask.copy()
                    candidate[min_y + cut :, :] = False
                else:
                    candidate = mask.copy()
                    candidate[: max_y - cut + 1, :] = False
                if candidate.sum() > 50:
                    derived.append((candidate, f"{source}_cut{offset_index + 1}"))

        return derived

    def _width_profile(self, crop: Any) -> tuple[Any, Any]:
        import numpy as np

        height = crop.shape[0]
        widths = np.zeros(height, dtype=float)
        centers = np.full(height, np.nan, dtype=float)
        for row_index in range(height):
            columns = np.flatnonzero(crop[row_index])
            if columns.size == 0:
                continue
            widths[row_index] = float(columns[-1] - columns[0] + 1)
            centers[row_index] = float((columns[-1] + columns[0]) / 2.0)
        return widths, centers

    def _toe_peak_features(self, crop: Any) -> tuple[int, float, float]:
        height, width = crop.shape
        if height < 8 or width < 8:
            return 0, 0.0, 0.0
        toe_crop = crop[: max(6, int(height * 0.27)), :]
        min_run = max(3, int(width * 0.030))
        max_runs = 0
        run_rows = 0
        for row in toe_crop:
            runs = self._active_runs(row, min_run=min_run)
            if runs:
                run_rows += 1
                max_runs = max(max_runs, len(runs))

        column_density = toe_crop.sum(axis=0).astype(float)
        if float(column_density.max()) <= 0:
            return 0, 0.0, 0.0
        smoothed = self._smooth(column_density, max(3, width // 40))
        threshold = max(2.0, float(smoothed.max()) * 0.25)
        active = smoothed >= threshold
        density_runs = self._active_runs(active, min_run=min_run)
        visible_toe_count = max(max_runs, len(density_runs))
        density_variation = float(smoothed.std() / max(smoothed.mean(), 1.0))
        row_presence = run_rows / max(toe_crop.shape[0], 1)
        peak_strength = max(
            0.0,
            min(1.0, 0.56 * min(density_variation / 1.35, 1.0) + 0.44 * min(row_presence / 0.72, 1.0)),
        )
        separation_score = min(len(density_runs) / 4.0, 1.0)
        return int(min(visible_toe_count, 5)), peak_strength, separation_score

    def _active_runs(self, values: Any, *, min_run: int) -> list[tuple[int, int]]:
        import numpy as np

        active = np.asarray(values).astype(bool)
        runs = []
        start = None
        for index, value in enumerate(active):
            if value and start is None:
                start = index
            elif not value and start is not None:
                if index - start >= min_run:
                    runs.append((start, index - 1))
                start = None
        if start is not None and len(active) - start >= min_run:
            runs.append((start, len(active) - 1))
        return runs

    def _band_percentile(self, values: Any, start: float, end: float, percentile: float) -> float:
        import numpy as np

        lower = int(len(values) * start)
        upper = max(lower + 1, int(len(values) * end))
        band = values[lower:upper]
        band = band[band > 0]
        if band.size == 0:
            return 0.0
        return float(np.percentile(band, percentile))

    def _smooth(self, values: Any, window: int) -> Any:
        import numpy as np

        window = max(1, int(window))
        if window <= 1:
            return values.astype(float)
        kernel = np.ones(window, dtype=float) / window
        return np.convolve(values.astype(float), kernel, mode="same")

    def _center_drift_score(self, centers: Any, widths: Any) -> float:
        import numpy as np

        active = (~np.isnan(centers)) & (widths > 0)
        if active.sum() < 3:
            return 0.0
        normalized_drift = float(np.nanstd(centers[active]) / max(np.nanmean(widths[active]), 1.0))
        return self._inverse_ramp_score(normalized_drift, low=0.08, high=0.45)

    def _cylindrical_band_score(self, widths: Any, start: float, end: float) -> float:
        lower = int(len(widths) * start)
        upper = max(lower + 1, int(len(widths) * end))
        band = widths[lower:upper]
        band = band[band > 0]
        if band.size < 4:
            return 0.0
        variation = float(band.std() / max(band.mean(), 1.0))
        return self._inverse_ramp_score(variation, low=0.04, high=0.20)

    def _ratio_score(self, value: float, target: float, tolerance: float) -> float:
        return max(0.0, min(1.0, 1.0 - abs(value - target) / tolerance))

    def _ramp_score(self, value: float, low: float, high: float) -> float:
        if value <= low:
            return 0.0
        if value >= high:
            return 1.0
        return (value - low) / (high - low)

    def _inverse_ramp_score(self, value: float, low: float, high: float) -> float:
        if value <= low:
            return 1.0
        if value >= high:
            return 0.0
        return 1.0 - (value - low) / (high - low)


class FootCandidateSelectionService:
    def __init__(self, edge_margin_ratio: float = 0.03):
        self.edge_margin_ratio = edge_margin_ratio
        self.shape_analyzer = FootShapeAnalyzer()

    def select(
        self, masks: list[dict[str, Any]], image_size: tuple[int, int]
    ) -> FootCandidateSelectionResult:
        normalized_masks = [
            {
                "mask": self.normalize_mask(mask_item.get("mask")),
                "score": self._score_to_float(mask_item.get("score")),
                "source_index": index,
            }
            for index, mask_item in enumerate(masks)
            if mask_item.get("mask") is not None
        ]

        raw_candidates = []
        for item in normalized_masks:
            mask = item["mask"]
            source_index = item["source_index"]
            score = item["score"]
            raw_candidates.append((mask, source_index, "sam_mask", score))
            raw_candidates.extend(
                (derived, source_index, source, score)
                for derived, source in self._derive_sub_candidates(mask)
            )
            raw_candidates.extend(
                (derived, source_index, source, score)
                for derived, source in self.shape_analyzer.derive_profile_candidates(mask)
            )
            inverse_mask = ~mask
            raw_candidates.append((inverse_mask, source_index, "inverse_sam_mask", score))
            raw_candidates.extend(
                (derived, source_index, f"inverse_{source}", score)
                for derived, source in self._derive_sub_candidates(inverse_mask)
            )

        diagnostics: list[CandidateDiagnostics] = []
        diagnostic_masks: list[Any] = []
        accepted: list[tuple[CandidateDiagnostics, Any]] = []
        for index, (mask, source_index, source, sam_score) in enumerate(raw_candidates):
            diagnostic = self._score_candidate(
                index=index,
                source_index=source_index,
                source=source,
                mask=mask,
                sam_score=sam_score,
                image_size=image_size,
            )
            if diagnostic is None:
                continue
            diagnostics.append(diagnostic)
            diagnostic_masks.append(mask)
            if not diagnostic.rejected:
                accepted.append((diagnostic, mask))

        if not accepted:
            return FootCandidateSelectionResult(selected=None, candidates=diagnostics, candidate_masks=diagnostic_masks)

        best_diagnostic, best_mask = max(accepted, key=lambda item: item[0].candidate_score)
        selected = SegmentedFoot(
            bbox=best_diagnostic.bbox,
            confidence_score=Decimal(str(round(best_diagnostic.candidate_score, 4))),
            touches_frame_edge=self._touches_frame_edge(best_diagnostic.bbox, image_size),
            area_pixels=best_diagnostic.area_pixels,
            mask=best_mask,
            diagnostics=best_diagnostic.__dict__,
        )
        return FootCandidateSelectionResult(
            selected=selected,
            candidates=diagnostics,
            candidate_masks=diagnostic_masks,
        )

    def normalize_mask(self, mask: Any):
        import numpy as np

        if mask is None:
            return None
        if hasattr(mask, "detach"):
            mask = mask.detach().cpu().numpy()
        elif isinstance(mask, Image.Image):
            mask = np.asarray(mask)
        array = np.asarray(mask)
        if array.ndim == 3:
            array = array.squeeze()
        if array.ndim != 2:
            return None
        return array.astype(bool)

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

    def _derive_sub_candidates(self, mask: Any) -> list[tuple[Any, str]]:
        import numpy as np

        if mask is None or not mask.any():
            return []

        components = self._connected_components(mask)
        derived = [(component, "component") for component in components if component.sum() > 25]

        ys, xs = np.where(mask)
        if len(xs) == 0:
            return derived
        min_y, max_y = int(ys.min()), int(ys.max())
        height = max_y - min_y + 1
        lower = mask.copy()
        lower[: min_y + int(height * 0.45), :] = False
        if lower.sum() > 25:
            lower_ys, lower_xs = np.where(lower)
            split_x = self._vertical_valley_split(
                lower,
                int(lower_xs.min()),
                int(lower_xs.max()),
            )
            left = lower.copy()
            left[:, split_x:] = False
            right = lower.copy()
            right[:, :split_x] = False
            if left.sum() > 25:
                derived.append((left, "lower_left_split"))
            if right.sum() > 25:
                derived.append((right, "lower_right_split"))

        return derived

    def _score_candidate(
        self,
        index: int,
        source_index: int,
        source: str,
        mask: Any,
        sam_score: float | None,
        image_size: tuple[int, int],
    ) -> CandidateDiagnostics | None:
        import numpy as np

        if mask is None or not mask.any():
            return None

        width, height = image_size
        image_area = width * height
        ys, xs = np.where(mask)
        bbox = BoundingBox(
            x=int(xs.min()),
            y=int(ys.min()),
            width=int(xs.max() - xs.min() + 1),
            height=int(ys.max() - ys.min() + 1),
        )
        area = int(mask.sum())
        area_ratio = area / image_area
        bbox_area_ratio = (bbox.width * bbox.height) / image_area
        aspect_ratio = bbox.width / max(bbox.height, 1)
        solidity = area / max(self._convex_hull_area(list(zip(xs.tolist(), ys.tolist()))), 1)
        elongation = max(bbox.width, bbox.height) / max(min(bbox.width, bbox.height), 1)
        shape_analysis = self.shape_analyzer.analyze(
            mask,
            bbox,
            area_ratio=area_ratio,
            bbox_area_ratio=bbox_area_ratio,
            solidity=solidity,
            elongation=elongation,
        )
        candidate_score = self._candidate_score(
            area_ratio=area_ratio,
            bbox_area_ratio=bbox_area_ratio,
            aspect_ratio=aspect_ratio,
            solidity=solidity,
            elongation=elongation,
            shape_analysis=shape_analysis,
            sam_score=sam_score,
            source=source,
        )
        rejection_reason = self._rejection_reason(
            source=source,
            bbox=bbox,
            area_ratio=area_ratio,
            bbox_area_ratio=bbox_area_ratio,
            aspect_ratio=aspect_ratio,
            solidity=solidity,
            elongation=elongation,
            shape_analysis=shape_analysis,
            candidate_score=candidate_score,
            image_size=image_size,
        )
        score_breakdown = {
            "toe_score": round(shape_analysis.toe_score, 4),
            "forefoot_score": round(shape_analysis.forefoot_score, 4),
            "heel_score": round(shape_analysis.heel_score, 4),
            "ankle_rejection_score": round(shape_analysis.ankle_rejection_score, 4),
            "leg_rejection_score": round(shape_analysis.leg_rejection_score, 4),
            "shape_score": round(shape_analysis.shape_score, 4),
            "final_score": round(candidate_score, 4),
            "sam_score": round(sam_score, 4) if sam_score is not None else 0.0,
        }
        return CandidateDiagnostics(
            index=index,
            source_index=source_index,
            source=source,
            bbox=bbox,
            area_pixels=area,
            area_ratio=round(area_ratio, 5),
            bbox_area_ratio=round(bbox_area_ratio, 5),
            aspect_ratio=round(aspect_ratio, 4),
            solidity=round(solidity, 4),
            elongation=round(elongation, 4),
            toe_score=round(shape_analysis.toe_score, 4),
            visible_toe_count=shape_analysis.visible_toe_count,
            forefoot_score=round(shape_analysis.forefoot_score, 4),
            heel_score=round(shape_analysis.heel_score, 4),
            ankle_rejection_score=round(shape_analysis.ankle_rejection_score, 4),
            leg_rejection_score=round(shape_analysis.leg_rejection_score, 4),
            shape_score=round(shape_analysis.shape_score, 4),
            score_breakdown=score_breakdown,
            profile=shape_analysis.profile,
            orientation=shape_analysis.orientation,
            sam_score=sam_score,
            candidate_score=round(candidate_score, 4),
            rejected=rejection_reason is not None,
            rejection_reason=rejection_reason,
        )

    def _candidate_score(
        self,
        area_ratio: float,
        bbox_area_ratio: float,
        aspect_ratio: float,
        solidity: float,
        elongation: float,
        shape_analysis: FootShapeAnalysis,
        sam_score: float | None,
        source: str,
    ) -> float:
        area_score = self._triangular_score(area_ratio, target=0.16, tolerance=0.18)
        bbox_score = self._triangular_score(bbox_area_ratio, target=0.22, tolerance=0.28)
        aspect_score = self._triangular_score(aspect_ratio, target=0.58, tolerance=0.55)
        elongation_score = self._triangular_score(elongation, target=1.90, tolerance=1.10)
        solidity_score = self._triangular_score(solidity, target=0.84, tolerance=0.35)
        model_score = sam_score if sam_score is not None else 0.65
        profile_bonus = 0.06 if source.startswith("profile_foot_") else 0.0
        component_bonus = 0.02 if source == "component" else 0.0
        geometry_score = (
            0.10 * area_score
            + 0.08 * bbox_score
            + 0.06 * aspect_score
            + 0.05 * elongation_score
            + 0.05 * solidity_score
            + 0.04 * model_score
        )
        anatomy_score = (
            0.30 * shape_analysis.toe_score
            + 0.27 * shape_analysis.forefoot_score
            + 0.17 * shape_analysis.heel_score
            + 0.16 * shape_analysis.shape_score
        )
        rejection_penalty = (
            0.20 * shape_analysis.ankle_rejection_score
            + 0.28 * shape_analysis.leg_rejection_score
        )
        score = anatomy_score + geometry_score + component_bonus + profile_bonus - rejection_penalty
        return max(0.0, min(score, 0.99))

    def _rejection_reason(
        self,
        source: str,
        bbox: BoundingBox,
        area_ratio: float,
        bbox_area_ratio: float,
        aspect_ratio: float,
        solidity: float,
        elongation: float,
        shape_analysis: FootShapeAnalysis,
        candidate_score: float,
        image_size: tuple[int, int],
    ) -> str | None:
        width, height = image_size
        margin_x = int(width * self.edge_margin_ratio)
        if area_ratio < 0.001:
            return "area too small"
        if source.startswith("lower_") or source.startswith("inverse_lower_"):
            if bbox.x <= margin_x or bbox.x + bbox.width >= width - margin_x:
                edge_candidate_is_plausible = (
                    candidate_score >= 0.62
                    and shape_analysis.visible_toe_count >= 2
                    and shape_analysis.toe_score >= 0.48
                    and shape_analysis.leg_rejection_score < 0.48
                )
                if not edge_candidate_is_plausible:
                    return "split candidate touches lateral frame edge"
            if shape_analysis.visible_toe_count < 2 or shape_analysis.toe_score < 0.50:
                return "lower split misses top toe region"
        if area_ratio > 0.62 or bbox_area_ratio > 0.72:
            return "full body or background mask"
        if bbox.height > height * 0.78 and bbox.y < height * 0.12:
            return "leg or full lower-body mask"
        if (
            shape_analysis.orientation == "toes_top"
            and bbox.y > height * 0.42
            and shape_analysis.toe_score < 0.60
        ):
            return "candidate starts too low and misses toes"
        if bbox.width < width * 0.06 or bbox.height < height * 0.05:
            return "candidate too small to be a foot"
        if aspect_ratio > 3.2 or aspect_ratio < 0.18:
            return "aspect ratio is not foot-like"
        if solidity < 0.18:
            return "contour is too fragmented"
        if elongation < 1.05:
            compact_candidate_is_plausible = (
                candidate_score >= 0.62
                and shape_analysis.visible_toe_count >= 2
                and shape_analysis.forefoot_score >= 0.55
                and shape_analysis.leg_rejection_score < 0.48
            )
            if not compact_candidate_is_plausible:
                return "candidate is not elongated enough"
        if shape_analysis.rejection_reasons:
            return "; ".join(shape_analysis.rejection_reasons)
        if shape_analysis.final_score < 0.30:
            return "anatomical foot score too low"
        return None

    def _connected_components(self, mask: Any) -> list[Any]:
        import numpy as np

        height, width = mask.shape
        visited = np.zeros_like(mask, dtype=bool)
        components = []
        for y in range(height):
            for x in range(width):
                if not mask[y, x] or visited[y, x]:
                    continue
                stack = [(x, y)]
                visited[y, x] = True
                points = []
                while stack:
                    px, py = stack.pop()
                    points.append((px, py))
                    for nx, ny in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
                        if 0 <= nx < width and 0 <= ny < height and mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((nx, ny))
                component = np.zeros_like(mask, dtype=bool)
                xs, ys = zip(*points, strict=True)
                component[list(ys), list(xs)] = True
                components.append(component)
        return components

    def _vertical_valley_split(self, mask: Any, min_x: int, max_x: int) -> int:
        import numpy as np

        density = mask.sum(axis=0)
        width = max_x - min_x + 1
        start = min_x + int(width * 0.40)
        end = min_x + int(width * 0.60)
        if end <= start:
            return min_x + width // 2
        window = density[start:end].astype(float)
        nonzero = window[window > 0]
        if nonzero.size:
            floor = max(1.0, float(np.percentile(nonzero, 12)))
            window = np.where(window > 0, window, floor)
        valley = int(np.argmin(window) + start)
        return valley

    def _convex_hull_area(self, points: list[tuple[int, int]]) -> float:
        if len(points) < 3:
            return float(len(points))
        sample_step = max(1, len(points) // 2000)
        sampled = sorted(set(points[::sample_step]))

        def cross(origin: tuple[int, int], a: tuple[int, int], b: tuple[int, int]) -> int:
            return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])

        lower: list[tuple[int, int]] = []
        for point in sampled:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
                lower.pop()
            lower.append(point)
        upper: list[tuple[int, int]] = []
        for point in reversed(sampled):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
                upper.pop()
            upper.append(point)
        hull = lower[:-1] + upper[:-1]
        if len(hull) < 3:
            return float(len(points))
        area = 0.0
        for index, point in enumerate(hull):
            next_point = hull[(index + 1) % len(hull)]
            area += point[0] * next_point[1] - next_point[0] * point[1]
        return abs(area) / 2

    def _triangular_score(self, value: float, target: float, tolerance: float) -> float:
        return max(0.0, 1.0 - abs(value - target) / tolerance)

    def _touches_frame_edge(self, bbox: BoundingBox, image_size: tuple[int, int]) -> bool:
        width, height = image_size
        margin_x = int(width * self.edge_margin_ratio)
        margin_y = int(height * self.edge_margin_ratio)
        return (
            bbox.x <= margin_x
            or bbox.y <= margin_y
            or bbox.x + bbox.width >= width - margin_x
            or bbox.y + bbox.height >= height - margin_y
        )
