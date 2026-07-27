from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/shoesizing")
os.environ.setdefault("JWT_SECRET_KEY", "local-measurement-script-secret")
os.environ.setdefault("AWS_S3_BUCKET", "local-measurement-script-bucket")

from app.services.ai.sam2_foot_segmentation_service import SAM2FootSegmentationService  # noqa: E402
from app.services.anatomical_landmark_validator import AnatomicalLandmarkValidator  # noqa: E402
from app.services.measurement_service import MeasurementService  # noqa: E402


def serialize_value(value):
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "width") and hasattr(value, "height"):
        return {
            "x": int(value.x),
            "y": int(value.y),
            "width": int(value.width),
            "height": int(value.height),
        }
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [serialize_value(item) for item in value]
    return value


def serialize_diagnostics(diagnostics):
    if not diagnostics:
        return None
    return serialize_value(dict(diagnostics))


def save_refined_mask_and_overlay(image: Image.Image, mask, mask_path: Path, overlay_path: Path) -> None:
    import numpy as np

    boolean_mask = np.asarray(mask).astype(bool)
    mask_image = Image.fromarray(boolean_mask.astype("uint8") * 255, mode="L")
    mask_image.save(mask_path)
    overlay = image.convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 220, 120, 105))
    overlay.alpha_composite(
        Image.composite(layer, Image.new("RGBA", image.size, (0, 0, 0, 0)), mask_image)
    )
    draw = ImageDraw.Draw(overlay)
    ys, xs = np.where(boolean_mask)
    if len(xs) and len(ys):
        draw.rectangle(
            (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1),
            outline=(0, 255, 120, 255),
            width=4,
        )
    overlay.convert("RGB").save(overlay_path)


def save_mask_overlay(image: Image.Image, mask, output_path: Path, color=(255, 48, 48, 110)) -> None:
    import numpy as np

    boolean_mask = np.asarray(mask).astype(bool)
    mask_image = Image.fromarray(boolean_mask.astype("uint8") * 255, mode="L")
    overlay = image.convert("RGBA")
    layer = Image.new("RGBA", image.size, color)
    overlay.alpha_composite(
        Image.composite(layer, Image.new("RGBA", image.size, (0, 0, 0, 0)), mask_image)
    )
    overlay.convert("RGB").save(output_path)


