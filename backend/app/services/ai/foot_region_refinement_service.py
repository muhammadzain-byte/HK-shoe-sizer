from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from app.services.ai.contracts import BoundingBox


@dataclass(frozen=True)
class HeelBoundary:
    axis_position: float
    x: float
    y: float


@dataclass(frozen=True)
class FootRegionRefinementResult:
    refined_mask: Any
    original_bbox: BoundingBox
    refined_bbox: BoundingBox
    heel_boundary: HeelBoundary
    removed_lower_leg_area_ratio: float
    refinement_confidence: float
    issues: list[str] = field(default_factory=list)
    width_profile: list[dict[str, float]] = field(default_factory=list)
    region_axis_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)
    heel_boundary_type: str = "straight_fallback"
    heel_boundary_confidence: float = 0.0
    heel_center: dict[str, float] = field(default_factory=dict)
    heel_curve_points: list[dict[str, float]] = field(default_factory=list)
    ankle_transition_position: float = 1.0

    def to_metadata(self) -> dict[str, Any]:
        return {
            "original_bbox": _bbox_to_dict(self.original_bbox),
            "refined_bbox": _bbox_to_dict(self.refined_bbox),
            "heel_boundary": {
                "axis_position": round(self.heel_boundary.axis_position, 4),
                "x": round(self.heel_boundary.x, 2),
                "y": round(self.heel_boundary.y, 2),
            },
            "heel_boundary_axis_position": round(self.heel_boundary.axis_position, 4),
            "heel_boundary_type": self.heel_boundary_type,
            "heel_boundary_confidence": self.heel_boundary_confidence,
            "heel_center": {
                "x": round(float(self.heel_center.get("x", self.heel_boundary.x)), 2),
                "y": round(float(self.heel_center.get("y", self.heel_boundary.y)), 2),
            },
            "heel_curve_points": [
                {"x": round(float(point["x"]), 2), "y": round(float(point["y"]), 2)}
                for point in self.heel_curve_points
            ],
            "ankle_transition_position": round(float(self.ankle_transition_position), 4),
            "removed_lower_leg_area_ratio": self.removed_lower_leg_area_ratio,
            "refinement_confidence": self.refinement_confidence,
            "issues": self.issues,
            "width_profile": self.width_profile,
            "region_axis_ranges": {
                key: [round(value[0], 4), round(value[1], 4)]
                for key, value in self.region_axis_ranges.items()
            },
        }


