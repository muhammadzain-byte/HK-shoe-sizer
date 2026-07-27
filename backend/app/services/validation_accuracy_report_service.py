from __future__ import annotations

from statistics import mean, median
from typing import Any

from app.models.validation_benchmark_result import ValidationBenchmarkResult


class ValidationAccuracyReportService:
    minimum_claim_cases = 50
    minimum_device_groups = 3

    def summarize(self, results: list[ValidationBenchmarkResult | dict[str, Any]]) -> dict[str, Any]:
        rows = [self._to_dict(result) for result in results]
        completed = [row for row in rows if row.get("failure_stage") is None]
        length_errors = [row["length_abs_error_mm"] for row in completed if row.get("length_abs_error_mm") is not None]
        width_errors = [row["width_abs_error_mm"] for row in completed if row.get("width_abs_error_mm") is not None]
        summary = {
            "case_count": len(rows),
            "completed_count": len(completed),
            "failed_count": len(rows) - len(completed),
            "mean_length_abs_error_mm": self._mean(length_errors),
            "mean_width_abs_error_mm": self._mean(width_errors),
            "median_length_abs_error_mm": self._median(length_errors),
            "median_width_abs_error_mm": self._median(width_errors),
            "p90_length_abs_error_mm": self._percentile(length_errors, 0.9),
            "p90_width_abs_error_mm": self._percentile(width_errors, 0.9),
            "within_3mm_length_percent": self._within(length_errors, 3),
            "within_5mm_length_percent": self._within(length_errors, 5),
            "within_3mm_width_percent": self._within(width_errors, 3),
            "within_5mm_width_percent": self._within(width_errors, 5),
            "failure_stage_counts": self._failure_stage_counts(rows),
            "common_failure_reasons": self._failure_reason_counts(rows),
            "accuracy_claim_allowed": False,
            "reason_accuracy_claim_blocked": "",
        }
        summary["accuracy_claim_allowed"], summary["reason_accuracy_claim_blocked"] = self._claim_status(
            summary,
            rows,
        )
        return summary

    def _claim_status(self, summary: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[bool, str]:
        if summary["completed_count"] < self.minimum_claim_cases:
            return False, "At least 50 completed real-device benchmark cases are required."
        groups = {
            (row.get("pipeline_output_json") or {}).get("device_group")
            for row in rows
            if (row.get("pipeline_output_json") or {}).get("device_group")
        }
        if len(groups) < self.minimum_device_groups:
            return False, "At least 3 device/browser groups are required."
        if (summary["mean_length_abs_error_mm"] or 999) > 5:
            return False, "Mean length absolute error must be <= 5 mm."
        if (summary["p90_length_abs_error_mm"] or 999) > 8:
            return False, "P90 length absolute error must be <= 8 mm."
        scale_failures = summary["failure_stage_counts"].get("scale", 0)
        if rows and scale_failures / len(rows) > 0.10:
            return False, "Scale failure rate must be <= 10%."
        return True, "Internal validation threshold met; still not a production accuracy claim."

    def _to_dict(self, result: ValidationBenchmarkResult | dict[str, Any]) -> dict[str, Any]:
        if isinstance(result, dict):
            return result
        return {
            "length_abs_error_mm": result.length_abs_error_mm,
            "width_abs_error_mm": result.width_abs_error_mm,
            "failure_stage": result.failure_stage,
            "failure_reasons_json": result.failure_reasons_json,
            "pipeline_output_json": result.pipeline_output_json,
        }

    def _mean(self, values: list[float]) -> float | None:
        return round(mean(values), 3) if values else None

    def _median(self, values: list[float]) -> float | None:
        return round(median(values), 3) if values else None

    def _percentile(self, values: list[float], percentile: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
        return round(ordered[index], 3)

    def _within(self, values: list[float], threshold: float) -> float | None:
        if not values:
            return None
        return round(sum(1 for value in values if value <= threshold) / len(values) * 100, 2)

    def _failure_stage_counts(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            stage = row.get("failure_stage")
            if stage:
                counts[stage] = counts.get(stage, 0) + 1
        return counts

    def _failure_reason_counts(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            for reason in row.get("failure_reasons_json") or []:
                counts[reason] = counts.get(reason, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True)[:10])
