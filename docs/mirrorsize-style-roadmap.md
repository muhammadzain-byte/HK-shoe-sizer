# MirrorSize-Style Roadmap

This project is building its own guided foot-measurement flow. It does not copy proprietary MirrorSize code or claim production sizing accuracy without scale validation.

## Built Now

Phase 4A adds guided capture and a backend capture-quality gate. The camera UI asks for a rear, high-resolution stream, shows toe/heel/side guide zones, captures device metadata, and checks a captured frame before upload.

Phase 4B adds persistent capture-session telemetry. Capture sessions store device metadata, camera/video dimensions, capture-quality scores, issues, instructions, and optional links to scans and uploaded images.

Phase 4C adds safe scale estimation architecture. It can calculate scale from a valid explicit reference object, but defaults to unavailable when no trusted scale source exists.

Phase 4D adds AR/depth adapter readiness. The backend can validate future depth metadata and estimate scale from strong synthetic depth evidence, but no native AR runtime is implemented.

Phase 4E adds a women-only generic shoe size engine that stays blocked unless trusted millimeter length and width exist.

Phase 4F connects the safe end-to-end flow with explicit stage statuses and next actions.

Phase 5A adds real-device validation readiness. It adds reference-object UX, conservative reference validation, database readiness checks, and a manual accuracy benchmark harness.

Phase 5C adds external foot dataset integration for AI research. These datasets live under `datasets/external/` and remain separate from the real-device accuracy dataset.

Phase 5D adds a safe external dataset population, conversion, split, and research training pipeline. Trained research models are disabled in production by default.

## Intended Flow

1. Guided camera capture.
2. Capture-quality validation.
3. SAM 2 foot segmentation.
4. Foot candidate selection and refinement.
5. Heel boundary refinement.
6. Landmark validation.
7. Scale estimation.
8. Real-world measurement only when scale is trusted.
9. Women-only shoe sizing only when measurement and scale are trusted.
10. Manual validation against ground truth before any accuracy claim.

## Safe Behavior

Bad capture returns instructions and should not proceed as trusted. Risky measurement returns review or failure states. Missing scale blocks millimeter conversion and shoe-size recommendations.

## Unsafe Behavior

It is unsafe to infer centimeters or millimeters from pixels alone. It is unsafe to recommend shoe size when capture quality, measurement quality, or scale confidence fails.

Telemetry is not scale. Device metadata can support future calibration analysis, but it does not make pixel measurements real-world measurements by itself.

External synthetic or 3D research datasets are not production accuracy proof. Real proof remains real phone captures plus manual millimeter ground truth in `datasets/validation/validation_cases.csv`.

## Privacy

Foot images and related telemetry are sensitive biometric-like data. Capture sessions are authenticated user data, not public analytics. Future dataset collection or model training should require explicit product and privacy decisions.

## Requires Real Device Testing

Rear-camera selection, high-resolution stream support, orientation events, browser permissions, capture-quality behavior, and telemetry completeness must be verified on real Android and iOS devices.

## Future Work

Next work should focus on collecting real-device validation cases, comparing against manual ground truth, and tuning thresholds before any accuracy claims.
## Phase 6A: Real-Device Validation Cockpit

The project now has a validation cockpit for real phone-capture evidence. This phase does not claim production accuracy. It creates the operational path to prove or disprove accuracy using real images, manual millimeter ground truth, reference-object evidence, and benchmark reports.

The cockpit is intentionally separate from synthetic and external research datasets.
