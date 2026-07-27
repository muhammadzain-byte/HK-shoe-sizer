# External Foot Datasets

External datasets are useful for AI research, but they do not prove this product's phone measurement accuracy. Real accuracy still requires `datasets/validation/validation_cases.csv` with real phone images, manual millimeter ground truth, reference-object evidence, and device metadata.

## Supported Research Datasets

### FOCUS / SynFoot2 / Foot3D

- Repo: https://github.com/OllieBoyne/FOCUS
- Project: https://www.ollieboyne.com/FOCUS/
- Paper: https://arxiv.org/abs/2502.06367
- Best for: dense correspondences, synthetic foot images, multi-view reconstruction, foot-part reasoning.

### FOUND / SynFoot

- Repo: https://github.com/OllieBoyne/FOUND
- Project: https://www.ollieboyne.com/FOUND/
- Paper: https://arxiv.org/abs/2310.18279
- Best for: synthetic images, masks, keypoints, surface normals, 3D fitting research.

### FIND / Foot3D

- Paper: https://arxiv.org/abs/2210.12241
- Best for: 3D foot scans, shape priors, future geometry validation.

### FootGait3D

- Paper: https://arxiv.org/abs/2507.11037
- Dataset: https://huggingface.co/datasets/ljw285/FootGait3D
- Best for: point clouds, gait/depth research, future AR/depth validation.
- Not a top-down phone measurement benchmark.

## Local Layout

- `datasets/external/focus/`
- `datasets/external/found/`
- `datasets/external/find_foot3d/`
- `datasets/external/footgait3d/`
- `datasets/external/common/manifests/`

Raw and processed payloads are ignored by `datasets/external/.gitignore`.

## Commands

```powershell
python backend\scripts\external_dataset_manager.py list
python backend\scripts\external_dataset_manager.py prepare-all
python backend\scripts\external_dataset_manager.py print-download-instructions --dataset focus_synfoot2_foot3d
python backend\scripts\external_dataset_manager.py inspect --dataset focus_synfoot2_foot3d
python backend\scripts\external_dataset_manager.py manifest --dataset focus_synfoot2_foot3d
python backend\scripts\external_dataset_manager.py convert --dataset found_synfoot --limit 1000
```

## Download Safety

The manager does not download large datasets by default. The `download` command refuses unless both `--accept-license` and `--explicit` are provided, and even then it prints safe manual instructions unless a future dataset-specific safe downloader is implemented.

Review licenses before downloading or using any external dataset.

Phase 5D adds population checks, manifest conversion, deterministic research splits, and lightweight mask-quality research training. Research models remain disabled in production by default.

## Safety Rule

Do not use external synthetic or research datasets for production accuracy claims. They are research inputs only.
