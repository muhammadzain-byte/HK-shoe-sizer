from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.schemas.shoe_size import ShoeSizeRequest, ShoeSizeResponse


class ShoeSizeService:
    chart_dir = Path(__file__).resolve().parents[1] / "data" / "size_charts"
    supported_regions = {"EU", "US", "UK", "PK"}
    minimum_scale_confidence = 0.85

    def recommend_size(self, payload: ShoeSizeRequest | dict[str, Any]) -> ShoeSizeResponse:
        request = payload if isinstance(payload, ShoeSizeRequest) else ShoeSizeRequest.model_validate(payload)
        blocked = self.validate_inputs(request)
        if blocked:
            return blocked

        chart = self.load_chart(request.region)
        effective_length = request.foot_length_mm + self.apply_fit_preference(
            request.fit_preference
        ) + self.apply_shoe_type_allowance(request.shoe_type)
        selected = self.calculate_length_bucket(chart, effective_length)
        if selected is None:
            return self._blocked(
                "unsupported",
                request.region,
                "Foot length is outside the generic chart range.",
                "length_out_of_chart",
            )

        width_category = self.calculate_width_category(request.foot_width_mm, selected)
        alternates = self.generate_alternates(chart, selected, effective_length, request.fit_preference)
        fit_notes = self._fit_notes(width_category, request.shoe_type, request.fit_preference)
        confidence = 0.88 if width_category == "regular" else 0.82
        return ShoeSizeResponse(
            recommendation_status="recommended",
            recommended_size=str(selected["size"]),
            size_system=chart["system"],
            width_category=width_category,
            confidence=confidence,
            reasoning=[
                {
                    "code": "generic_chart_match",
                    "message": (
                        f"Matched {effective_length:.1f} mm adjusted length to generic "
                        f"{chart['system']} women chart."
                    ),
                },
                {
                    "code": "not_brand_specific",
                    "message": chart["source_note"],
                },
            ],
            alternate_sizes=alternates,
            fit_notes=fit_notes,
            blocked_reason=None,
        )

    def load_chart(self, region: str) -> dict[str, Any]:
        normalized = region.lower()
        path = self.chart_dir / f"women_{normalized}.json"
        if not path.exists():
            raise ValueError(f"Unsupported size region: {region}")
        return json.loads(path.read_text(encoding="utf-8"))

    def calculate_length_bucket(
        self,
        chart: dict[str, Any],
        effective_length_mm: float,
    ) -> dict[str, Any] | None:
        sizes = chart.get("sizes") or []
        for size in sizes:
            if size["min_length_mm"] <= effective_length_mm <= size["max_length_mm"]:
                return size
        if sizes and effective_length_mm < sizes[0]["min_length_mm"]:
            return sizes[0]
        if sizes and effective_length_mm <= sizes[-1]["max_length_mm"] + 4:
            return sizes[-1]
        return None

    def calculate_width_category(self, foot_width_mm: float, size: dict[str, Any]) -> str:
        if foot_width_mm < size["regular_width_min_mm"]:
            return "narrow"
        if foot_width_mm > size["regular_width_max_mm"]:
            return "wide"
        return "regular"

    def apply_fit_preference(self, fit_preference: str) -> float:
        return {
            "snug": 0.0,
            "regular": 3.0,
            "relaxed": 6.0,
        }.get(fit_preference, 3.0)

    def apply_shoe_type_allowance(self, shoe_type: str) -> float:
        return {
            "sneaker": 2.0,
            "heel": 0.0,
            "sandal": -1.0,
            "khussa": -1.0,
            "flat": 0.0,
            "formal": 1.0,
        }.get(shoe_type, 0.0)

    def generate_alternates(
        self,
        chart: dict[str, Any],
        selected: dict[str, Any],
        effective_length_mm: float,
        fit_preference: str,
    ) -> list[dict[str, str]]:
        sizes = chart.get("sizes") or []
        index = sizes.index(selected)
        alternates: list[dict[str, str]] = []
        if index > 0 and effective_length_mm <= selected["min_length_mm"] + 1.5:
            alternates.append({"size": str(sizes[index - 1]["size"]), "reason": "Near lower size boundary."})
        if index < len(sizes) - 1 and (
            effective_length_mm >= selected["max_length_mm"] - 1.5 or fit_preference == "relaxed"
        ):
            alternates.append({"size": str(sizes[index + 1]["size"]), "reason": "Comfort alternate."})
        return alternates

    def validate_inputs(self, request: ShoeSizeRequest) -> ShoeSizeResponse | None:
        if request.capture_status == "reject":
            return self._blocked(
                "blocked_by_capture_quality",
                request.region,
                "Capture quality was rejected.",
                "capture_rejected",
            )
        if request.gender.lower() not in {"women", "woman"}:
            return self._blocked(
                "unsupported",
                request.region,
                "Only women sizing is supported.",
                "women_only",
            )
        if request.region not in self.supported_regions:
            return self._blocked("unsupported", request.region, "Unsupported size region.", "unsupported_region")
        if request.measurement_status != "trusted":
            return self._blocked(
                "blocked_by_measurement_quality",
                request.region,
                "Measurement must be trusted before recommending size.",
                "measurement_not_trusted",
            )
        if request.scale_status != "available":
            return self._blocked(
                "blocked_by_scale",
                request.region,
                "Scale is unavailable, so real-world size is blocked.",
                "scale_unavailable",
            )
        if request.scale_confidence < self.minimum_scale_confidence:
            return self._blocked(
                "blocked_by_scale",
                request.region,
                "Scale confidence is below trusted threshold.",
                "scale_low_confidence",
            )
        if request.foot_length_mm is None or request.foot_width_mm is None:
            return self._blocked(
                "blocked_by_scale",
                request.region,
                "Foot length and width in millimeters are required.",
                "missing_real_world_measurement",
            )
        return None

    def _fit_notes(self, width_category: str, shoe_type: str, fit_preference: str) -> list[str]:
        notes = ["Generic chart only; validate with brand-specific sizing before production."]
        if width_category == "wide":
            notes.append("Foot width is above the generic regular range; consider wide fit where available.")
        if width_category == "narrow":
            notes.append("Foot width is below the generic regular range; check fit security.")
        if shoe_type == "sneaker":
            notes.append("Sneaker allowance adds a small comfort buffer.")
        if shoe_type == "heel":
            notes.append("Heel sizing avoids excessive size-up for stability.")
        if shoe_type == "khussa":
            notes.append("Khussa fit can be snug; treat this as advisory.")
        if fit_preference == "relaxed":
            notes.append("Relaxed preference may show the next size as an alternate.")
        return notes

    def _blocked(
        self,
        status: str,
        region: str,
        reason: str,
        code: str,
    ) -> ShoeSizeResponse:
        return ShoeSizeResponse(
            recommendation_status=status,
            recommended_size=None,
            size_system=region,
            width_category=None,
            confidence=0.0,
            reasoning=[{"code": code, "message": reason}],
            alternate_sizes=[],
            fit_notes=[],
            blocked_reason=reason,
        )
