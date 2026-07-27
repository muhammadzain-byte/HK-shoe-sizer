from dataclasses import dataclass, field
from decimal import Decimal
from math import sqrt
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw
from sqlalchemy.orm import Session

from app.models.foot_measurement import FootMeasurement


@dataclass(frozen=True)
class MeasurementPoint:
    x: float
    y: float


@dataclass(frozen=True)
class RegionDebug:
    name: str
    polygon: list[tuple[float, float]]


@dataclass(frozen=True)
class LegacyMeasurementDebug:
    heel_point: MeasurementPoint
    toe_point: MeasurementPoint
    width_left_point: MeasurementPoint
    width_right_point: MeasurementPoint
    foot_length_pixels: float
    foot_width_pixels: float


@dataclass(frozen=True)
class MeasurementQualityReport:
    measurement_confidence: float
    issues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FootMeasurementResult:
    measurement_status: str
    foot_length_pixels: float
    foot_width_pixels: float
    heel_point: MeasurementPoint
    toe_point: MeasurementPoint
    width_left_point: MeasurementPoint
    width_right_point: MeasurementPoint
    confidence_score: float
    contour_points: list[tuple[int, int]]
    bounding_box: tuple[int, int, int, int]
    heel_region: RegionDebug | None = None
    toe_region: RegionDebug | None = None
    forefoot_region: RegionDebug | None = None
    toe_candidates: list[MeasurementPoint] = field(default_factory=list)
    legacy: LegacyMeasurementDebug | None = None
    quality_issues: list[str] = field(default_factory=list)


class MeasurementQualityAnalyzer:
    def analyze(
        self,
        contour_area: float,
        hull_area: float,
        bbox_area: float,
        heel_width: float,
        toe_candidate_count: int,
        forefoot_width: float,
        segmentation_confidence: float | None,
    ) -> MeasurementQualityReport:
        issues: list[str] = []
        solidity = contour_area / max(hull_area, 1.0)
        completeness = contour_area / max(bbox_area, 1.0)

        if heel_width <= 1:
            issues.append("heel ambiguity")
        if toe_candidate_count == 0:
            issues.append("toe ambiguity")
        if solidity < 0.45 or completeness < 0.35:
            issues.append("low-confidence contours")
        if forefoot_width <= heel_width * 0.9:
            issues.append("unusual foot shape")
        if completeness < 0.42 and solidity < 0.55:
            issues.append("overlapping feet")

        segmentation_score = segmentation_confidence if segmentation_confidence is not None else 0.65
        issue_penalty = min(len(issues) * 0.08, 0.32)
        confidence = (
            0.38 * segmentation_score
            + 0.26 * min(solidity, 1.0)
            + 0.22 * min(completeness, 1.0)
            + 0.14 * min(toe_candidate_count / 5, 1.0)
            - issue_penalty
        )
        return MeasurementQualityReport(
            measurement_confidence=round(max(0.0, min(confidence, 0.99)), 4),
            issues=issues,
        )


