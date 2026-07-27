from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_VALIDATION_COLUMNS = [
    "case_id",
    "case_label",
    "image_path",
    "device_label",
    "device_os",
    "browser",
    "capture_scenario",
    "foot_side",
    "ground_truth_length_mm",
    "ground_truth_width_mm",
    "ground_truth_source",
    "reference_mode",
    "reference_width_mm",
    "reference_height_mm",
    "reference_bbox_x",
    "reference_bbox_y",
    "reference_bbox_width",
    "reference_bbox_height",
    "reference_polygon_json",
    "expected_capture_status",
    "expected_measurement_status",
    "expected_scale_status",
    "expected_recommendation_status",
    "notes",
]


REFERENCE_DEFAULTS_MM = {
    "credit_card": (85.60, 53.98),
    "a4_paper": (210.00, 297.00),
    "calibration_card": (100.00, 60.00),
}


@dataclass(frozen=True)
class ValidationDatasetIssue:
    case_id: str | None
    field: str | None
    severity: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "field": self.field,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class ValidationDatasetRows:
    rows: list[dict[str, str]]
    columns: list[str]
    path: Path
    issues: list[ValidationDatasetIssue] = field(default_factory=list)


class ValidationDatasetLoader:
    """Loads validation CSVs while treating starter samples as non-evidence."""

    required_columns = REQUIRED_VALIDATION_COLUMNS
    reference_defaults_mm = REFERENCE_DEFAULTS_MM

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path.cwd()
        self.last_columns: list[str] = []

    def load_csv(self, path: str | Path) -> ValidationDatasetRows:
        csv_path = Path(path)
        issues: list[ValidationDatasetIssue] = []
        if not csv_path.exists():
            return ValidationDatasetRows(
                rows=[],
                columns=[],
                path=csv_path,
                issues=[
                    ValidationDatasetIssue(
                        case_id=None,
                        field=None,
                        severity="error",
                        message=f"CSV file does not exist: {csv_path}",
                    )
                ],
            )
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]
        self.last_columns = columns
        issues.extend(self.validate_columns(rows, columns=columns))
        return ValidationDatasetRows(rows=rows, columns=columns, path=csv_path, issues=issues)

    def validate_columns(
        self,
        rows: list[dict[str, str]],
        columns: list[str] | None = None,
    ) -> list[ValidationDatasetIssue]:
        present = set(columns or self.last_columns or (rows[0].keys() if rows else []))
        missing = [column for column in self.required_columns if column not in present]
        return [
            ValidationDatasetIssue(
                case_id=None,
                field=column,
                severity="error",
                message=f"Missing required column: {column}",
            )
            for column in missing
        ]

    def validate_case(
        self,
        row: dict[str, str],
        *,
        accuracy_mode: bool = False,
    ) -> list[ValidationDatasetIssue]:
        case_id = row.get("case_id") or None
        issues: list[ValidationDatasetIssue] = []
        image_path = row.get("image_path") or ""
        if image_path:
            resolved = self._resolve_path(image_path)
            if not resolved.exists():
                issues.append(
                    ValidationDatasetIssue(
                        case_id=case_id,
                        field="image_path",
                        severity="warning",
                        message="Image path does not exist yet. Sample/template rows are not accuracy evidence.",
                    )
                )
        else:
            issues.append(
                ValidationDatasetIssue(
                    case_id=case_id,
                    field="image_path",
                    severity="warning",
                    message="Image path is blank.",
                )
            )

        mode = (row.get("reference_mode") or "none").strip()
        if mode and mode != "none":
            width = self._positive_float(row.get("reference_width_mm"))
            height = self._positive_float(row.get("reference_height_mm"))
            if width is None or height is None:
                issues.append(
                    ValidationDatasetIssue(
                        case_id=case_id,
                        field="reference_width_mm",
                        severity="error",
                        message="Reference dimensions are required when reference_mode is not none.",
                    )
                )
            if mode not in {"credit_card", "a4_paper", "calibration_card", "custom_object"}:
                issues.append(
                    ValidationDatasetIssue(
                        case_id=case_id,
                        field="reference_mode",
                        severity="error",
                        message=f"Unsupported reference mode: {mode}",
                    )
                )

        length = self._positive_float(row.get("ground_truth_length_mm"))
        width = self._positive_float(row.get("ground_truth_width_mm"))
        if accuracy_mode and (length is None or width is None):
            issues.append(
                ValidationDatasetIssue(
                    case_id=case_id,
                    field="ground_truth_length_mm",
                    severity="error",
                    message="Ground-truth length and width are required in accuracy mode.",
                )
            )
        return issues

    def summarize_dataset(
        self,
        rows: list[dict[str, str]],
        *,
        accuracy_mode: bool = False,
    ) -> dict[str, Any]:
        issues: list[ValidationDatasetIssue] = []
        scenario_counts: dict[str, int] = {}
        real_image_count = 0
        missing_image_count = 0
        ground_truth_count = 0
        reference_object_count = 0

        for row in rows:
            issues.extend(self.validate_case(row, accuracy_mode=accuracy_mode))
            scenario = row.get("capture_scenario") or "unknown"
            scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1
            image_path = row.get("image_path") or ""
            if image_path and self._resolve_path(image_path).exists():
                real_image_count += 1
            else:
                missing_image_count += 1
            if (
                self._positive_float(row.get("ground_truth_length_mm")) is not None
                and self._positive_float(row.get("ground_truth_width_mm")) is not None
            ):
                ground_truth_count += 1
            if (row.get("reference_mode") or "none").strip() != "none":
                reference_object_count += 1

        return {
            "case_count": len(rows),
            "real_image_count": real_image_count,
            "missing_image_count": missing_image_count,
            "ground_truth_count": ground_truth_count,
            "reference_object_count": reference_object_count,
            "scenario_counts": scenario_counts,
            "issues": [issue.to_dict() for issue in issues],
        }

    def _resolve_path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.project_root / path

    def _positive_float(self, value: str | None) -> float | None:
        try:
            if value is None or str(value).strip() == "":
                return None
            parsed = float(value)
        except ValueError:
            return None
        return parsed if parsed > 0 else None
