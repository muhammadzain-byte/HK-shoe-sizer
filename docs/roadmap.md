# Development Roadmap

## Phase 1: Foundation

- Architecture documentation.
- FastAPI app and service boundaries.
- Next.js page hierarchy.
- PostgreSQL schema and Alembic migration.
- JWT authentication.
- S3 upload abstraction.
- Placeholder AI contracts.

## Phase 2: Workflow Completion

- Persist login token.
- Wire frontend forms to backend APIs.
- Implement browser camera capture with file upload.
- Add scan creation and upload completion flows.
- Add paginated scan history.
- Add scan detail status views.

Status: implemented.

## Phase 3: AI Integration

- Add image validation layer before AI processing.
- Add SAM adapter.
- Add YOLOv8 segmentation adapter.
- Add Depth Anything V2 adapter.
- Define calibration method.
- Implement rule-based women's size recommendation.

Phase 3A status: image validation layer implemented. Measurement and recommendation remain unimplemented.

Phase 3B status: SAM 2 segmentation service implemented for validation. Measurement and recommendation remain unimplemented.

Phase 3C status: pixel-only measurement engine implemented. Calibration, Depth Anything V2, and recommendations remain unimplemented.

## Phase 4: Production Hardening

- Add guided capture quality gates. Status: implemented in Phase 4A.
- Store capture-session device/camera telemetry. Status: implemented in Phase 4B.
- Add safe scale estimation architecture without faking millimeters. Status: implemented in Phase 4C.
- Add AR/depth adapter readiness without native runtime claims. Status: implemented in Phase 4D.
- Add women-only generic size engine blocked by measurement and scale gates. Status: implemented in Phase 4E.
- Add end-to-end safe flow orchestration. Status: implemented in Phase 4F.
- Add async processing worker.
- Add rate limiting.
- Add observability.
- Add CI/CD.
- Add privacy retention jobs.

Phase 4B note: capture telemetry is stored for authenticated users and linked to scans/uploads when available. It is not calibration, depth, centimeter conversion, or shoe sizing.

Phase 4C note: reference-object scale can be estimated when explicitly provided and validated. Device metadata, uncalibrated depth, and monocular depth do not produce millimeters. Shoe sizing remains blocked.

Phase 4D-4F note: depth metadata is adapter-ready, generic women-only size mapping exists, and the full pipeline is connected. Native AR runtime, brand sizing, production accuracy claims, and model training remain out of scope.

## Phase 5: Real-Device Proof

- Add database readiness verification. Status: implemented in Phase 5A.
- Add reference-object capture UX and safe reference validation. Status: implemented in Phase 5A.
- Add measurement accuracy validation harness. Status: implemented in Phase 5A.
- Add real-device testing checklist. Status: implemented in Phase 5A.
- Collect real device benchmark cases.
- Compare AI length/width against manual ground truth.
- Tune capture and reference-object gates from benchmark evidence.

Phase 5A note: the system is ready to be tested with reference objects and real devices. It still does not claim production accuracy, does not fake no-reference scale, and does not recommend shoe size without trusted measurement and scale.

- Add external foot dataset registry and research-only manifests. Status: implemented in Phase 5C.

Phase 5C note: external datasets live under `datasets/external/` and are for AI research only. They do not replace the real accuracy dataset at `datasets/validation/validation_cases.csv`.

- Add end-to-end external dataset population, conversion, split, and research training pipeline. Status: implemented in Phase 5D.

Phase 5D note: the pipeline can prepare folders, inspect datasets, create manifests, convert metadata, build research splits, and train a lightweight mask-quality research model on available masks. It does not download by accident, does not train production models, and does not prove measurement accuracy.
## Phase 6A: Real-Device Validation

- Added validation case storage and benchmark result storage.
- Added frontend validation cockpit for manual ground truth and reference-object annotation.
- Added benchmark/report scripts.
- Production accuracy claims remain blocked until enough real-device evidence passes strict thresholds.
