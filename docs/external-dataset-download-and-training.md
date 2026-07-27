# External Dataset Download And Research Training

Phase 5D adds an end-to-end research pipeline for external foot datasets. Phase 5E adds actual acquisition preflight, official link discovery, explicit download attempts, extraction reports, and a smoke-only training fallback. Phase 5F adds full-auto tool setup and safe automatic download attempts across discovered official links. This does not prove production measurement accuracy.

Real accuracy proof still comes from `datasets/validation/validation_cases.csv` with real phone images, manual millimeter measurements, reference-object evidence, and benchmark reports.

## Safe Dataset Commands

```powershell
python backend\scripts\dataset_acquisition_preflight.py
python backend\scripts\setup_dataset_tools.py --install
python backend\scripts\external_dataset_manager.py prepare-all
python backend\scripts\external_dataset_manager.py list
python backend\scripts\external_dataset_manager.py inspect-all
python backend\scripts\external_dataset_manager.py manifest-all
python backend\scripts\external_dataset_manager.py discover-links --dataset found_synfoot --deep
python backend\scripts\external_dataset_manager.py discover-links --dataset focus_synfoot2_foot3d --deep
python backend\scripts\external_dataset_manager.py print-download-instructions --dataset focus_synfoot2_foot3d
```

Download commands refuse unless both flags are present:

```powershell
python backend\scripts\external_dataset_manager.py download --dataset found_synfoot --accept-license --explicit --try-all --limit-files 1000
python backend\scripts\external_dataset_manager.py download --dataset focus_synfoot2_foot3d --accept-license --explicit --try-all --limit-files 1000
python backend\scripts\external_dataset_manager.py download --dataset footgait3d --accept-license --explicit --try-all --dry-run
```

FOCUS, FOUND, and FIND/Foot3D require official repo/project instructions. FootGait3D can use Hugging Face only if `huggingface_hub` is installed, license terms are accepted, and the command is explicit.

If an official dataset resolves to Google Drive or another manual access path, the manager writes `manual_download_required.json` and does not invent samples. Install optional Google Drive tooling only after license review:

```powershell
pip install gdown
```

Extraction is explicit and only supports known archive types:

```powershell
python backend\scripts\external_dataset_manager.py extract --dataset found_synfoot --explicit
```

## Population Check

```powershell
python backend\scripts\check_dataset_population.py
```

Statuses:

- `empty`
- `downloaded`
- `manifest_ready`
- `converted`
- `training_ready`

## Convert To Common Format

```powershell
python backend\scripts\external_dataset_manager.py convert --dataset found_synfoot --limit 1000
python backend\scripts\external_dataset_manager.py convert-all --limit 1000
```

Converted metadata is written to:

`datasets/external/common/processed/{dataset_id}/{sample_id}.json`

Manifests are written to:

`datasets/external/common/manifests/{dataset_id}_manifest.json`

## Build Splits

```powershell
python backend\scripts\build_research_splits.py --dataset found_synfoot --task segmentation_baseline --train 0.8 --val 0.1 --test 0.1
```

Splits are deterministic and refuse missing labels or tiny datasets.

## Train Research Models

Mask quality is the first lightweight trainable task:

```powershell
python backend\scripts\train_research_models.py --task mask_quality --dataset found_synfoot --limit 500
```

Outputs:

- `models/research/mask_quality/mask_quality_model.joblib`
- `models/research/mask_quality/feature_schema.json`
- `artifacts/training/mask_quality/training_report.json`
- `artifacts/training/mask_quality/confusion_matrix.json`

If sklearn is unavailable, the script writes a rule-baseline report instead of pretending ML training succeeded.

On Python versions where the optional sklearn stack is unstable, the trainer also falls back to the rule baseline and records the reason in the report.

If no real external files are available, a smoke-only code path can verify the trainer without claiming research value:

```powershell
python backend\scripts\train_research_models.py --task mask_quality --dataset smoke_test --allow-smoke-data
```

Smoke data is synthetic code-path test data only. It is not a research dataset, not production evidence, and should not be used for accuracy claims.

## Full Research Pipeline

```powershell
python backend\scripts\run_external_dataset_pipeline.py --dataset found_synfoot --safe-auto --limit 1000
python backend\scripts\run_external_dataset_pipeline.py --dataset found_synfoot --full-auto --accept-license --explicit --try-all --install-missing-tools --limit 1000
python backend\scripts\run_external_dataset_pipeline.py --dataset found_synfoot --accept-license --explicit --discover --download --extract --manifest --convert --split --train --limit 1000 --task mask_quality
```

If files are missing, the pipeline exits gracefully with `waiting_for_dataset_files`.

The full pipeline report is written to:

`artifacts/external_dataset_pipeline/{dataset_id}_full_pipeline_report.json`

## Phase 5F Acquisition Result

The Phase 5F automated run reached the official FOUND and FOCUS links, downloaded files through safe public methods, extracted supported archives, generated non-zero manifests, and converted common metadata samples.

Observed result from the Phase 5F run:

- FOUND downloaded 5 official files from the discovered Google Drive folder. The manifest contains metadata/checkpoint/keypoint-related files, but no RGB images or mask labels.
- FOCUS downloaded 925 files across the discovered Google Drive files and extracted 927 archive members. The manifest contains meshes, metadata, and dense-correspondence-style artifacts, but no RGB images or mask labels.
- Mask-quality and segmentation splits were skipped because no mask samples were detected.
- Mesh reconstruction research splits can be built from the downloaded FOCUS mesh samples. Training is still placeholder/readiness-only until a reviewed mesh reconstruction training objective is implemented.
- Real external mask-quality ML training did not run.
- Smoke training can still verify the code path, but it is not research training and not accuracy evidence.

Do not treat downloaded meshes/checkpoints/metadata as phone-measurement validation. Real measurement accuracy still requires `datasets/validation/validation_cases.csv` with real phone captures, reference scale, and manual millimeter ground truth.

Useful follow-up command for the acquired FOCUS payload:

```powershell
python backend\scripts\build_research_splits.py --dataset focus_synfoot2_foot3d --task mesh_reconstruction_research --limit 1000
python backend\scripts\train_research_models.py --task mesh_reconstruction_research --dataset focus_synfoot2_foot3d --limit 1000
```

The training command currently writes a readiness report only; it does not train or enable a production model.

## Production Safety

Research models are disabled by default with `ENABLE_RESEARCH_MODELS=false`.

Even when enabled for debugging, they cannot override capture, measurement, scale, or size gates. They can only add debug evidence.

Do not commit dataset payloads or large model binaries.
