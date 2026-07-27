# AI Research Dataset Mapping

External foot datasets can improve research workflows without changing production safety gates.

## Useful Research Directions

1. SAM 2 mask validation: compare mask shapes, contour quality, and foot-part coverage against synthetic or annotated masks.
2. Toe and heel landmark detection: study dense correspondence, keypoints, and foot-part labels for landmark hardening.
3. Foot-part segmentation: improve reasoning about toes, forefoot, midfoot, heel, ankle, and lower-leg rejection.
4. Surface normal research: use FOUND/SynFoot normals for future pose and shape cues.
5. Future depth and 3D foot models: use Foot3D-style scans and FootGait3D point clouds for geometry research.
6. Mesh reconstruction research: use acquired FOCUS/Foot3D mesh files for split design and future mesh-quality evaluation.
7. Synthetic pretraining: explore synthetic data for future model research after license review.
8. Failure-case generation: create synthetic crop, tilt, mask, and landmark stress tests.

## What External Datasets Cannot Do

1. Cannot prove real-world phone measurement accuracy.
2. Cannot replace manual ground truth.
3. Cannot replace reference-object validation.
4. Cannot guarantee women's shoe size accuracy.
5. Cannot be used for production claims without proper license and validation.
6. Mesh files alone cannot train the current mask-quality model; mask/image payloads are still required for that task.

## Separation From Validation Dataset

Real measurement validation remains in `datasets/validation/validation_cases.csv`.

External research datasets live in `datasets/external/` and are marked research-only in manifests.

## Phase 5D Pipeline

The research pipeline can inspect local external files, create common manifests, convert sample metadata, build train/val/test splits, and train a lightweight mask-quality research model when valid masks exist. Mesh-only datasets can produce mesh reconstruction research splits and readiness reports, but no production model is trained from them.

Research models must stay disabled in production and may only add debug evidence.