def save_heel_boundary_debug(
    image: Image.Image,
    mask,
    refinement_metadata: dict | None,
    output_path: Path,
) -> None:
    import numpy as np

    boolean_mask = np.asarray(mask).astype(bool)
    mask_image = Image.fromarray(boolean_mask.astype("uint8") * 255, mode="L")
    overlay = image.convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 220, 120, 90))
    overlay.alpha_composite(
        Image.composite(layer, Image.new("RGBA", image.size, (0, 0, 0, 0)), mask_image)
    )
    draw = ImageDraw.Draw(overlay, "RGBA")
    metadata = refinement_metadata or {}
    curve_points = metadata.get("heel_curve_points") or []
    if curve_points:
        draw.line(
            [(float(point["x"]), float(point["y"])) for point in curve_points],
            fill=(30, 80, 255, 255),
            width=5,
        )
    center = metadata.get("heel_center")
    if isinstance(center, dict):
        x = float(center["x"])
        y = float(center["y"])
        draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(255, 60, 60, 255), outline=(255, 255, 255, 255), width=2)
        draw.text((x + 8, y + 4), "heel center", fill=(255, 60, 60, 255))
    draw.text(
        (12, 12),
        f"heel boundary: {metadata.get('heel_boundary_type', 'unknown')} "
        f"confidence={float(metadata.get('heel_boundary_confidence', 0)):.2f}",
        fill=(0, 0, 0, 255),
    )
    overlay.convert("RGB").save(output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify pixel-only foot measurement engine.")
    parser.add_argument("--image", required=True, help="Path to a JPG, PNG, or WebP image.")
    parser.add_argument("--output-dir", default=".", help="Output directory for measurement artifacts.")
    parser.add_argument(
        "--validate-landmarks",
        action="store_true",
        help="Run anatomical landmark validation and emit measurement_quality_report.json.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image_path = Path(args.image).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not image_path.exists():
        print(f"FAIL: image not found: {image_path}", file=sys.stderr)
        return 1

    model_id = os.getenv("SAM2_MODEL_ID", "facebook/sam2.1-hiera-large")
    device = os.getenv("SAM2_DEVICE", "cpu")

    try:
        image = Image.open(image_path).convert("RGB")
        segmentation_service = SAM2FootSegmentationService(model_id=model_id, device=device)
        measurement_service = MeasurementService()
        landmark_validator = AnatomicalLandmarkValidator()

        segmentation_start = time.perf_counter()
        segmentation = segmentation_service.segment(image)
        segmentation_time = time.perf_counter() - segmentation_start
        selected = segmentation.feet[0] if segmentation.feet else None
        if not selected or selected.mask is None:
            print("FAIL: no selected foot mask available", file=sys.stderr)
            return 1
        diagnostics = serialize_diagnostics(selected.diagnostics)
        refinement_metadata = diagnostics.get("refinement") if isinstance(diagnostics, dict) else None

        measurement_start = time.perf_counter()
        result = measurement_service.measure_mask(
            selected.mask,
            float(segmentation.confidence_score) if segmentation.confidence_score is not None else None,
            refinement_metadata=refinement_metadata,
        )
        measurement_time = time.perf_counter() - measurement_start

        overlay_path = output_dir / "measurement_overlay.png"
        anatomical_overlay_path = output_dir / "anatomical_measurement_overlay.png"
        landmark_validation_overlay_path = output_dir / "anatomical_landmark_validation_overlay.png"
        comparison_overlay_path = output_dir / "measurement_comparison_overlay.png"
        metadata_path = output_dir / "measurement_metadata.json"
        refined_mask_path = output_dir / "refined_foot_mask.png"
        refined_overlay_path = output_dir / "refined_foot_overlay.png"
        segmentation_overlay_path = output_dir / "segmentation_overlay.png"
        selected_foot_path = output_dir / "selected_foot.png"
        heel_boundary_debug_path = output_dir / "heel_boundary_debug.png"
        refinement_metadata_path = output_dir / "refinement_metadata.json"
        quality_report_path = output_dir / "measurement_quality_report.json"
        measurement_service.save_overlay(image, result, overlay_path)
        measurement_service.save_anatomical_overlay(image, result, anatomical_overlay_path)
        measurement_service.save_comparison_overlay(image, result, comparison_overlay_path)
        save_refined_mask_and_overlay(image, selected.mask, refined_mask_path, refined_overlay_path)
        save_mask_overlay(image, selected.mask, segmentation_overlay_path)
        save_mask_overlay(image, selected.mask, selected_foot_path, color=(0, 220, 120, 105))
        save_heel_boundary_debug(image, selected.mask, refinement_metadata, heel_boundary_debug_path)

        validation_report = None
        if args.validate_landmarks:
            validation_report = landmark_validator.validate(
                original_image=image,
                selected_candidate_mask=None,
                refined_foot_mask=selected.mask,
                heel_boundary_metadata=refinement_metadata,
                measurement_result=result,
                width_profile=(
                    refinement_metadata.get("width_profile")
                    if isinstance(refinement_metadata, dict)
                    else None
                ),
                contour_points=result.contour_points,
            )
            landmark_validator.save_overlay(
                image=image,
                refined_foot_mask=selected.mask,
                measurement_result=result,
                report=validation_report,
                heel_boundary_metadata=refinement_metadata,
                output_path=landmark_validation_overlay_path,
            )
            quality_report_path.write_text(
                json.dumps(validation_report.to_dict(), indent=2),
                encoding="utf-8",
            )
        if refinement_metadata:
            refinement_metadata_path.write_text(json.dumps(refinement_metadata, indent=2), encoding="utf-8")
        metadata = {
            "model_id": model_id,
            "device": device,
            "segmentation_time": round(segmentation_time, 4),
            "measurement_time": round(measurement_time, 4),
            "measurement_status": (
                validation_report.measurement_status
                if validation_report is not None
                else result.measurement_status
            ),
            "raw_measurement_status": result.measurement_status,
            "foot_length_pixels": result.foot_length_pixels,
            "foot_width_pixels": result.foot_width_pixels,
            "heel_point": {"x": result.heel_point.x, "y": result.heel_point.y},
            "toe_point": {"x": result.toe_point.x, "y": result.toe_point.y},
            "width_points": {
                "left": {"x": result.width_left_point.x, "y": result.width_left_point.y},
                "right": {"x": result.width_right_point.x, "y": result.width_right_point.y},
            },
            "confidence_score": result.confidence_score,
            "quality_issues": result.quality_issues,
            "anatomical_landmark_validation": (
                validation_report.to_dict() if validation_report is not None else None
            ),
            "toe_candidates": [{"x": point.x, "y": point.y} for point in result.toe_candidates],
            "legacy_measurement": {
                "foot_length_pixels": result.legacy.foot_length_pixels if result.legacy else None,
                "foot_width_pixels": result.legacy.foot_width_pixels if result.legacy else None,
                "heel_point": (
                    {"x": result.legacy.heel_point.x, "y": result.legacy.heel_point.y}
                    if result.legacy
                    else None
                ),
                "toe_point": (
                    {"x": result.legacy.toe_point.x, "y": result.legacy.toe_point.y}
                    if result.legacy
                    else None
                ),
                "width_points": (
                    {
                        "left": {
                            "x": result.legacy.width_left_point.x,
                            "y": result.legacy.width_left_point.y,
                        },
                        "right": {
                            "x": result.legacy.width_right_point.x,
                            "y": result.legacy.width_right_point.y,
                        },
                    }
                    if result.legacy
                    else None
                ),
            },
            "selected_foot": {
                "bbox": {
                    "x": selected.bbox.x,
                    "y": selected.bbox.y,
                "width": selected.bbox.width,
                "height": selected.bbox.height,
                },
                "selection_confidence": float(selected.confidence_score or 0),
                "diagnostics": diagnostics,
            },
            "outputs": {
                "segmentation_overlay": str(segmentation_overlay_path),
                "selected_foot": str(selected_foot_path),
                "refined_foot_mask": str(refined_mask_path),
                "refined_foot_overlay": str(refined_overlay_path),
                "heel_boundary_debug": str(heel_boundary_debug_path),
                "refinement_metadata": str(refinement_metadata_path),
                "measurement_overlay": str(overlay_path),
                "anatomical_measurement_overlay": str(anatomical_overlay_path),
                "anatomical_landmark_validation_overlay": str(landmark_validation_overlay_path),
                "measurement_comparison_overlay": str(comparison_overlay_path),
                "measurement_quality_report": str(quality_report_path),
                "measurement_metadata": str(metadata_path),
            },
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        print("PASS: Measurement engine completed successfully")
        print(f"Model ID: {model_id}")
        print(f"Device: {device}")
        print(f"Segmentation Time: {segmentation_time:.4f}s")
        print(f"Measurement Time: {measurement_time:.4f}s")
        print(f"Foot Length Pixels: {result.foot_length_pixels}")
        print(f"Foot Width Pixels: {result.foot_width_pixels}")
        print(f"Heel Point: {metadata['heel_point']}")
        print(f"Toe Point: {metadata['toe_point']}")
        print(f"Width Points: {metadata['width_points']}")
        print(f"Confidence Score: {result.confidence_score}")
        if validation_report is not None:
            print(f"Landmark Raw Trust Score: {validation_report.trust_score_raw}")
            print(f"Landmark Final Trust Score: {validation_report.trust_score_after_penalties}")
            print(f"Landmark Measurement Status: {validation_report.measurement_status}")
            print(f"Landmark Recommendation: {validation_report.recommendation}")
            print(f"Landmark Risk Scores: {validation_report.risk_scores}")
            print(f"Landmark Penalties: {validation_report.penalties}")
            print(f"Landmark Hard Gates: {validation_report.hard_gates_triggered}")
            print(f"Landmark Issues: {validation_report.issues}")
            print(f"Saved Landmark Validation Overlay: {landmark_validation_overlay_path}")
            print(f"Saved Measurement Quality Report: {quality_report_path}")
        print(f"Saved Segmentation Overlay: {segmentation_overlay_path}")
        print(f"Saved Selected Foot: {selected_foot_path}")
        print(f"Saved Refined Foot Mask: {refined_mask_path}")
        print(f"Saved Refined Foot Overlay: {refined_overlay_path}")
        print(f"Saved Heel Boundary Debug: {heel_boundary_debug_path}")
        print(f"Saved Refinement Metadata: {refinement_metadata_path}")
        print(f"Saved Overlay: {overlay_path}")
        print(f"Saved Anatomical Overlay: {anatomical_overlay_path}")
        print(f"Saved Comparison Overlay: {comparison_overlay_path}")
        print(f"Saved Metadata: {metadata_path}")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
