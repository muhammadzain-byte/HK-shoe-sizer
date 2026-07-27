# SAM 2 Production Verification

This runbook verifies that SAM 2 can download, load, run inference, generate masks, and write visual artifacts before measurement work begins.

The verification script does not modify production routes, production APIs, measurement logic, sizing logic, or calibration logic.

## Script

```text
backend/scripts/test_sam2.py
```

## How To Run

From the repository root:

```bash
python backend/scripts/test_sam2.py --image test_foot.jpg
```

Optional output directory:

```bash
python backend/scripts/test_sam2.py --image test_foot.jpg --output-dir backend/scripts/sam2_outputs
```

Model and device are read from environment variables:

```bash
SAM2_MODEL_ID=facebook/sam2.1-hiera-large
SAM2_DEVICE=cpu
```

Supported devices:

- `cpu`
- `cuda`

## Expected Console Output

The script prints:

- Model ID
- Device
- Download Time
- Model Load Time
- Inference Time
- Mask Count
- Mask Areas
- Bounding Boxes
- Confidence Scores
- Peak Memory Usage
- Generated file paths
- `PASS: SAM 2 verification completed successfully`

## Generated Files

The script writes:

- `output_mask.png`: binary segmentation mask.
- `output_overlay.png`: original image with red mask overlay and green bounding boxes.
- `output_metadata.json`: structured diagnostics.

Example metadata:

```json
{
  "model_id": "facebook/sam2.1-hiera-large",
  "device": "cpu",
  "download_time": 12.5,
  "model_load_time": 12.5,
  "inference_time": 4.2,
  "mask_count": 3,
  "scores": [0.96, 0.91, 0.78],
  "bounding_boxes": [
    {
      "x": 120,
      "y": 80,
      "width": 620,
      "height": 340
    }
  ]
}
```

## Pass Criteria

PASS means:

- Model downloads or resolves from local cache.
- Model loads successfully.
- Inference executes successfully.
- At least one mask is generated.
- `output_mask.png` is generated.
- `output_overlay.png` is generated.
- `output_metadata.json` is generated.

## Fail Criteria

FAIL means:

- Model download fails.
- Model load fails.
- Inference raises an exception.
- No masks are generated.
- Output files cannot be written.

## CPU Performance Expectations

CPU mode is useful for correctness verification and development.

Expect:

- Slow first run because model files may download.
- Slow inference, especially for large images.
- High RAM usage for larger SAM 2 variants.

Recommended CPU environment:

- 8+ CPU cores.
- 16 GB RAM minimum.
- Use a smaller model ID for smoke testing if needed.

Example:

```bash
SAM2_MODEL_ID=facebook/sam2.1-hiera-tiny SAM2_DEVICE=cpu python backend/scripts/test_sam2.py --image test_foot.jpg
```

## GPU Performance Expectations

GPU mode is recommended for production validation.

Expect:

- Faster inference after model load.
- Higher initial VRAM allocation during model load.
- Better throughput for repeated validations.

Recommended GPU environment:

- NVIDIA CUDA-capable GPU.
- 12 GB VRAM minimum for large variants.
- PyTorch build compatible with the installed CUDA runtime.

Run:

```bash
SAM2_DEVICE=cuda python backend/scripts/test_sam2.py --image test_foot.jpg
```

## Hugging Face Authentication

Public SAM 2 models may download without authentication depending on the model and local Hugging Face configuration.

If access fails:

1. Create or use a Hugging Face token.
2. Authenticate locally:

```bash
huggingface-cli login
```

Or set:

```bash
HF_TOKEN=your-token
```

Common authentication or download failures:

- Missing model access approval.
- Network proxy restrictions.
- Expired token.
- Hugging Face cache directory is not writable.

## Troubleshooting

### `SAM2_DEVICE=cuda was requested, but CUDA is not available`

Use CPU:

```bash
SAM2_DEVICE=cpu python backend/scripts/test_sam2.py --image test_foot.jpg
```

Or install a CUDA-compatible PyTorch build.

### Model Download Fails

Check:

- Internet connectivity.
- Hugging Face authentication.
- Model ID spelling.
- Disk space in the Hugging Face cache.

### No Masks Generated

Try:

- A clearer image.
- A higher-resolution image.
- A smaller crop around the foot.
- A different SAM 2 model variant.

### Out Of Memory

Try:

- CPU mode for correctness-only verification.
- A smaller SAM 2 model.
- A smaller input image.
- A GPU with more VRAM.

## Known Limitations

- SAM 2 is class-agnostic; generated masks are not inherently labeled as feet.
- The script verifies segmentation execution, not measurement quality.
- The script does not perform shoe sizing.
- First-run timing includes model resolution and potential downloads.
- `download_time` is measured with Hugging Face `snapshot_download`.
- `model_load_time` is measured during Transformers pipeline construction after the model snapshot has been resolved.
