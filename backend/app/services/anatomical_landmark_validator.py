from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from app.services.measurement_service import FootMeasurementResult, MeasurementPoint


@dataclass(frozen=True)
class AnatomicalValidationReport:
    trusted: bool
    trust_score: float
    trust_score_raw: float
    trust_score_after_penalties: float
    measurement_status: str
    landmark_scores: dict[str, float]
    risk_scores: dict[str, float] = field(default_factory=dict)
    penalties: dict[str, float] = field(default_factory=dict)
    hard_gates_triggered: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    recommendation: str = "needs_review"
    recommendation_reason: str = ""
    debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trusted": self.trusted,
            "trust_score": self.trust_score,
            "trust_score_raw": self.trust_score_raw,
            "trust_score_after_penalties": self.trust_score_after_penalties,
            "measurement_status": self.measurement_status,
            "recommendation": self.recommendation,
            "landmark_scores": self.landmark_scores,
            "risk_scores": self.risk_scores,
            "penalties": self.penalties,
            "hard_gates_triggered": self.hard_gates_triggered,
            "issues": self.issues,
            "recommendation_reason": self.recommendation_reason,
            "debug": self.debug,
        }


class AnatomicalLandmarkValidator:
    """Measurement-grade anatomical checks for pixel-only foot landmarks."""

    def validate(
        self,
        original_image: Image.Image | None,
        selected_candidate_mask: Any | None,
        refined_foot_mask: Any,
        heel_boundary_metadata: dict[str, Any] | None,
        measurement_result: FootMeasurementResult,
        width_profile: list[dict[str, float]] | None = None,
        contour_points: list[tuple[int, int]] | None = None,
    ) -> AnatomicalValidationReport:
        binary = self._normalize_mask(refined_foot_mask)
        original = self._normalize_mask(selected_candidate_mask) if selected_candidate_mask is not None else binary
        frame, canonical, points = self._mask_geometry(binary)
        metadata = heel_boundary_metadata or {}
        contour = contour_points or measurement_result.contour_points

        scores: dict[str, float] = {}
        issues: list[str] = []
        debug: dict[str, Any] = {}

        scores["toe_point"], toe_issues, toe_debug = self._validate_toe_point(
            binary,
            frame,
            canonical,
            measurement_result,
        )
        issues.extend(toe_issues)
        debug["toe_point"] = toe_debug

        scores["heel_center"], heel_issues, heel_debug = self._validate_heel_center(
            binary,
            frame,
            canonical,
            metadata,
            measurement_result.heel_point,
        )
        issues.extend(heel_issues)
        debug["heel_center"] = heel_debug

        scores["heel_boundary"], boundary_issues, boundary_debug = self._validate_heel_boundary(
            original,
            binary,
            metadata,
            width_profile or metadata.get("width_profile") or [],
        )
        issues.extend(boundary_issues)
        debug["heel_boundary"] = boundary_debug

        scores["forefoot_width"], width_issues, width_debug = self._validate_forefoot_width(
            binary,
            frame,
            canonical,
            measurement_result,
        )
        issues.extend(width_issues)
        debug["forefoot_width"] = width_debug

        scores["mask_quality"], mask_issues, mask_debug = self._validate_mask_quality(binary, original)
        issues.extend(mask_issues)
        debug["mask_quality"] = mask_debug

        risk_scores = self._risk_scores(debug, metadata, measurement_result)
        penalties = self._risk_penalties(risk_scores, metadata)
        hard_gates = self._hard_gates(risk_scores, metadata)
        issues.extend(self._risk_issues(risk_scores, penalties, hard_gates))

        trust_score_raw = round(
            0.20 * scores["toe_point"]
            + 0.20 * scores["heel_center"]
            + 0.20 * scores["heel_boundary"]
            + 0.20 * scores["forefoot_width"]
            + 0.20 * scores["mask_quality"],
            4,
        )
        trust_score = round(max(0.0, trust_score_raw - sum(penalties.values())), 4)
        for name, score in scores.items():
            if score < 0.58:
                issues.append(f"major: {name} landmark score is too low")
            elif score < 0.70:
                issues.append(f"minor: {name} landmark score needs review")

        if self._has_major_issue(issues) or any(gate.endswith("_fail") for gate in hard_gates):
            status = "failed_quality_gate"
            recommendation = "reject"
            trusted = False
        elif trust_score >= 0.90 and not issues and not hard_gates:
            status = "trusted"
            recommendation = "accept"
            trusted = True
        elif trust_score >= 0.72:
            status = "needs_review"
            recommendation = "needs_review"
            trusted = False
        else:
            status = "failed_quality_gate"
            recommendation = "reject"
            trusted = False
        recommendation_reason = self._recommendation_reason(status, risk_scores, hard_gates, issues)

        debug["image_size"] = original_image.size if original_image is not None else None
        debug["contour_point_count"] = len(contour)
        return AnatomicalValidationReport(
            trusted=trusted,
            trust_score=trust_score,
            trust_score_raw=trust_score_raw,
            trust_score_after_penalties=trust_score,
            measurement_status=status,
            landmark_scores={key: round(value, 4) for key, value in scores.items()},
            risk_scores={key: round(value, 4) for key, value in risk_scores.items()},
            penalties={key: round(value, 4) for key, value in penalties.items()},
            hard_gates_triggered=hard_gates,
            issues=issues,
            recommendation=recommendation,
            recommendation_reason=recommendation_reason,
            debug=debug,
        )

    def save_overlay(
        self,
        image: Image.Image,
        refined_foot_mask: Any,
        measurement_result: FootMeasurementResult,
        report: AnatomicalValidationReport,
        heel_boundary_metadata: dict[str, Any] | None,
        output_path: str | Path,
        selected_candidate_mask: Any | None = None,
    ) -> None:
        refined = self._normalize_mask(refined_foot_mask)
        selected = self._normalize_mask(selected_candidate_mask) if selected_candidate_mask is not None else refined
        removed = selected & ~refined

        overlay = image.convert("RGBA")
        for mask, color in (
            (removed, (255, 135, 40, 145)),
            (refined, (0, 220, 120, 80)),
        ):
            layer = Image.new("RGBA", image.size, color)
            mask_image = Image.fromarray(mask.astype("uint8") * 255, mode="L")
            overlay.alpha_composite(
                Image.composite(layer, Image.new("RGBA", image.size, (0, 0, 0, 0)), mask_image)
            )

        draw = ImageDraw.Draw(overlay, "RGBA")
        if measurement_result.contour_points:
            draw.line(
                [*measurement_result.contour_points, measurement_result.contour_points[0]],
                fill=(0, 210, 110, 255),
                width=3,
            )

        metadata = heel_boundary_metadata or {}
        curve_points = metadata.get("heel_curve_points") or []
        if curve_points:
            draw.line(
                [(float(point["x"]), float(point["y"])) for point in curve_points],
                fill=(30, 80, 255, 255),
                width=5,
            )
        self._draw_point(draw, measurement_result.heel_point, "Heel center", (255, 70, 70, 255), 7)
        self._draw_point(draw, measurement_result.toe_point, "Selected toe", (30, 100, 255, 255), 7)
        for candidate in measurement_result.toe_candidates:
            if self._distance(candidate, measurement_result.toe_point) > 3:
                self._draw_point(draw, candidate, "", (80, 160, 255, 160), 4)
        draw.line(
            (
                measurement_result.width_left_point.x,
                measurement_result.width_left_point.y,
                measurement_result.width_right_point.x,
                measurement_result.width_right_point.y,
            ),
            fill=(255, 80, 220, 255),
            width=5,
        )
        self._draw_point(draw, measurement_result.width_left_point, "Width edge", (255, 80, 220, 255), 5)
        self._draw_point(draw, measurement_result.width_right_point, "", (255, 80, 220, 255), 5)

        x, y, w, _h = measurement_result.bounding_box
        draw.rectangle((x, y, x + 520, y + 230), fill=(255, 255, 255, 220))
        draw.text((x + 8, y + 8), f"Status: {report.measurement_status}", fill=(0, 0, 0, 255))
        draw.text(
            (x + 8, y + 28),
            f"Trust raw: {report.trust_score_raw:.2f}  final: {report.trust_score_after_penalties:.2f}",
            fill=(0, 0, 0, 255),
        )
        score_lines = [
            f"toe {report.landmark_scores['toe_point']:.2f}",
            f"heel center {report.landmark_scores['heel_center']:.2f}",
            f"heel boundary {report.landmark_scores['heel_boundary']:.2f}",
            f"forefoot width {report.landmark_scores['forefoot_width']:.2f}",
            f"mask {report.landmark_scores['mask_quality']:.2f}",
        ]
        for index, line in enumerate(score_lines):
            draw.text((x + 8, y + 52 + index * 18), line, fill=(0, 0, 0, 255))
        risk_lines = [
            f"lower_leg_risk {report.risk_scores.get('lower_leg_risk', 0):.2f}",
            f"top_crop_risk {report.risk_scores.get('top_crop_risk', 0):.2f}",
            f"rectangularity {report.risk_scores.get('rectangularity', 0):.2f}",
            f"completeness {report.risk_scores.get('completeness', 0):.2f}",
            f"recommendation {report.recommendation}",
        ]
        for index, line in enumerate(risk_lines):
            draw.text((x + 190, y + 52 + index * 18), line, fill=(0, 0, 0, 255))
        gates = ", ".join(report.hard_gates_triggered) if report.hard_gates_triggered else "none"
        draw.text((x + 8, y + 150), f"Hard gates: {gates}"[:75], fill=(150, 60, 0, 255))
        draw.text((x + 8, y + 170), report.recommendation_reason[:78], fill=(0, 0, 0, 255))
        if report.issues:
            draw.text((x + 8, y + 190), "; ".join(report.issues[:3])[:78], fill=(180, 40, 40, 255))

        overlay.convert("RGB").save(output_path)

    def _validate_toe_point(
        self,
        binary: Any,
        frame: dict[str, Any],
        canonical: Any,
        result: FootMeasurementResult,
    ) -> tuple[float, list[str], dict[str, Any]]:
        issues: list[str] = []
        v_min = float(canonical[:, 1].min())
        v_max = float(canonical[:, 1].max())
        height = max(v_max - v_min, 1.0)
        toe_uv = self._point_to_canonical(result.toe_point, frame)
        on_mask = self._point_on_mask(binary, result.toe_point, radius=3)
        top_score = 1.0 - min(max((toe_uv[1] - v_min) / (height * 0.16), 0.0), 1.0)
        candidates = result.toe_candidates or []
        candidate_distance = min((self._distance(result.toe_point, item) for item in candidates), default=999.0)
        candidate_score = 1.0 if candidate_distance <= max(8.0, height * 0.02) else 0.25
        peak_count = self._toe_peak_count(canonical, v_min, height)
        peak_score = min(peak_count / 3.0, 1.0)
        top_crop_risk = self._top_crop_risk(binary)
        bbox_top = float(result.bounding_box[1])
        near_top_bbox_edge = result.toe_point.y <= bbox_top + 2.0
        if peak_count <= 1:
            issues.append("minor: limited toe peak evidence")
        if not on_mask:
            issues.append("major: toe point is outside refined mask")
        if top_score < 0.35:
            issues.append("major: toe point is not on top toe contour")
        if top_crop_risk > 1.10:
            issues.append("major: toe contour appears cropped or missing")
        if near_top_bbox_edge and top_crop_risk >= 0.60:
            issues.append("minor: Toe point may be constrained by crop boundary.")
        score = (
            0.35 * (1.0 if on_mask else 0.0)
            + 0.30 * top_score
            + 0.20 * candidate_score
            + 0.15 * peak_score
        )
        if near_top_bbox_edge and top_crop_risk >= 0.60:
            score -= 0.10
        if not on_mask or top_score < 0.35 or top_crop_risk > 1.10:
            score = min(score, 0.45)
        return self._clamp(score), issues, {
            "on_mask": on_mask,
            "top_score": round(top_score, 4),
            "candidate_distance": round(candidate_distance, 2),
            "toe_peak_count": peak_count,
            "top_crop_risk": round(top_crop_risk, 4),
            "near_top_bbox_edge": near_top_bbox_edge,
        }

    def _validate_heel_center(
        self,
        binary: Any,
        frame: dict[str, Any],
        canonical: Any,
        metadata: dict[str, Any],
        heel_point: MeasurementPoint,
    ) -> tuple[float, list[str], dict[str, Any]]:
        issues: list[str] = []
        v_min = float(canonical[:, 1].min())
        v_max = float(canonical[:, 1].max())
        height = max(v_max - v_min, 1.0)
        heel_uv = self._point_to_canonical(heel_point, frame)
        axial_position = (heel_uv[1] - v_min) / height
        on_mask = self._point_on_mask(binary, heel_point, radius=4)
        center_score, edge_debug = self._heel_centering_score(canonical, heel_uv, height)
        curve_conf = self._float(metadata.get("heel_boundary_confidence"), 0.0)
        curve_points = metadata.get("heel_curve_points") or []
        curve_distance = self._distance_to_curve(heel_point, curve_points)
        curve_score = 1.0 if curve_distance <= max(16.0, height * 0.035) else 0.35
        position_score = min(max((axial_position - 0.68) / 0.22, 0.0), 1.0)

        if not on_mask:
            issues.append("major: heel center is outside refined mask")
        if axial_position < 0.76:
            issues.append("major: heel center is not posterior enough")
        if center_score < 0.45:
            issues.append("major: heel center is not centered between heel edges")
        if curve_points and curve_distance > max(20.0, height * 0.04):
            issues.append("major: heel center is not supported by heel curve")
        evidence = str(metadata.get("heel_boundary_evidence") or "inferred")
        if not curve_points:
            issues.append("minor: heel center uses straight fallback boundary")
        elif evidence != "contour_supported":
            issues.append("minor: Heel boundary is inferred and requires review.")

        score = (
            0.25 * (1.0 if on_mask else 0.0)
            + 0.25 * position_score
            + 0.25 * center_score
            + 0.15 * curve_score
            + 0.10 * min(curve_conf / 0.85, 1.0)
        )
        return self._clamp(score), issues, {
            "on_mask": on_mask,
            "axial_position": round(axial_position, 4),
            "center_score": round(center_score, 4),
            "curve_distance": round(curve_distance, 2),
            "heel_boundary_evidence": evidence,
            **edge_debug,
        }

    def _validate_heel_boundary(
        self,
        selected_mask: Any,
        refined_mask: Any,
        metadata: dict[str, Any],
        width_profile: list[dict[str, float]],
    ) -> tuple[float, list[str], dict[str, Any]]:
        issues: list[str] = []
        boundary_type = str(metadata.get("heel_boundary_type") or "straight_fallback")
        boundary_conf = self._float(metadata.get("heel_boundary_confidence"), 0.0)
        removed_ratio = self._float(metadata.get("removed_lower_leg_area_ratio"), 0.0)
        curve_points = metadata.get("heel_curve_points") or []
        curve_score = 1.0 if boundary_type == "curved" and len(curve_points) >= 7 else 0.55
        removed_score = 1.0 - min(abs(removed_ratio - 0.18) / 0.18, 1.0)
        if removed_ratio < 0.03:
            issues.append("major: lower-leg removal is too low")
            removed_score = min(removed_score, 0.25)
        if removed_ratio > 0.45:
            issues.append("major: heel may be over-trimmed")
            removed_score = min(removed_score, 0.25)
        if boundary_type != "curved":
            issues.append("minor: straight heel boundary fallback reduces trust")
        if boundary_conf < 0.45:
            issues.append("major: heel boundary confidence is too low")
        mask_removed = max(int(selected_mask.sum()) - int(refined_mask.sum()), 0) / max(int(selected_mask.sum()), 1)
        if removed_ratio == 0 and mask_removed > 0:
            removed_ratio = mask_removed
        profile_score = self._width_profile_boundary_score(width_profile)
        score = (
            0.30 * curve_score
            + 0.25 * min(boundary_conf / 0.85, 1.0)
            + 0.25 * removed_score
            + 0.20 * profile_score
        )
        return self._clamp(score), issues, {
            "heel_boundary_type": boundary_type,
            "heel_boundary_confidence": boundary_conf,
            "removed_lower_leg_area_ratio": removed_ratio,
            "profile_score": round(profile_score, 4),
        }

    def _validate_forefoot_width(
        self,
        binary: Any,
        frame: dict[str, Any],
        canonical: Any,
        result: FootMeasurementResult,
    ) -> tuple[float, list[str], dict[str, Any]]:
        import numpy as np

        issues: list[str] = []
        v_min = float(canonical[:, 1].min())
        v_max = float(canonical[:, 1].max())
        height = max(v_max - v_min, 1.0)
        left_uv = self._point_to_canonical(result.width_left_point, frame)
        right_uv = self._point_to_canonical(result.width_right_point, frame)
        mid_v = (left_uv[1] + right_uv[1]) / 2.0
        axial_position = (mid_v - v_min) / height
        zone_score = 1.0 - min(abs(axial_position - 0.42) / 0.22, 1.0)
        left_on_mask = self._point_on_mask(binary, result.width_left_point, radius=3)
        right_on_mask = self._point_on_mask(binary, result.width_right_point, radius=3)
        width_vector = np.array(
            [
                result.width_left_point.x - result.width_right_point.x,
                result.width_left_point.y - result.width_right_point.y,
            ],
            dtype=float,
        )
        axis_vector = np.array(
            [
                result.toe_point.x - result.heel_point.x,
                result.toe_point.y - result.heel_point.y,
            ],
            dtype=float,
        )
        perpendicular_score = 1.0 - abs(float(width_vector @ axis_vector) / max(np.linalg.norm(width_vector) * np.linalg.norm(axis_vector), 1.0))
        crossing_score = self._line_mask_coverage(binary, result.width_left_point, result.width_right_point)
        stable_score = self._forefoot_stable_width_score(canonical, left_uv, right_uv, v_min, height)

        if axial_position < 0.22 or axial_position > 0.68:
            issues.append("major: width line is outside forefoot zone")
        if not left_on_mask or not right_on_mask:
            issues.append("major: width endpoint is outside mask contour")
        if perpendicular_score < 0.70:
            issues.append("major: width line is not perpendicular enough to foot axis")
        if crossing_score < 0.70:
            issues.append("major: width line crosses too much background")

        score = (
            0.28 * zone_score
            + 0.22 * (1.0 if left_on_mask and right_on_mask else 0.0)
            + 0.20 * perpendicular_score
            + 0.18 * crossing_score
            + 0.12 * stable_score
        )
        return self._clamp(score), issues, {
            "axial_position": round(axial_position, 4),
            "perpendicular_score": round(perpendicular_score, 4),
            "line_mask_coverage": round(crossing_score, 4),
            "stable_width_score": round(stable_score, 4),
        }

    def _validate_mask_quality(self, refined_mask: Any, selected_mask: Any) -> tuple[float, list[str], dict[str, Any]]:
        import cv2
        import numpy as np

        issues: list[str] = []
        mask_u8 = refined_mask.astype("uint8") * 255
        contours, hierarchy = cv2.findContours(mask_u8, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0.0, ["major: refined mask has no contour"], {}
        external = [contour for index, contour in enumerate(contours) if hierarchy[0][index][3] == -1]
        largest = max(external, key=cv2.contourArea)
        contour_area = max(float(cv2.contourArea(largest)), 1.0)
        hull_area = max(float(cv2.contourArea(cv2.convexHull(largest))), 1.0)
        x, y, w, h = cv2.boundingRect(largest)
        bbox_area = max(float(w * h), 1.0)
        component_score = 1.0 if len(external) == 1 else max(0.2, 1.0 - 0.2 * (len(external) - 1))
        hole_area = 0.0
        for index, contour in enumerate(contours):
            if hierarchy[0][index][3] != -1:
                hole_area += float(cv2.contourArea(contour))
        hole_ratio = hole_area / max(contour_area + hole_area, 1.0)
        solidity = contour_area / hull_area
        completeness = float(refined_mask.sum()) / bbox_area
        rectangularity = contour_area / bbox_area
        width_profile = self._vertical_width_profile(refined_mask)
        bottom_width = float(np.percentile(width_profile[-12:], 70)) if len(width_profile) >= 12 else 0.0
        forefoot_width = float(np.percentile(width_profile[20:50], 85)) if len(width_profile) >= 50 else max(width_profile, default=0.0)
        lower_leg_risk = bottom_width / max(forefoot_width, 1.0)
        top_width = float(np.percentile(width_profile[:8], 85)) if len(width_profile) >= 12 else 0.0
        top_crop_risk = top_width / max(forefoot_width, 1.0)

        if len(external) > 1:
            issues.append("major: refined mask has disconnected artifacts")
        if hole_ratio > 0.03:
            issues.append("major: refined mask contains large holes")
        if rectangularity > 0.86:
            issues.append("major: refined mask is overly rectangular")
        if lower_leg_risk > 0.90:
            issues.append("major: lower-leg continuation may remain in refined mask")
        if top_crop_risk > 1.10:
            issues.append("major: toe contour appears cropped or missing")
        if completeness < 0.35:
            issues.append("major: refined mask is incomplete")

        score = (
            0.22 * component_score
            + 0.20 * (1.0 - min(hole_ratio / 0.05, 1.0))
            + 0.20 * min(solidity / 0.82, 1.0)
            + 0.18 * min(completeness / 0.58, 1.0)
            + 0.12 * (1.0 - min(max(rectangularity - 0.72, 0.0) / 0.22, 1.0))
            + 0.04 * (1.0 - min(max(lower_leg_risk - 0.72, 0.0) / 0.30, 1.0))
            + 0.04 * (1.0 - min(max(top_crop_risk - 0.62, 0.0) / 0.30, 1.0))
        )
        return self._clamp(score), issues, {
            "components": len(external),
            "hole_ratio": round(hole_ratio, 4),
            "solidity": round(solidity, 4),
            "completeness": round(completeness, 4),
            "rectangularity": round(rectangularity, 4),
            "lower_leg_risk": round(lower_leg_risk, 4),
            "top_crop_risk": round(top_crop_risk, 4),
        }

    def _mask_geometry(self, binary: Any) -> tuple[dict[str, Any], Any, Any]:
        import numpy as np

        points_yx = np.argwhere(binary)
        if len(points_yx) == 0:
            raise ValueError("Refined foot mask is empty.")
        points = np.column_stack((points_yx[:, 1], points_yx[:, 0])).astype("float64")
        mean = points.mean(axis=0)
        centered = points - mean
        covariance = np.cov(centered.T)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        order = np.argsort(eigenvalues)[::-1]
        major_axis = eigenvectors[:, order[0]]
        minor_axis = eigenvectors[:, order[1]]
        if major_axis[1] < 0:
            major_axis = -major_axis
        frame = {"mean": mean, "major_axis": major_axis, "minor_axis": minor_axis}
        canonical = self._to_canonical(points, frame)
        if self._needs_orientation_flip(canonical):
            frame["major_axis"] = -frame["major_axis"]
            canonical = self._to_canonical(points, frame)
        return frame, canonical, points

    def _normalize_mask(self, mask: Any):
        import numpy as np

        if mask is None:
            raise ValueError("Mask is missing.")
        if hasattr(mask, "detach"):
            mask = mask.detach().cpu().numpy()
        elif isinstance(mask, Image.Image):
            mask = np.asarray(mask)
        array = np.asarray(mask)
        if array.ndim == 3:
            array = array.squeeze()
        if array.ndim != 2:
            raise ValueError(f"Expected 2D mask, got {array.shape}.")
        return array.astype(bool)

    def _to_canonical(self, points: Any, frame: dict[str, Any]):
        import numpy as np

        centered = points - frame["mean"]
        return np.column_stack((centered @ frame["minor_axis"], centered @ frame["major_axis"]))

    def _point_to_canonical(self, point: MeasurementPoint, frame: dict[str, Any]) -> tuple[float, float]:
        import numpy as np

        centered = np.array([point.x, point.y], dtype=float) - frame["mean"]
        return float(centered @ frame["minor_axis"]), float(centered @ frame["major_axis"])

    def _needs_orientation_flip(self, canonical: Any) -> bool:
        v_min = float(canonical[:, 1].min())
        v_max = float(canonical[:, 1].max())
        height = max(v_max - v_min, 1.0)
        top = canonical[canonical[:, 1] <= v_min + 0.12 * height]
        bottom = canonical[canonical[:, 1] >= v_max - 0.12 * height]
        top_width = self._canonical_width(top)
        bottom_width = self._canonical_width(bottom)
        return bottom_width > top_width * 1.18

    def _canonical_width(self, points: Any) -> float:
        if len(points) < 2:
            return 0.0
        return float(points[:, 0].max() - points[:, 0].min())

    def _point_on_mask(self, binary: Any, point: MeasurementPoint, radius: int) -> bool:
        y = int(round(point.y))
        x = int(round(point.x))
        y0 = max(0, y - radius)
        y1 = min(binary.shape[0], y + radius + 1)
        x0 = max(0, x - radius)
        x1 = min(binary.shape[1], x + radius + 1)
        return bool(binary[y0:y1, x0:x1].any())

    def _toe_peak_count(self, canonical: Any, v_min: float, height: float) -> int:
        import numpy as np

        toe_region = canonical[canonical[:, 1] <= v_min + 0.22 * height]
        if len(toe_region) < 10:
            return 0
        bins = np.linspace(float(toe_region[:, 0].min()), float(toe_region[:, 0].max()), 36)
        peaks = 0
        prev_tip = None
        for start, end in zip(bins[:-1], bins[1:], strict=True):
            section = toe_region[(toe_region[:, 0] >= start) & (toe_region[:, 0] < end)]
            if len(section) < 6:
                continue
            tip = float(section[:, 1].min())
            if prev_tip is None or tip < prev_tip - height * 0.012:
                peaks += 1
            prev_tip = tip
        return int(min(peaks, 5))

    def _heel_centering_score(self, canonical: Any, heel_uv: tuple[float, float], height: float) -> tuple[float, dict[str, Any]]:
        band = canonical[(canonical[:, 1] >= heel_uv[1] - 0.08 * height) & (canonical[:, 1] <= heel_uv[1] + 0.02 * height)]
        if len(band) < 4:
            return 0.2, {"heel_left_edge": None, "heel_right_edge": None}
        left = float(band[:, 0].min())
        right = float(band[:, 0].max())
        center = (left + right) / 2.0
        half_width = max((right - left) / 2.0, 1.0)
        score = 1.0 - min(abs(heel_uv[0] - center) / half_width, 1.0)
        return score, {
            "heel_left_edge_u": round(left, 2),
            "heel_right_edge_u": round(right, 2),
            "heel_center_offset": round(float(heel_uv[0] - center), 2),
        }

    def _distance_to_curve(self, point: MeasurementPoint, curve_points: list[dict[str, Any]]) -> float:
        if not curve_points:
            return 999.0
        return min(
            sqrt((point.x - float(item["x"])) ** 2 + (point.y - float(item["y"])) ** 2)
            for item in curve_points
        )

    def _width_profile_boundary_score(self, profile: list[dict[str, float]]) -> float:
        import numpy as np

        if not profile:
            return 0.55
        positions = np.array([float(row["axis_position"]) for row in profile], dtype=float)
        widths = np.array([float(row["width"]) for row in profile], dtype=float)
        active = widths > 0
        if active.sum() < 10:
            return 0.35
        forefoot = widths[(positions >= 0.22) & (positions <= 0.52) & active]
        lower = widths[(positions >= 0.72) & (positions <= 0.92) & active]
        if forefoot.size == 0 or lower.size == 0:
            return 0.45
        ratio = float(np.percentile(forefoot, 85) / max(np.percentile(lower, 45), 1.0))
        return self._clamp((ratio - 0.95) / 0.42)

    def _line_mask_coverage(self, binary: Any, left: MeasurementPoint, right: MeasurementPoint) -> float:
        import numpy as np

        samples = max(int(self._distance(left, right) // 4), 12)
        hits = 0
        for t in np.linspace(0, 1, samples):
            x = int(round(left.x * (1 - t) + right.x * t))
            y = int(round(left.y * (1 - t) + right.y * t))
            if 0 <= y < binary.shape[0] and 0 <= x < binary.shape[1] and binary[y, x]:
                hits += 1
        return hits / max(samples, 1)

    def _forefoot_stable_width_score(
        self,
        canonical: Any,
        left_uv: tuple[float, float],
        right_uv: tuple[float, float],
        v_min: float,
        height: float,
    ) -> float:
        import numpy as np

        target_width = abs(left_uv[0] - right_uv[0])
        widths = []
        for position in np.linspace(0.28, 0.64, 28):
            v = v_min + position * height
            section = canonical[(canonical[:, 1] >= v - 0.01 * height) & (canonical[:, 1] <= v + 0.01 * height)]
            if len(section) >= 4:
                widths.append(float(section[:, 0].max() - section[:, 0].min()))
        if not widths:
            return 0.25
        stable_width = float(np.percentile(widths, 90))
        return self._clamp(1.0 - abs(stable_width - target_width) / max(stable_width, 1.0))

    def _vertical_width_profile(self, mask: Any) -> list[float]:
        import numpy as np

        ys, xs = np.where(mask)
        if len(ys) == 0:
            return []
        y_min, y_max = int(ys.min()), int(ys.max())
        profile = []
        for start in np.linspace(y_min, y_max, 90):
            end = start + max((y_max - y_min) / 90, 1.0)
            band_xs = xs[(ys >= start) & (ys < end)]
            profile.append(float(band_xs.max() - band_xs.min()) if len(band_xs) >= 2 else 0.0)
        return profile

    def _top_crop_risk(self, mask: Any) -> float:
        profile = self._vertical_width_profile(mask)
        if len(profile) < 50:
            return 0.0
        import numpy as np

        top_width = float(np.percentile(profile[:8], 85))
        forefoot_width = float(np.percentile(profile[20:50], 85))
        return top_width / max(forefoot_width, 1.0)

    def _risk_scores(
        self,
        debug: dict[str, Any],
        metadata: dict[str, Any],
        result: FootMeasurementResult,
    ) -> dict[str, float]:
        mask_quality = debug.get("mask_quality", {})
        toe_debug = debug.get("toe_point", {})
        heel_debug = debug.get("heel_center", {})
        lower_leg_risk = self._float(mask_quality.get("lower_leg_risk"), 0.0)
        top_crop_risk = max(
            self._float(mask_quality.get("top_crop_risk"), 0.0),
            self._float(toe_debug.get("top_crop_risk"), 0.0),
        )
        rectangularity = self._float(mask_quality.get("rectangularity"), 0.0)
        completeness = self._float(mask_quality.get("completeness"), 1.0)
        crop_boundary_risk = top_crop_risk
        if toe_debug.get("near_top_bbox_edge") and top_crop_risk >= 0.60:
            crop_boundary_risk = max(crop_boundary_risk, 0.65)
        heel_inference_risk = self._heel_inference_risk(metadata, heel_debug)
        return {
            "lower_leg_risk": lower_leg_risk,
            "top_crop_risk": top_crop_risk,
            "rectangularity": rectangularity,
            "completeness": completeness,
            "crop_boundary_risk": crop_boundary_risk,
            "heel_inference_risk": heel_inference_risk,
            "measurement_confidence": self._float(result.confidence_score, 0.0),
        }

    def _risk_penalties(self, risk_scores: dict[str, float], metadata: dict[str, Any]) -> dict[str, float]:
        lower_leg_risk = risk_scores["lower_leg_risk"]
        top_crop_risk = risk_scores["top_crop_risk"]
        rectangularity = risk_scores["rectangularity"]
        completeness = risk_scores["completeness"]
        heel_type = str(metadata.get("heel_boundary_type") or "straight_fallback")
        heel_confidence = self._float(metadata.get("heel_boundary_confidence"), 0.0)
        heel_inference_risk = risk_scores["heel_inference_risk"]

        lower_leg_penalty = self._tiered_penalty(lower_leg_risk, [(0.75, 0.25), (0.60, 0.15), (0.40, 0.05)])
        top_crop_penalty = self._tiered_penalty(top_crop_risk, [(0.75, 0.25), (0.60, 0.15), (0.40, 0.05)])
        rectangularity_penalty = self._tiered_penalty(rectangularity, [(0.85, 0.15), (0.70, 0.08)])
        if completeness < 0.75:
            completeness_penalty = 0.18
        elif completeness < 0.85:
            completeness_penalty = 0.08
        else:
            completeness_penalty = 0.0
        if heel_type != "curved":
            heel_penalty = 0.10
        elif heel_confidence < 0.65:
            heel_penalty = 0.15
        elif heel_confidence < 0.85:
            heel_penalty = 0.08
        elif heel_inference_risk >= 0.25:
            heel_penalty = 0.05
        else:
            heel_penalty = 0.0
        return {
            "lower_leg_penalty": lower_leg_penalty,
            "top_crop_penalty": top_crop_penalty,
            "rectangularity_penalty": rectangularity_penalty,
            "completeness_penalty": completeness_penalty,
            "heel_penalty": heel_penalty,
        }

    def _hard_gates(self, risk_scores: dict[str, float], metadata: dict[str, Any]) -> list[str]:
        gates: list[str] = []
        lower_leg_risk = risk_scores["lower_leg_risk"]
        top_crop_risk = risk_scores["top_crop_risk"]
        removed_ratio = self._float(metadata.get("removed_lower_leg_area_ratio"), 0.0)
        heel_confidence = self._float(metadata.get("heel_boundary_confidence"), 0.0)
        strong_lower_leg_removal_evidence = (
            removed_ratio >= 0.15 and heel_confidence >= 0.90 and lower_leg_risk < 0.82
        )
        if lower_leg_risk >= 0.75:
            gates.append("lower_leg_risk_review" if strong_lower_leg_removal_evidence else "lower_leg_risk_fail")
        elif lower_leg_risk >= 0.60:
            gates.append("lower_leg_risk_review")
        if top_crop_risk >= 0.75:
            gates.append("top_crop_risk_fail")
        elif top_crop_risk >= 0.60:
            gates.append("top_crop_risk_review")
        if lower_leg_risk >= 0.60 and top_crop_risk >= 0.60:
            gates.append("combined_lower_leg_and_top_crop_review")
        return gates

    def _risk_issues(
        self,
        risk_scores: dict[str, float],
        penalties: dict[str, float],
        hard_gates: list[str],
    ) -> list[str]:
        issues: list[str] = []
        if risk_scores["lower_leg_risk"] >= 0.60:
            issues.append("review: lower_leg_risk exceeds trusted threshold")
        if risk_scores["top_crop_risk"] >= 0.60:
            issues.append("review: top_crop_risk exceeds trusted threshold")
        if risk_scores["rectangularity"] >= 0.75:
            issues.append("review: Mask is too rectangular / crop-like.")
        if risk_scores["completeness"] < 0.85:
            issues.append("review: Mask completeness is below trusted threshold.")
        if risk_scores["crop_boundary_risk"] >= 0.60:
            issues.append("review: crop boundary risk requires human inspection")
        if penalties["heel_penalty"] > 0:
            issues.append("review: heel boundary evidence reduces trust")
        if hard_gates:
            issues.append(f"review: hard gates triggered: {', '.join(hard_gates)}")
        return issues

    def _recommendation_reason(
        self,
        status: str,
        risk_scores: dict[str, float],
        hard_gates: list[str],
        issues: list[str],
    ) -> str:
        if status == "trusted":
            return "All landmark scores passed and no risk gate exceeded trusted thresholds."
        if any(gate.endswith("_fail") for gate in hard_gates):
            return f"Rejected because hard fail gates triggered: {', '.join(hard_gates)}."
        if self._has_major_issue(issues):
            return "Rejected because one or more anatomical landmarks failed a major quality rule."
        risk_summary = (
            f"Needs review because risk signals are elevated "
            f"(lower_leg_risk={risk_scores['lower_leg_risk']:.2f}, "
            f"top_crop_risk={risk_scores['top_crop_risk']:.2f}, "
            f"rectangularity={risk_scores['rectangularity']:.2f}, "
            f"completeness={risk_scores['completeness']:.2f})."
        )
        if hard_gates:
            return f"{risk_summary} Hard gates: {', '.join(hard_gates)}."
        return risk_summary

    def _heel_inference_risk(self, metadata: dict[str, Any], heel_debug: dict[str, Any]) -> float:
        evidence = str(metadata.get("heel_boundary_evidence") or heel_debug.get("heel_boundary_evidence") or "inferred")
        heel_type = str(metadata.get("heel_boundary_type") or "straight_fallback")
        confidence = self._float(metadata.get("heel_boundary_confidence"), 0.0)
        if heel_type != "curved":
            return 0.85
        if evidence == "contour_supported":
            return max(0.0, 0.20 - confidence * 0.10)
        return max(0.25, min(0.85, 1.0 - confidence + 0.25))

    def _tiered_penalty(self, value: float, tiers: list[tuple[float, float]]) -> float:
        for threshold, penalty in tiers:
            if value >= threshold:
                return penalty
        return 0.0

    def _has_major_issue(self, issues: list[str]) -> bool:
        return any(issue.startswith("major:") for issue in issues)

    def _float(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _clamp(self, value: float) -> float:
        return max(0.0, min(float(value), 1.0))

    def _distance(self, first: MeasurementPoint, second: MeasurementPoint) -> float:
        return sqrt((first.x - second.x) ** 2 + (first.y - second.y) ** 2)

    def _draw_point(
        self,
        draw: ImageDraw.ImageDraw,
        point: MeasurementPoint,
        label: str,
        color: tuple[int, int, int, int],
        radius: int,
    ) -> None:
        draw.ellipse(
            (point.x - radius, point.y - radius, point.x + radius, point.y + radius),
            fill=color,
            outline=(255, 255, 255, 255),
            width=2,
        )
        if label:
            draw.text((point.x + 8, point.y + 4), label, fill=color)