class MeasurementService:
    model_name = "pixel_anatomical_pca"
    model_version = "0.2.0"

    def __init__(self) -> None:
        self.quality_analyzer = MeasurementQualityAnalyzer()

    def measure_mask(
        self,
        selected_mask: Any,
        segmentation_confidence: float | None,
        refinement_metadata: dict[str, Any] | None = None,
    ) -> FootMeasurementResult:
        import cv2
        import numpy as np

        binary = self._normalize_mask(selected_mask)
        contours, _ = cv2.findContours(
            (binary.astype("uint8") * 255), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
        )
        if not contours:
            raise ValueError("No contour found in selected foot mask.")

        contour = max(contours, key=cv2.contourArea)
        contour_area = float(cv2.contourArea(contour))
        if contour_area <= 0:
            raise ValueError("Selected foot contour has no measurable area.")

        contour_points_array = contour.reshape(-1, 2).astype("float64")
        mask_points_yx = np.argwhere(binary)
        mask_points = np.column_stack((mask_points_yx[:, 1], mask_points_yx[:, 0])).astype("float64")

        frame = self._canonical_frame(contour_points_array)
        mask_canonical = self._to_canonical(mask_points, frame)
        if self._needs_orientation_flip(mask_canonical):
            frame["major_axis"] = -frame["major_axis"]
            mask_canonical = self._to_canonical(mask_points, frame)

        legacy = self._legacy_measurement(contour_points_array, frame)

        v_min = float(mask_canonical[:, 1].min())
        v_max = float(mask_canonical[:, 1].max())
        height = max(v_max - v_min, 1.0)
        heel_region = self._region_band(frame, mask_canonical, v_max - 0.20 * height, v_max)
        toe_region = self._region_band(frame, mask_canonical, v_min, v_min + 0.25 * height)
        forefoot_region = self._region_band(frame, mask_canonical, v_min + 0.28 * height, v_min + 0.66 * height)

        heel_point, heel_width = self._heel_center(frame, mask_canonical, v_max, height)
        heel_point, heel_center_issues = self._refined_heel_center_or_fallback(
            heel_point,
            refinement_metadata,
        )
        toe_candidates = self._toe_candidates(frame, mask_canonical, v_min, height)
        toe_point = self._select_longest_toe(heel_point, toe_candidates)
        width_left, width_right, foot_width = self._forefoot_width(frame, mask_canonical, v_min, height)
        foot_length = self._distance(heel_point, toe_point)

        x, y, w, h = cv2.boundingRect(contour)
        hull = cv2.convexHull(contour)
        hull_area = max(float(cv2.contourArea(hull)), 1.0)
        quality = self.quality_analyzer.analyze(
            contour_area=contour_area,
            hull_area=hull_area,
            bbox_area=max(w * h, 1),
            heel_width=heel_width,
            toe_candidate_count=len(toe_candidates),
            forefoot_width=foot_width,
            segmentation_confidence=segmentation_confidence,
        )
        quality_issues = [*quality.issues, *heel_center_issues]

        contour_points = [(int(point[0][0]), int(point[0][1])) for point in contour]
        return FootMeasurementResult(
            measurement_status="completed",
            foot_length_pixels=round(foot_length, 2),
            foot_width_pixels=round(foot_width, 2),
            heel_point=heel_point,
            toe_point=toe_point,
            width_left_point=width_left,
            width_right_point=width_right,
            confidence_score=quality.measurement_confidence,
            contour_points=contour_points,
            bounding_box=(int(x), int(y), int(w), int(h)),
            heel_region=heel_region,
            toe_region=toe_region,
            forefoot_region=forefoot_region,
            toe_candidates=toe_candidates,
            legacy=legacy,
            quality_issues=quality_issues,
        )

    def persist_result(self, db: Session, scan_id: Any, result: FootMeasurementResult) -> FootMeasurement:
        measurement = FootMeasurement(
            scan_id=scan_id,
            model_name=self.model_name,
            model_version=self.model_version,
            foot_length_pixels=Decimal(str(result.foot_length_pixels)),
            foot_width_pixels=Decimal(str(result.foot_width_pixels)),
            heel_x=Decimal(str(round(result.heel_point.x, 2))),
            heel_y=Decimal(str(round(result.heel_point.y, 2))),
            toe_x=Decimal(str(round(result.toe_point.x, 2))),
            toe_y=Decimal(str(round(result.toe_point.y, 2))),
            width_left_x=Decimal(str(round(result.width_left_point.x, 2))),
            width_left_y=Decimal(str(round(result.width_left_point.y, 2))),
            width_right_x=Decimal(str(round(result.width_right_point.x, 2))),
            width_right_y=Decimal(str(round(result.width_right_point.y, 2))),
            confidence_score=Decimal(str(result.confidence_score)),
            measurement_status=result.measurement_status,
        )
        db.add(measurement)
        db.commit()
        db.refresh(measurement)
        return measurement

    def save_overlay(
        self,
        image: Image.Image,
        result: FootMeasurementResult,
        output_path: str | Path,
    ) -> None:
        self.save_anatomical_overlay(image, result, output_path)

    def save_anatomical_overlay(
        self,
        image: Image.Image,
        result: FootMeasurementResult,
        output_path: str | Path,
    ) -> None:
        overlay = image.convert("RGBA")
        draw = ImageDraw.Draw(overlay, "RGBA")
        self._draw_region(draw, result.heel_region, (255, 120, 80, 55), (255, 120, 80, 210))
        self._draw_region(draw, result.toe_region, (80, 160, 255, 45), (80, 160, 255, 210))
        self._draw_region(draw, result.forefoot_region, (255, 80, 220, 45), (255, 80, 220, 210))
        if result.contour_points:
            draw.line([*result.contour_points, result.contour_points[0]], fill=(0, 210, 110, 255), width=3)
        x, y, w, h = result.bounding_box
        draw.rectangle((x, y, x + w, y + h), outline=(255, 220, 0, 255), width=2)
        for candidate in result.toe_candidates:
            self._draw_point(draw, candidate, "", (80, 160, 255, 150), radius=4)
        self._draw_point(draw, result.heel_point, "Heel center", (255, 80, 80, 255))
        self._draw_point(draw, result.toe_point, "Longest toe", (30, 100, 255, 255))
        draw.line(
            (result.heel_point.x, result.heel_point.y, result.toe_point.x, result.toe_point.y),
            fill=(30, 100, 255, 255),
            width=3,
        )
        draw.line(
            (
                result.width_left_point.x,
                result.width_left_point.y,
                result.width_right_point.x,
                result.width_right_point.y,
            ),
            fill=(255, 80, 220, 255),
            width=4,
        )
        draw.text(
            (x + 5, max(0, y - 48)),
            f"Anatomical L {result.foot_length_pixels:.2f}px  W {result.foot_width_pixels:.2f}px",
            fill=(0, 0, 0, 255),
        )
        draw.text(
            (x + 5, max(14, y - 28)),
            f"Confidence {result.confidence_score:.2f}",
            fill=(0, 0, 0, 255),
        )
        overlay.convert("RGB").save(output_path)

    def save_comparison_overlay(
        self,
        image: Image.Image,
        result: FootMeasurementResult,
        output_path: str | Path,
    ) -> None:
        if result.legacy is None:
            self.save_anatomical_overlay(image, result, output_path)
            return
        old_panel = image.convert("RGBA")
        new_panel = image.convert("RGBA")
        old_draw = ImageDraw.Draw(old_panel, "RGBA")
        new_draw = ImageDraw.Draw(new_panel, "RGBA")
        self._draw_legacy(old_draw, result)
        self._draw_anatomical_primitives(new_draw, result)
        canvas = Image.new("RGB", (image.width * 2, image.height), "white")
        canvas.paste(old_panel.convert("RGB"), (0, 0))
        canvas.paste(new_panel.convert("RGB"), (image.width, 0))
        draw = ImageDraw.Draw(canvas)
        draw.text((8, 8), "OLD METHOD", fill=(0, 0, 0))
        draw.text((image.width + 8, 8), "NEW ANATOMICAL METHOD", fill=(0, 0, 0))
        draw.text(
            (8, 28),
            f"dL {result.foot_length_pixels - result.legacy.foot_length_pixels:.2f}px "
            f"dW {result.foot_width_pixels - result.legacy.foot_width_pixels:.2f}px",
            fill=(0, 0, 0),
        )
        canvas.save(output_path)

    def _normalize_mask(self, mask: Any):
        import numpy as np

        if mask is None:
            raise ValueError("Selected foot mask is missing.")
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

    def _canonical_frame(self, points):
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

    def _to_canonical(self, points, frame):
        import numpy as np

        centered = points - frame["mean"]
        u = centered @ frame["minor_axis"]
        v = centered @ frame["major_axis"]
        return np.column_stack((u, v))

    def _from_canonical(self, canonical_point, frame) -> MeasurementPoint:
        point = (
            frame["mean"]
            + canonical_point[0] * frame["minor_axis"]
            + canonical_point[1] * frame["major_axis"]
        )
        return MeasurementPoint(float(point[0]), float(point[1]))

    def _needs_orientation_flip(self, mask_canonical) -> bool:
        v_min = float(mask_canonical[:, 1].min())
        v_max = float(mask_canonical[:, 1].max())
        height = max(v_max - v_min, 1.0)
        top = mask_canonical[mask_canonical[:, 1] <= v_min + 0.12 * height]
        bottom = mask_canonical[mask_canonical[:, 1] >= v_max - 0.12 * height]
        top_width = self._canonical_width(top)
        bottom_width = self._canonical_width(bottom)
        # Heel should be at bottom, and is normally narrower than the toe end.
        return bottom_width > top_width * 1.18

    def _canonical_width(self, points) -> float:
        if len(points) == 0:
            return 0.0
        return float(points[:, 0].max() - points[:, 0].min())

    def _region_band(self, frame, mask_canonical, v_start: float, v_end: float) -> RegionDebug:
        band = mask_canonical[(mask_canonical[:, 1] >= v_start) & (mask_canonical[:, 1] <= v_end)]
        if len(band) == 0:
            u_min = u_max = 0.0
        else:
            u_min = float(band[:, 0].min())
            u_max = float(band[:, 0].max())
        polygon = [
            self._point_tuple(self._from_canonical((u_min, v_start), frame)),
            self._point_tuple(self._from_canonical((u_max, v_start), frame)),
            self._point_tuple(self._from_canonical((u_max, v_end), frame)),
            self._point_tuple(self._from_canonical((u_min, v_end), frame)),
        ]
        return RegionDebug(name="band", polygon=polygon)

    def _heel_center(self, frame, mask_canonical, v_max: float, height: float) -> tuple[MeasurementPoint, float]:
        import numpy as np

        heel = mask_canonical[mask_canonical[:, 1] >= v_max - 0.20 * height]
        if len(heel) == 0:
            heel = mask_canonical
        bottom_band = heel[heel[:, 1] >= np.percentile(heel[:, 1], 78)]
        if len(bottom_band) == 0:
            bottom_band = heel
        u_left = float(bottom_band[:, 0].min())
        u_right = float(bottom_band[:, 0].max())
        center = ((u_left + u_right) / 2, float(bottom_band[:, 1].mean()))
        return self._from_canonical(center, frame), abs(u_right - u_left)

    def _refined_heel_center_or_fallback(
        self,
        fallback: MeasurementPoint,
        refinement_metadata: dict[str, Any] | None,
    ) -> tuple[MeasurementPoint, list[str]]:
        if not refinement_metadata:
            return fallback, []
        confidence = self._float_or_none(refinement_metadata.get("heel_boundary_confidence"))
        center = refinement_metadata.get("heel_center")
        if (
            isinstance(center, dict)
            and confidence is not None
            and confidence >= 0.45
            and self._float_or_none(center.get("x")) is not None
            and self._float_or_none(center.get("y")) is not None
        ):
            return MeasurementPoint(float(center["x"]), float(center["y"])), []
        return fallback, ["heel center fallback used"]

    def _toe_candidates(self, frame, mask_canonical, v_min: float, height: float) -> list[MeasurementPoint]:
        import numpy as np

        toe_region = mask_canonical[mask_canonical[:, 1] <= v_min + 0.25 * height]
        if len(toe_region) == 0:
            return [self._from_canonical(mask_canonical[int(mask_canonical[:, 1].argmin())], frame)]

        u_values = np.round(toe_region[:, 0]).astype(int)
        candidates: list[MeasurementPoint] = []
        for cluster in self._clusters(sorted(set(u_values.tolist())), gap=3):
            cluster_points = toe_region[np.isin(u_values, cluster)]
            if len(cluster_points) == 0:
                continue
            tip = cluster_points[int(cluster_points[:, 1].argmin())]
            candidates.append(self._from_canonical(tip, frame))
        if not candidates:
            candidates.append(self._from_canonical(toe_region[int(toe_region[:, 1].argmin())], frame))
        return candidates

    def _select_longest_toe(
        self, heel_point: MeasurementPoint, toe_candidates: list[MeasurementPoint]
    ) -> MeasurementPoint:
        return max(toe_candidates, key=lambda point: self._distance(heel_point, point))

    def _forefoot_width(self, frame, mask_canonical, v_min: float, height: float):
        import numpy as np

        start = v_min + 0.38 * height
        end = v_min + 0.68 * height
        best_width = 0.0
        best_left = best_right = mask_canonical[0]
        bins = np.linspace(start, end, 35)
        for band_start, band_end in zip(bins[:-1], bins[1:], strict=True):
            section = mask_canonical[
                (mask_canonical[:, 1] >= band_start) & (mask_canonical[:, 1] <= band_end)
            ]
            if len(section) < 2:
                continue
            width = float(section[:, 0].max() - section[:, 0].min())
            if width > best_width:
                median_v = float(section[:, 1].mean())
                best_width = width
                best_left = (float(section[:, 0].min()), median_v)
                best_right = (float(section[:, 0].max()), median_v)
        return (
            self._from_canonical(best_left, frame),
            self._from_canonical(best_right, frame),
            round(best_width, 2),
        )

    def _legacy_measurement(self, points, frame) -> LegacyMeasurementDebug:
        canonical = self._to_canonical(points, frame)
        if self._needs_orientation_flip(canonical):
            frame = {**frame, "major_axis": -frame["major_axis"]}
            canonical = self._to_canonical(points, frame)
        toe = self._from_canonical(canonical[int(canonical[:, 1].argmin())], frame)
        heel = self._from_canonical(canonical[int(canonical[:, 1].argmax())], frame)
        if heel.y < toe.y:
            heel, toe = toe, heel
        left, right, width = self._legacy_max_width(points, canonical, frame)
        return LegacyMeasurementDebug(
            heel_point=heel,
            toe_point=toe,
            width_left_point=left,
            width_right_point=right,
            foot_length_pixels=round(self._distance(heel, toe), 2),
            foot_width_pixels=width,
        )

    def _legacy_max_width(self, points, canonical, frame):
        import numpy as np

        best_width = 0.0
        best_left = canonical[0]
        best_right = canonical[0]
        bins = np.linspace(canonical[:, 1].min(), canonical[:, 1].max(), 80)
        for start, end in zip(bins[:-1], bins[1:], strict=True):
            section = canonical[(canonical[:, 1] >= start) & (canonical[:, 1] <= end)]
            if len(section) < 2:
                continue
            width = float(section[:, 0].max() - section[:, 0].min())
            if width > best_width:
                best_width = width
                median_v = float(section[:, 1].mean())
                best_left = (float(section[:, 0].min()), median_v)
                best_right = (float(section[:, 0].max()), median_v)
        return self._from_canonical(best_left, frame), self._from_canonical(best_right, frame), round(best_width, 2)

    def _clusters(self, values: list[int], gap: int) -> list[list[int]]:
        if not values:
            return []
        clusters = [[values[0]]]
        for value in values[1:]:
            if value - clusters[-1][-1] <= gap:
                clusters[-1].append(value)
            else:
                clusters.append([value])
        return clusters

    def _draw_legacy(self, draw: ImageDraw.ImageDraw, result: FootMeasurementResult) -> None:
        if result.legacy is None:
            return
        if result.contour_points:
            draw.line([*result.contour_points, result.contour_points[0]], fill=(0, 210, 110, 255), width=2)
        self._draw_point(draw, result.legacy.heel_point, "Old heel", (255, 80, 80, 255), radius=5)
        self._draw_point(draw, result.legacy.toe_point, "Old toe", (80, 160, 255, 255), radius=5)
        draw.line(
            (
                result.legacy.width_left_point.x,
                result.legacy.width_left_point.y,
                result.legacy.width_right_point.x,
                result.legacy.width_right_point.y,
            ),
            fill=(255, 80, 220, 255),
            width=3,
        )
        draw.line(
            (
                result.legacy.heel_point.x,
                result.legacy.heel_point.y,
                result.legacy.toe_point.x,
                result.legacy.toe_point.y,
            ),
            fill=(80, 160, 255, 220),
            width=2,
        )

    def _draw_anatomical_primitives(self, draw: ImageDraw.ImageDraw, result: FootMeasurementResult) -> None:
        self._draw_region(draw, result.heel_region, (255, 120, 80, 55), (255, 120, 80, 210))
        self._draw_region(draw, result.forefoot_region, (255, 80, 220, 45), (255, 80, 220, 210))
        if result.contour_points:
            draw.line([*result.contour_points, result.contour_points[0]], fill=(0, 210, 110, 255), width=2)
        self._draw_point(draw, result.heel_point, "New heel", (255, 80, 80, 255), radius=5)
        self._draw_point(draw, result.toe_point, "New toe", (30, 100, 255, 255), radius=5)
        draw.line(
            (
                result.width_left_point.x,
                result.width_left_point.y,
                result.width_right_point.x,
                result.width_right_point.y,
            ),
            fill=(255, 80, 220, 255),
            width=3,
        )
        draw.line(
            (result.heel_point.x, result.heel_point.y, result.toe_point.x, result.toe_point.y),
            fill=(30, 100, 255, 220),
            width=2,
        )

    def _draw_region(self, draw: ImageDraw.ImageDraw, region: RegionDebug | None, fill, outline) -> None:
        if region and len(region.polygon) >= 3:
            draw.polygon(region.polygon, fill=fill, outline=outline)

    def _distance(self, first: MeasurementPoint, second: MeasurementPoint) -> float:
        return sqrt((first.x - second.x) ** 2 + (first.y - second.y) ** 2)

    def _float_or_none(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _draw_point(
        self,
        draw: ImageDraw.ImageDraw,
        point: MeasurementPoint,
        label: str,
        color,
        radius: int = 6,
    ) -> None:
        draw.ellipse(
            (point.x - radius, point.y - radius, point.x + radius, point.y + radius),
            fill=color,
            outline=(255, 255, 255, 255),
            width=2,
        )
        if label:
            draw.text((point.x + 8, point.y + 4), label, fill=color)

    def _point_tuple(self, point: MeasurementPoint) -> tuple[float, float]:
        return (point.x, point.y)
