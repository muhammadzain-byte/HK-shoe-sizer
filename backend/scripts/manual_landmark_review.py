from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print a manual landmark review checklist.")
    parser.add_argument("--image", required=True, help="Original foot image path.")
    parser.add_argument("--overlay", required=True, help="Landmark validation overlay path.")
    parser.add_argument("--measurement-metadata", required=True, help="measurement_metadata.json path.")
    parser.add_argument("--refinement-metadata", required=True, help="refinement_metadata.json path.")
    parser.add_argument("--quality-report", required=True, help="measurement_quality_report.json path.")
    return parser.parse_args()


def read_json(path: str) -> dict:
    payload = Path(path).expanduser().resolve()
    if not payload.exists():
        raise FileNotFoundError(f"Missing file: {payload}")
    return json.loads(payload.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    image_path = Path(args.image).expanduser().resolve()
    overlay_path = Path(args.overlay).expanduser().resolve()
    measurement = read_json(args.measurement_metadata)
    refinement = read_json(args.refinement_metadata)
    quality = read_json(args.quality_report)

    print("Manual Landmark Review")
    print("======================")
    print(f"Image: {image_path}")
    print(f"Overlay: {overlay_path}")
    print()
    print("Automated Summary")
    print(f"- measurement_status: {quality.get('measurement_status')}")
    print(f"- trust_score_raw: {quality.get('trust_score_raw')}")
    print(f"- trust_score_after_penalties: {quality.get('trust_score_after_penalties')}")
    print(f"- recommendation: {quality.get('recommendation')}")
    print(f"- recommendation_reason: {quality.get('recommendation_reason')}")
    print(f"- risk_scores: {quality.get('risk_scores') or {}}")
    print(f"- penalties: {quality.get('penalties') or {}}")
    print(f"- hard_gates_triggered: {quality.get('hard_gates_triggered') or []}")
    print(f"- issues: {quality.get('issues') or []}")
    print(f"- heel_boundary_type: {refinement.get('heel_boundary_type')}")
    print(f"- heel_boundary_confidence: {refinement.get('heel_boundary_confidence')}")
    print(f"- heel_center: {refinement.get('heel_center')}")
    print(f"- toe_point: {measurement.get('toe_point')}")
    print(f"- width_points: {measurement.get('width_points')}")
    print()
    print("Human Checklist")
    print("1. Is lower leg still included? Accept / Reject / Needs Review")
    print("2. Is the heel boundary truly anatomical? Accept / Reject / Needs Review")
    print("3. Is the toe point constrained by crop? Accept / Reject / Needs Review")
    print("4. Is the mask too rectangular? Accept / Reject / Needs Review")
    print("5. Should this result be trusted or needs review? Accept / Reject / Needs Review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