class FootRegionRefinementService:
    """Trims ankle/lower-leg continuation from a selected foot candidate mask."""

    model_name = "foot_region_refinement_width_profile"
    model_version = "0.1.0"

    def refine(self, selected_mask: Any, selected_bbox: BoundingBox | None = None) -> FootRegionRefinementResult:
        import numpy as np

        binary = self._normalize_mask(selected_mask)
        if selected_bbox is None:
            selected_bbox = self._bbox_from_mask(binary)

        contour_mask, contour_area, issues = self._largest_contour_mask(binary)
        if contour_area <= 0:
            raise ValueError("Selected candidate mask has no measurable contour.")

        points_yx = np.argwhere(contour_mask)
        points = np.column_stack((points_yx[:, 1], points_yx[:, 0])).astype("float64")
        frame = self._canonical_frame(points)
        canonical = self._to_canonical(points, frame)
        v_min = float(canonical[:, 1].min())
        v_max = float(canonical[:, 1].max())
        axis_length = max(v_max - v_min, 1.0)

        profile = self._width_profile(canonical, v_min, v_max)
        heel_axis_position, confidence, boundary_issues = self._heel_boundary_axis_position(
            profile,
            axis_length,
        )
        issues.extend(boundary_issues)

        boundary_v = v_min + heel_axis_position * axis_length
        heel_model = self._heel_boundary_model(
            canonical,
            profile,
            frame,
            v_min,
            axis_length,
            heel_axis_position,
            boundary_v,
            confidence,
        )
        retained = canonical[:, 1] <= heel_model["allowed_v"]
        if retained.sum() < max(25, int(len(canonical) * 0.35)):
            issues.append("heel boundary would remove too much foot; using original mask")
            retained = np.ones(len(canonical), dtype=bool)
            heel_axis_position = 1.0
            boundary_v = v_max
            confidence = min(confidence, 0.35)
            heel_model = self._straight_boundary_model(canonical, frame, boundary_v, axis_length, heel_axis_position)

        refined_mask = np.zeros_like(contour_mask, dtype=bool)
        retained_points = points_yx[retained]
        refined_mask[retained_points[:, 0], retained_points[:, 1]] = True
        refined_mask = self._morphological_cleanup(refined_mask)

        refined_bbox = self._bbox_from_mask(refined_mask) if refined_mask.any() else selected_bbox
        original_area = int(contour_mask.sum())
        refined_area = int(refined_mask.sum())
        removed_area_ratio = round(max(original_area - refined_area, 0) / max(original_area, 1), 4)
        if removed_area_ratio < 0.015:
            issues.append("no meaningful ankle/lower-leg continuation detected")
        if heel_axis_position > 0.94 and removed_area_ratio < 0.04:
            confidence = min(confidence, 0.55)

        boundary_point = heel_model["boundary_point"]
        heel_center = heel_model["heel_center"]
        heel_boundary_confidence = min(
            max(float(heel_model["confidence"]), float(confidence)),
            0.99,
        )
        if heel_model["boundary_type"] == "straight_fallback":
            heel_boundary_confidence = min(heel_boundary_confidence, 0.58)

        return FootRegionRefinementResult(
            refined_mask=refined_mask,
            original_bbox=selected_bbox,
            refined_bbox=refined_bbox,
            heel_boundary=HeelBoundary(
                axis_position=round(float(heel_axis_position), 4),
                x=float(boundary_point[0]),
                y=float(boundary_point[1]),
            ),
            removed_lower_leg_area_ratio=removed_area_ratio,
            refinement_confidence=round(float(max(0.0, min(confidence, 0.99))), 4),
            issues=issues,
            width_profile=profile,
            region_axis_ranges={
                "toe": (0.00, 0.25),
                "forefoot": (0.25, 0.52),
                "midfoot": (0.52, min(0.74, heel_axis_position)),
                "heel": (max(0.68, heel_axis_position - 0.16), heel_axis_position),
                "removed_ankle_lower_leg": (heel_axis_position, 1.00),
            },
            heel_boundary_type=heel_model["boundary_type"],
            heel_boundary_confidence=round(float(max(0.0, heel_boundary_confidence)), 4),
            heel_center={"x": float(heel_center[0]), "y": float(heel_center[1])},
            heel_curve_points=heel_model["curve_points"],
            ankle_transition_position=round(float(heel_axis_position), 4),
        )

    def save_refined_mask(self, result: FootRegionRefinementResult, path: str | Path) -> None:
        Image.fromarray(result.refined_mask.astype("uint8") * 255, mode="L").save(path)

    def save_refined_overlay(
        self,
        image: Image.Image,
        result: FootRegionRefinementResult,
        path: str | Path,
    ) -> None:
        overlay = image.convert("RGBA")
        layer = Image.new("RGBA", image.size, (0, 220, 120, 105))
        mask_image = Image.fromarray(result.refined_mask.astype("uint8") * 255, mode="L")
        overlay.alpha_composite(
            Image.composite(layer, Image.new("RGBA", image.size, (0, 0, 0, 0)), mask_image)
        )
        draw = ImageDraw.Draw(overlay, "RGBA")
        box = result.refined_bbox
        draw.rectangle((box.x, box.y, box.x + box.width, box.y + box.height), outline=(0, 255, 120, 255), width=4)
        self._draw_boundary(draw, result)
        overlay.convert("RGB").save(path)

    def save_debug_overlay(
        self,
        image: Image.Image,
        original_mask: Any,
        result: FootRegionRefinementResult,
        path: str | Path,
    ) -> None:
        original = self._normalize_mask(original_mask)
        refined = result.refined_mask.astype(bool)
        removed = original & ~refined

        overlay = image.convert("RGBA")
        for mask, color in (
            (original, (255, 80, 80, 65)),
            (removed, (255, 150, 40, 150)),
            (refined, (0, 220, 120, 100)),
        ):
            layer = Image.new("RGBA", image.size, color)
            mask_image = Image.fromarray(mask.astype("uint8") * 255, mode="L")
            overlay.alpha_composite(
                Image.composite(layer, Image.new("RGBA", image.size, (0, 0, 0, 0)), mask_image)
            )

        draw = ImageDraw.Draw(overlay, "RGBA")
        self._draw_region_bands(draw, original, result)
        self._draw_boundary(draw, result)
        self._draw_width_profile(draw, result)
        original_box = result.original_bbox
        refined_box = result.refined_bbox
        draw.rectangle(
            (
                original_box.x,
                original_box.y,
                original_box.x + original_box.width,
                original_box.y + original_box.height,
            ),
            outline=(255, 80, 80, 255),
            width=3,
        )
        draw.rectangle(
            (
                refined_box.x,
                refined_box.y,
                refined_box.x + refined_box.width,
                refined_box.y + refined_box.height,
            ),
            outline=(0, 255, 120, 255),
            width=4,
        )
        draw.text((12, 12), "red=original  green=refined  orange=removed", fill=(0, 0, 0, 255))
        draw.text(
            (12, 34),
            f"removed={result.removed_lower_leg_area_ratio:.3f} confidence={result.refinement_confidence:.2f}",
            fill=(0, 0, 0, 255),
        )
        draw.text(
            (12, 56),
            f"heel={result.heel_boundary_type} confidence={result.heel_boundary_confidence:.2f}",
            fill=(0, 0, 0, 255),
        )
        self._draw_heel_center(draw, result)
        overlay.convert("RGB").save(path)

    def save_heel_boundary_debug(
        self,
        image: Image.Image,
        original_mask: Any,
        result: FootRegionRefinementResult,
        path: str | Path,
    ) -> None:
        original = self._normalize_mask(original_mask)
        refined = result.refined_mask.astype(bool)
        removed = original & ~refined

        overlay = image.convert("RGBA")
        for mask, color in (
            (original, (255, 80, 80, 55)),
            (refined, (0, 220, 120, 95)),
            (removed, (255, 140, 40, 155)),
        ):
            layer = Image.new("RGBA", image.size, color)
            mask_image = Image.fromarray(mask.astype("uint8") * 255, mode="L")
            overlay.alpha_composite(
                Image.composite(layer, Image.new("RGBA", image.size, (0, 0, 0, 0)), mask_image)
            )

        draw = ImageDraw.Draw(overlay, "RGBA")
        self._draw_region_bands(draw, original, result)
        self._draw_boundary(draw, result)
        self._draw_heel_center(draw, result)
        self._draw_width_profile(draw, result)
        draw.text((12, 12), "red=selected  green=heel-refined  orange=removed lower leg", fill=(0, 0, 0, 255))
        draw.text(
            (12, 34),
            f"heel boundary: {result.heel_boundary_type}  confidence={result.heel_boundary_confidence:.2f}",
            fill=(0, 0, 0, 255),
        )
        overlay.convert("RGB").save(path)

    def _normalize_mask(self, mask: Any):
        import numpy as np

        if mask is None:
            raise ValueError("Selected candidate mask is missing.")
        if hasattr(mask, "detach"):
            mask = mask.detach().cpu().numpy()
        elif isinstance(mask, Image.Image):
            mask = np.asarray(mask)
        array = np.asarray(mask)
        if array.ndim == 3:
            array = array.squeeze()
        if array.ndim != 2:
            raise ValueError(f"Expected a 2D mask, got shape {array.shape}.")
        return array.astype(bool)

    def _largest_contour_mask(self, binary: Any) -> tuple[Any, float, list[str]]:
        import cv2
        import numpy as np

        contours, _ = cv2.findContours(
            (binary.astype("uint8") * 255), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return np.zeros_like(binary, dtype=bool), 0.0, ["no contour found"]
        contour = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(contour))
        mask = np.zeros_like(binary, dtype="uint8")
        cv2.drawContours(mask, [contour], -1, 255, thickness=-1)
        issues = []
        if len(contours) > 1:
            issues.append("multiple contours found; using largest contour")
        return mask.astype(bool), area, issues

    def _morphological_cleanup(self, mask: Any):
        import cv2
        import numpy as np

        kernel = np.ones((5, 5), dtype="uint8")
        cleaned = cv2.morphologyEx(mask.astype("uint8") * 255, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, np.ones((3, 3), dtype="uint8"))
        return cleaned.astype(bool)

    def _canonical_frame(self, points: Any) -> dict[str, Any]:
        import numpy as np

        mean = points.mean(axis=0)
        centered = points - mean
        covariance = np.cov(centered.T)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        order = np.argsort(eigenvalues)[::-1]
        major_axis = eigenvectors[:, order[0]]
        minor_axis = eigenvectors[:, order[1]]
        if major_axis[1] < 0:
            major_axis = -major_axis
        return {"mean": mean, "major_axis": major_axis, "minor_axis": minor_axis}

    def _to_canonical(self, points: Any, frame: dict[str, Any]):
        import numpy as np

        centered = points - frame["mean"]
        u = centered @ frame["minor_axis"]
        v = centered @ frame["major_axis"]
        return np.column_stack((u, v))

    def _from_canonical(self, canonical_point: tuple[float, float], frame: dict[str, Any]):
        return (
            frame["mean"]
            + canonical_point[0] * frame["minor_axis"]
            + canonical_point[1] * frame["major_axis"]
        )

    def _width_profile(self, canonical: Any, v_min: float, v_max: float) -> list[dict[str, float]]:
        import numpy as np

        axis_length = max(v_max - v_min, 1.0)
        bins = np.linspace(v_min, v_max, 91)
        profile = []
        for index, (start, end) in enumerate(zip(bins[:-1], bins[1:], strict=True)):
            band = canonical[(canonical[:, 1] >= start) & (canonical[:, 1] < end)]
            axis_position = ((start + end) / 2 - v_min) / axis_length
            if len(band) < 2:
                profile.append(
                    {
                        "band": index,
                        "axis_position": round(float(axis_position), 4),
                        "width": 0.0,
                        "area": 0.0,
                        "left_edge": 0.0,
                        "right_edge": 0.0,
                        "center": 0.0,
                    }
                )
                continue
            left = float(band[:, 0].min())
            right = float(band[:, 0].max())
            profile.append(
                {
                    "band": index,
                    "axis_position": round(float(axis_position), 4),
                    "width": round(float(right - left), 4),
                    "area": float(len(band)),
                    "left_edge": round(left, 4),
                    "right_edge": round(right, 4),
                    "center": round(float((left + right) / 2), 4),
                }
            )
        return profile

    def _heel_boundary_axis_position(
        self,
        profile: list[dict[str, float]],
        axis_length: float,
    ) -> tuple[float, float, list[str]]:
        import numpy as np

        widths = np.array([row["width"] for row in profile], dtype=float)
        positions = np.array([row["axis_position"] for row in profile], dtype=float)
        active = widths > 0
        if active.sum() < 12:
            return 1.0, 0.2, ["insufficient width profile for refinement"]

        smooth = self._smooth(widths, 5)
        forefoot_band = (positions >= 0.18) & (positions <= 0.48) & active
        midfoot_band = (positions >= 0.48) & (positions <= 0.72) & active
        lower_band = (positions >= 0.72) & active
        if not forefoot_band.any() or not midfoot_band.any() or not lower_band.any():
            return 1.0, 0.28, ["missing expected toe/forefoot/heel profile bands"]

        forefoot_width = float(np.percentile(smooth[forefoot_band], 92))
        midfoot_width = float(np.percentile(smooth[midfoot_band], 45))
        lower_widths = smooth[lower_band]
        lower_variation = float(lower_widths.std() / max(lower_widths.mean(), 1.0))
        tail_band = (positions >= 0.86) & active
        tail_width = float(np.percentile(smooth[tail_band], 65)) if tail_band.any() else float(lower_widths[-1])
        terminal_band = (positions >= 0.96) & active
        terminal_width = (
            float(np.percentile(smooth[terminal_band], 50))
            if terminal_band.any()
            else float(lower_widths[-1])
        )
        forefoot_to_tail = forefoot_width / max(tail_width, 1.0)
        forefoot_to_midfoot = forefoot_width / max(midfoot_width, 1.0)
        terminal_to_forefoot = terminal_width / max(forefoot_width, 1.0)
        terminal_to_tail = terminal_width / max(tail_width, 1.0)

        candidates: list[tuple[float, float]] = []
        for index, position in enumerate(positions):
            if position < 0.68 or position > 0.93 or not active[index]:
                continue
            after = smooth[index:]
            after_positions = positions[index:]
            after_active = after[after > 0]
            if after_active.size < 5:
                continue
            after_mean = float(after_active.mean())
            after_variation = float(after_active.std() / max(after_mean, 1.0))
            local_drop = max(0.0, (forefoot_width - smooth[index]) / max(forefoot_width, 1.0))
            tail_narrowness = max(0.0, (forefoot_width - after_mean) / max(forefoot_width, 1.0))
            lower_extension = max(0.0, float(after_positions[-1] - position))
            cylindrical_score = max(0.0, min(1.0, 1.0 - after_variation / 0.22))
            score = (
                0.34 * tail_narrowness
                + 0.26 * cylindrical_score
                + 0.22 * local_drop
                + 0.18 * min(lower_extension / 0.22, 1.0)
            )
            candidates.append((score, float(position)))

        issues = []
        if not candidates:
            issues.append("no clear heel-to-ankle transition found")
            return 1.0, 0.42, issues

        best_score, best_position = max(candidates, key=lambda item: item[0])
        has_leg_tail = (
            forefoot_to_tail >= 1.12
            and terminal_to_forefoot >= 0.28
            and terminal_to_tail >= 0.72
            and lower_variation <= 0.36
            and best_score >= 0.36
            and axis_length >= 80
        )
        if not has_leg_tail:
            issues.append("no strong lower-leg continuation detected")
            return 1.0, max(0.38, min(0.58, best_score)), issues

        boundary = max(0.70, min(best_position, 0.92))
        confidence = (
            0.30 * min(forefoot_to_tail / 1.55, 1.0)
            + 0.26 * min(forefoot_to_midfoot / 1.35, 1.0)
            + 0.24 * best_score
            + 0.12 * max(0.0, min(1.0, 1.0 - lower_variation / 0.36))
            + 0.08 * max(0.0, min(1.0, terminal_to_tail))
        )
        return boundary, confidence, issues

    def _smooth(self, values: Any, window: int):
        import numpy as np

        window = max(1, int(window))
        if window <= 1:
            return values.astype(float)
        kernel = np.ones(window, dtype=float) / window
        return np.convolve(values.astype(float), kernel, mode="same")

    def _band_center_u(self, canonical: Any, boundary_v: float, axis_length: float) -> float:
        half_band = max(axis_length * 0.01, 2.0)
        band = canonical[
            (canonical[:, 1] >= boundary_v - half_band)
            & (canonical[:, 1] <= boundary_v + half_band)
        ]
        if len(band) == 0:
            return float(canonical[:, 0].mean())
        return float((band[:, 0].min() + band[:, 0].max()) / 2)

    def _heel_boundary_model(
        self,
        canonical: Any,
        profile: list[dict[str, float]],
        frame: dict[str, Any],
        v_min: float,
        axis_length: float,
        heel_axis_position: float,
        boundary_v: float,
        confidence: float,
    ) -> dict[str, Any]:
        if heel_axis_position >= 0.96 or confidence < 0.42:
            return self._straight_boundary_model(canonical, frame, boundary_v, axis_length, heel_axis_position)

        boundary_width = self._profile_percentile(profile, heel_axis_position, "width", 55, window=0.035)
        heel_width = self._profile_percentile(profile, max(0.60, heel_axis_position - 0.08), "width", 82, window=0.08)
        ankle_width = self._profile_percentile(profile, min(0.98, heel_axis_position + 0.12), "width", 55, window=0.06)
        if boundary_width <= 6 or heel_width <= 6:
            return self._straight_boundary_model(canonical, frame, boundary_v, axis_length, heel_axis_position)

        has_ankle_narrowing = ankle_width <= max(heel_width * 0.90, boundary_width * 1.15)
        has_lower_extension = heel_axis_position <= 0.91
        if not (has_ankle_narrowing and has_lower_extension):
            return self._straight_boundary_model(canonical, frame, boundary_v, axis_length, heel_axis_position)

        center_u = self._band_center_u(canonical, boundary_v, axis_length)
        half_width = max(boundary_width * 0.52, heel_width * 0.34, 8.0)
        sag = min(axis_length * 0.072, max(axis_length * 0.035, half_width * 0.44, 14.0))
        side_lift = sag * 0.18
        normalized = abs(canonical[:, 0] - center_u) / max(half_width, 1.0)
        curve = boundary_v + sag * (1.0 - normalized**2)
        allowed_v = curve.copy()
        outside = normalized > 1.0
        allowed_v[outside] = boundary_v - side_lift * (normalized[outside] - 1.0).clip(0.0, 1.0)

        heel_center = self._from_canonical((center_u, boundary_v + sag), frame)
        boundary_point = self._from_canonical((center_u, boundary_v), frame)
        curve_points = []
        sample_count = 25
        for index in range(sample_count):
            lateral = -half_width + (2 * half_width) * index / max(sample_count - 1, 1)
            u = center_u + lateral
            ratio = abs(lateral) / max(half_width, 1.0)
            v = boundary_v + sag * (1.0 - ratio**2)
            point = self._from_canonical((u, v), frame)
            curve_points.append({"x": float(point[0]), "y": float(point[1])})

        curve_confidence = (
            0.46 * min(confidence / 0.72, 1.0)
            + 0.24 * min(heel_width / max(ankle_width, 1.0) / 1.20, 1.0)
            + 0.18 * min((1.0 - heel_axis_position) / 0.24, 1.0)
            + 0.12 * min(sag / max(axis_length * 0.05, 1.0), 1.0)
        )
        return {
            "allowed_v": allowed_v,
            "boundary_type": "curved",
            "confidence": max(confidence, min(curve_confidence, 0.94)),
            "boundary_point": boundary_point,
            "heel_center": heel_center,
            "curve_points": curve_points,
        }

    def _straight_boundary_model(
        self,
        canonical: Any,
        frame: dict[str, Any],
        boundary_v: float,
        axis_length: float,
        heel_axis_position: float,
    ) -> dict[str, Any]:
        boundary_center_u = self._band_center_u(canonical, boundary_v, axis_length)
        boundary_point = self._from_canonical((boundary_center_u, boundary_v), frame)
        allowed_v = canonical[:, 1] * 0 + boundary_v
        return {
            "allowed_v": allowed_v,
            "boundary_type": "straight_fallback",
            "confidence": 0.42 if heel_axis_position < 0.96 else 0.35,
            "boundary_point": boundary_point,
            "heel_center": boundary_point,
            "curve_points": [],
        }

    def _profile_percentile(
        self,
        profile: list[dict[str, float]],
        axis_position: float,
        key: str,
        percentile: float,
        window: float,
    ) -> float:
        import numpy as np

        values = [
            float(row[key])
            for row in profile
            if abs(float(row["axis_position"]) - axis_position) <= window and float(row[key]) > 0
        ]
        if not values:
            values = [float(row[key]) for row in profile if float(row[key]) > 0]
        if not values:
            return 0.0
        return float(np.percentile(np.asarray(values, dtype=float), percentile))

    def _bbox_from_mask(self, mask: Any) -> BoundingBox:
        import numpy as np

        ys, xs = np.where(mask)
        if len(xs) == 0 or len(ys) == 0:
            return BoundingBox(x=0, y=0, width=0, height=0)
        return BoundingBox(
            x=int(xs.min()),
            y=int(ys.min()),
            width=int(xs.max() - xs.min() + 1),
            height=int(ys.max() - ys.min() + 1),
        )

    def _draw_boundary(self, draw: ImageDraw.ImageDraw, result: FootRegionRefinementResult) -> None:
        box = result.original_bbox
        if result.heel_curve_points:
            points = [(point["x"], point["y"]) for point in result.heel_curve_points]
            draw.line(points, fill=(30, 80, 255, 255), width=5)
            label_x = min(point[0] for point in points)
            label_y = min(point[1] for point in points)
            draw.text((label_x, max(0, label_y - 22)), "curved heel boundary", fill=(30, 80, 255, 255))
            return
        y = result.heel_boundary.y
        draw.line(
            (box.x - 16, y, box.x + box.width + 16, y),
            fill=(30, 80, 255, 255),
            width=5,
        )
        draw.text((box.x + 6, max(0, y - 22)), "heel boundary fallback", fill=(30, 80, 255, 255))

    def _draw_heel_center(self, draw: ImageDraw.ImageDraw, result: FootRegionRefinementResult) -> None:
        x = float(result.heel_center.get("x", result.heel_boundary.x))
        y = float(result.heel_center.get("y", result.heel_boundary.y))
        draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(255, 40, 40, 255), outline=(255, 255, 255, 255), width=2)
        draw.text((x + 9, y + 4), "heel center", fill=(255, 40, 40, 255))

    def _draw_region_bands(
        self,
        draw: ImageDraw.ImageDraw,
        original_mask: Any,
        result: FootRegionRefinementResult,
    ) -> None:
        box = result.original_bbox
        colors = {
            "toe": (80, 160, 255, 38),
            "forefoot": (255, 80, 220, 34),
            "midfoot": (255, 220, 80, 30),
            "heel": (80, 255, 140, 38),
            "removed_ankle_lower_leg": (255, 120, 40, 45),
        }
        for name, axis_range in result.region_axis_ranges.items():
            y0 = box.y + box.height * axis_range[0]
            y1 = box.y + box.height * axis_range[1]
            draw.rectangle((box.x, y0, box.x + box.width, y1), fill=colors.get(name, (255, 255, 255, 20)))
            draw.text((box.x + 6, max(0, y0 + 4)), name, fill=(0, 0, 0, 180))

    def _draw_width_profile(self, draw: ImageDraw.ImageDraw, result: FootRegionRefinementResult) -> None:
        box = result.original_bbox
        profile = result.width_profile
        if not profile:
            return
        max_width = max((row["width"] for row in profile), default=1.0)
        x0 = box.x + box.width + 28
        x1 = x0 + 120
        y0 = box.y
        y1 = box.y + box.height
        draw.rectangle((x0, y0, x1, y1), outline=(0, 0, 0, 180), width=2)
        points = []
        for row in profile:
            y = y0 + box.height * row["axis_position"]
            x = x0 + 8 + (row["width"] / max(max_width, 1.0)) * 104
            points.append((x, y))
        if len(points) >= 2:
            draw.line(points, fill=(0, 0, 0, 230), width=3)
        draw.text((x0, max(0, y0 - 18)), "width profile", fill=(0, 0, 0, 255))


def _bbox_to_dict(bbox: BoundingBox) -> dict[str, int]:
    return {
        "x": int(bbox.x),
        "y": int(bbox.y),
        "width": int(bbox.width),
        "height": int(bbox.height),
    }
