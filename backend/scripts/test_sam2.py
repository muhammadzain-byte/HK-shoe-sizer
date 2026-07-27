from __future__ import annotations

import argparse
import json
import os
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.ai.foot_candidate_selection_service import FootCandidateSelectionService  # noqa: E402
from app.services.ai.foot_region_refinement_service import FootRegionRefinementService  # noqa: E402


DEFAULT_MODEL_ID = "facebook/sam2.1-hiera-large"
DEFAULT_DEVICE = "cpu"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify SAM 2 mask generation on a real image.")
    parser.add_argument("--image", required=True, help="Path to a JPG, PNG, or WebP image.")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for output_mask.png, output_overlay.png, and output_metadata.json.",
    )
    return parser.parse_args()


def resolve_device(device_name: str) -> tuple[int, str]:
    import torch

    requested = device_name.lower()
    if requested == "cpu":
        return -1, "cpu"
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("SAM2_DEVICE=cuda was requested, but CUDA is not available.")
        return 0, "cuda"
    raise RuntimeError("SAM2_DEVICE must be either 'cpu' or 'cuda'.")


def bytes_to_mb(value: int | float) -> float:
    return round(float(value) / (1024 * 1024), 2)


def current_peak_memory(device_label: str) -> dict[str, float | None]:
    current, peak = tracemalloc.get_traced_memory()
    result: dict[str, float | None] = {
        "python_current_mb": bytes_to_mb(current),
        "python_peak_mb": bytes_to_mb(peak),
        "gpu_peak_mb": None,
    }

    if device_label == "cuda":
        try:
            import torch

            result["gpu_peak_mb"] = bytes_to_mb(torch.cuda.max_memory_allocated())
        except Exception:
            result["gpu_peak_mb"] = None
    return result


def first_present(mapping: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def describe_mask(mask: Any, index: int) -> None:
    shape = getattr(mask, "shape", None)
    dtype = getattr(mask, "dtype", None)
    print(f"Mask {index} Type: {type(mask).__name__}")
    print(f"Mask {index} Shape: {shape}")
    print(f"Mask {index} DType: {dtype}")


def score_to_float(score: Any) -> float | None:
    if score is None:
        return None
    if hasattr(score, "detach"):
        score = score.detach().cpu()
        if hasattr(score, "numel") and score.numel() == 1:
            return float(score.item())
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def normalize_mask(mask: Any):
    import numpy as np

    if mask is None:
        raise ValueError("Mask is None")
    if hasattr(mask, "detach"):
        mask = mask.detach().cpu().numpy()
    elif isinstance(mask, Image.Image):
        mask = np.asarray(mask)
    array = np.asarray(mask)
    if array.ndim == 3:
        array = array.squeeze()
    if array.ndim != 2:
        raise ValueError(f"Expected a 2D mask after normalization, got shape {array.shape}")
    return array.astype(bool)


def extract_masks(raw_result: Any) -> list[dict[str, Any]]:
    if isinstance(raw_result, dict):
        masks = first_present(raw_result, ("masks", "mask", "segmentation"), [])
        scores = first_present(raw_result, ("scores", "iou_scores", "stability_score"), [])
        if hasattr(masks, "detach"):
            masks = list(masks)
        elif not isinstance(masks, list | tuple):
            masks = [masks]
        if hasattr(scores, "detach"):
            scores = list(scores)
        elif scores is None or isinstance(scores, int | float):
            scores = [scores] if scores is not None else []
        return [{"mask": mask, "score": scores[index] if index < len(scores) else None} for index, mask in enumerate(masks)]

    if isinstance(raw_result, list):
        extracted = []
        for item in raw_result:
            if isinstance(item, dict):
                mask = first_present(item, ("mask", "segmentation"))
                score = first_present(item, ("score", "stability_score", "iou_score"))
                extracted.append(
                    {
                        "mask": mask,
                        "score": score,
                    }
                )
        return extracted

    return []


def mask_bbox(mask: Any) -> tuple[dict[str, int] | None, int]:
    import numpy as np

    boolean_mask = normalize_mask(mask)
    ys, xs = np.where(boolean_mask)
    if len(xs) == 0 or len(ys) == 0:
        return None, 0

    min_x = int(xs.min())
    max_x = int(xs.max())
    min_y = int(ys.min())
    max_y = int(ys.max())
    return (
        {
            "x": min_x,
            "y": min_y,
            "width": max_x - min_x + 1,
            "height": max_y - min_y + 1,
        },
        int(boolean_mask.sum()),
    )


def combined_mask_image(masks: list[dict[str, Any]], image_size: tuple[int, int]) -> Image.Image:
    import numpy as np

    width, height = image_size
    combined = np.zeros((height, width), dtype=bool)
    for item in masks:
        mask = item.get("mask")
        if mask is None:
            continue
        boolean_mask = normalize_mask(mask)
        if boolean_mask.shape != combined.shape:
            boolean_mask = np.asarray(Image.fromarray(boolean_mask.astype("uint8") * 255).resize((width, height))) > 0
        combined |= boolean_mask
    return Image.fromarray((combined.astype("uint8") * 255), mode="L")


def save_overlay(image: Image.Image, mask_image: Image.Image, boxes: list[dict[str, int]], path: Path) -> None:
    overlay = Image.new("RGBA", image.size, (255, 0, 0, 0))
    red_layer = Image.new("RGBA", image.size, (255, 48, 48, 110))
    overlay.paste(red_layer, mask=mask_image)
    composed = Image.alpha_composite(image.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(composed)
    for box in boxes:
        x0 = box["x"]
        y0 = box["y"]
        x1 = box["x"] + box["width"]
        y1 = box["y"] + box["height"]
        draw.rectangle((x0, y0, x1, y1), outline=(0, 255, 120, 255), width=4)
    composed.convert("RGB").save(path)


def bbox_to_dict(bbox: Any) -> dict[str, int]:
    return {
        "x": int(bbox.x),
        "y": int(bbox.y),
        "width": int(bbox.width),
        "height": int(bbox.height),
    }


def diagnostic_to_dict(diagnostic: Any) -> dict[str, Any]:
    payload = dict(diagnostic.__dict__)
    payload["bbox"] = bbox_to_dict(diagnostic.bbox)
    return payload


def save_selected_foot(image: Image.Image, selected_mask: Any, selected_box: dict[str, int], path: Path) -> None:
    mask_image = Image.fromarray((selected_mask.astype("uint8") * 255), mode="L")
    save_overlay(image, mask_image, [selected_box], path)


def save_candidate_masks(
    image_size: tuple[int, int],
    masks: list[dict[str, Any]],
    diagnostics: list[Any],
    path: Path,
) -> None:
    import numpy as np

    width, height = image_size
    canvas = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(canvas)
    colors = [
        (255, 80, 80),
        (80, 255, 120),
        (80, 160, 255),
        (255, 220, 80),
        (210, 120, 255),
        (255, 150, 80),
    ]
    selector = FootCandidateSelectionService()

    for index, item in enumerate(masks):
        mask = selector.normalize_mask(item.get("mask"))
        if mask is None:
            continue
        if mask.shape != (height, width):
            mask = np.asarray(Image.fromarray(mask.astype("uint8") * 255).resize((width, height))) > 0
        color = colors[index % len(colors)]
        layer = Image.new("RGB", (width, height), color)
        canvas.paste(layer, mask=Image.fromarray((mask.astype("uint8") * 120), mode="L"))

    for diagnostic in diagnostics:
        box = diagnostic.bbox
        color = (0, 255, 120) if not diagnostic.rejected else (255, 255, 255)
        draw.rectangle(
            (box.x, box.y, box.x + box.width, box.y + box.height),
            outline=color,
            width=2,
        )
        draw.text((box.x + 2, box.y + 2), str(diagnostic.index), fill=color)

    canvas.save(path)


def save_candidate_debug_overlay(
    image: Image.Image,
    diagnostics: list[Any],
    candidate_masks: list[Any],
    selected_index: int | None,
    path: Path,
) -> None:
    import numpy as np

    composed = image.convert("RGBA")
    colors = [
        (255, 80, 80, 65),
        (80, 180, 255, 65),
        (255, 220, 80, 65),
        (210, 120, 255, 65),
        (80, 255, 150, 65),
        (255, 150, 80, 65),
    ]
    for diagnostic, mask in zip(diagnostics, candidate_masks, strict=False):
        boolean_mask = np.asarray(mask).astype(bool)
        if boolean_mask.shape != (image.height, image.width):
            boolean_mask = np.asarray(
                Image.fromarray(boolean_mask.astype("uint8") * 255).resize(image.size)
            ) > 0
        color = (0, 255, 120, 105) if diagnostic.index == selected_index else colors[diagnostic.index % len(colors)]
        layer = Image.new("RGBA", image.size, color)
        composed.alpha_composite(
            Image.composite(layer, Image.new("RGBA", image.size, (0, 0, 0, 0)), Image.fromarray(boolean_mask.astype("uint8") * 255))
        )

    draw = ImageDraw.Draw(composed)
    for diagnostic in diagnostics:
        box = diagnostic.bbox
        color = (0, 255, 120, 255) if diagnostic.index == selected_index else (255, 210, 60, 255)
        draw.rectangle(
            (box.x, box.y, box.x + box.width, box.y + box.height),
            outline=color,
            width=5 if diagnostic.index == selected_index else 3,
        )
        reason = diagnostic.rejection_reason or "accepted"
        label = f"#{diagnostic.index} {diagnostic.candidate_score:.2f} {reason}"
        text_y = max(0, box.y - 16)
        draw.rectangle((box.x, text_y, min(image.width, box.x + 360), text_y + 16), fill=(0, 0, 0, 150))
        draw.text((box.x + 3, text_y + 2), label[:64], fill=color)
    composed.convert("RGB").save(path)


def candidate_score_summary(candidate: dict[str, Any], selected_index: int | None) -> dict[str, Any]:
    return {
        "candidate_id": candidate["index"],
        "source": candidate["source"],
        "bbox": candidate["bbox"],
        "area_ratio": candidate["area_ratio"],
        "toe_score": candidate["toe_score"],
        "forefoot_score": candidate["forefoot_score"],
        "heel_score": candidate["heel_score"],
        "ankle_rejection_score": candidate["ankle_rejection_score"],
        "leg_rejection_score": candidate["leg_rejection_score"],
        "shape_score": candidate["shape_score"],
        "final_score": candidate["candidate_score"],
        "accepted": candidate["index"] == selected_index,
        "rejected": candidate["rejected"],
        "rejection_reason": candidate["rejection_reason"],
        "visible_toe_count": candidate["visible_toe_count"],
        "orientation": candidate["orientation"],
        "profile": candidate["profile"],
    }


def main() -> int:
    args = parse_args()
    image_path = Path(args.image).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not image_path.exists():
        print(f"FAIL: image not found: {image_path}", file=sys.stderr)
        return 1

    model_id = os.getenv("SAM2_MODEL_ID", DEFAULT_MODEL_ID)
    device_name = os.getenv("SAM2_DEVICE", DEFAULT_DEVICE)

    tracemalloc.start()
    try:
        import torch
        from huggingface_hub import snapshot_download
        from transformers import pipeline
    except Exception as exc:
        print(f"FAIL: could not import SAM 2 dependencies: {exc}", file=sys.stderr)
        return 1

    try:
        device, device_label = resolve_device(device_name)
        if device_label == "cuda":
            torch.cuda.reset_peak_memory_stats()

        print(f"Model ID: {model_id}")
        print(f"Device: {device_label}")

        image = Image.open(image_path).convert("RGB")

        download_start = time.perf_counter()
        snapshot_download(repo_id=model_id)
        download_time = time.perf_counter() - download_start

        load_start = time.perf_counter()
        mask_pipeline = pipeline("mask-generation", model=model_id, device=device)
        load_time = time.perf_counter() - load_start

        inference_start = time.perf_counter()
        raw_result = mask_pipeline(image)
        inference_time = time.perf_counter() - inference_start

        masks = extract_masks(raw_result)
        if not masks:
            print("FAIL: no masks generated", file=sys.stderr)
            return 1

        selector = FootCandidateSelectionService()
        refinement_service = FootRegionRefinementService()
        selection = selector.select(masks, image.size)

        boxes: list[dict[str, int]] = []
        areas: list[int] = []
        scores: list[float | None] = []
        for index, item in enumerate(masks):
            describe_mask(item.get("mask"), index)
            box, area = mask_bbox(item.get("mask"))
            if box is not None:
                boxes.append(box)
            areas.append(area)
            score = item.get("score")
            scores.append(score_to_float(score))

        mask_image = combined_mask_image(masks, image.size)
        mask_path = output_dir / "output_mask.png"
        overlay_path = output_dir / "output_overlay.png"
        segmentation_overlay_path = output_dir / "segmentation_overlay.png"
        metadata_path = output_dir / "output_metadata.json"
        selected_foot_path = output_dir / "selected_foot.png"
        candidate_masks_path = output_dir / "candidate_masks.png"
        candidate_debug_path = output_dir / "candidate_debug_overlay.png"
        candidate_score_breakdown_path = output_dir / "candidate_score_breakdown.json"
        refined_mask_path = output_dir / "refined_foot_mask.png"
        refined_overlay_path = output_dir / "refined_foot_overlay.png"
        refinement_debug_path = output_dir / "foot_region_refinement_debug.png"
        heel_boundary_debug_path = output_dir / "heel_boundary_debug.png"
        refinement_metadata_path = output_dir / "refinement_metadata.json"
        mask_image.save(mask_path)
        save_overlay(image, mask_image, boxes, overlay_path)
        save_overlay(image, mask_image, boxes, segmentation_overlay_path)

        selected_box = bbox_to_dict(selection.selected.bbox) if selection.selected else None
        refinement_metadata = None
        refined_box = None
        if selection.selected and selection.selected.mask is not None and selected_box is not None:
            selected_mask = selector.normalize_mask(selection.selected.mask)
            save_selected_foot(image, selected_mask, selected_box, selected_foot_path)
            refinement = refinement_service.refine(selected_mask, selection.selected.bbox)
            refinement_service.save_refined_mask(refinement, refined_mask_path)
            refinement_service.save_refined_overlay(image, refinement, refined_overlay_path)
            refinement_service.save_debug_overlay(image, selected_mask, refinement, refinement_debug_path)
            refinement_service.save_heel_boundary_debug(image, selected_mask, refinement, heel_boundary_debug_path)
            refinement_metadata = refinement.to_metadata()
            refined_box = refinement_metadata["refined_bbox"]
            refinement_metadata_path.write_text(json.dumps(refinement_metadata, indent=2), encoding="utf-8")
        save_candidate_masks(image.size, masks, selection.candidates, candidate_masks_path)
        selected_index = selection.selected.diagnostics["index"] if selection.selected and selection.selected.diagnostics else None
        save_candidate_debug_overlay(
            image,
            selection.candidates,
            selection.candidate_masks,
            selected_index,
            candidate_debug_path,
        )

        candidate_diagnostics = [diagnostic_to_dict(candidate) for candidate in selection.candidates]
        candidate_score_breakdown_path.write_text(
            json.dumps(
                [candidate_score_summary(candidate, selected_index) for candidate in candidate_diagnostics],
                indent=2,
            ),
            encoding="utf-8",
        )

        memory = current_peak_memory(device_label)
        metadata = {
            "model_id": model_id,
            "device": device_label,
            "download_time": round(download_time, 4),
            "model_load_time": round(load_time, 4),
            "inference_time": round(inference_time, 4),
            "mask_count": len(masks),
            "mask_areas": areas,
            "scores": scores,
            "bounding_boxes": boxes,
            "selected_foot": {
                "foot_count": 1 if selection.selected else 0,
                "foot_bbox": selected_box,
                "confidence": float(selection.selected.confidence_score) if selection.selected else None,
                "refined_bbox": refined_box,
                "refinement": refinement_metadata,
            },
            "candidate_diagnostics": candidate_diagnostics,
            "peak_memory_usage": memory,
            "outputs": {
                "mask": str(mask_path),
                "overlay": str(overlay_path),
                "segmentation_overlay": str(segmentation_overlay_path),
                "selected_foot": str(selected_foot_path),
                "candidate_masks": str(candidate_masks_path),
                "candidate_debug_overlay": str(candidate_debug_path),
                "candidate_score_breakdown": str(candidate_score_breakdown_path),
                "refined_foot_mask": str(refined_mask_path),
                "refined_foot_overlay": str(refined_overlay_path),
                "foot_region_refinement_debug": str(refinement_debug_path),
                "heel_boundary_debug": str(heel_boundary_debug_path),
                "refinement_metadata": str(refinement_metadata_path),
                "metadata": str(metadata_path),
            },
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        print(f"Download Time: {download_time:.4f}s")
        print(f"Model Load Time: {load_time:.4f}s")
        print(f"Inference Time: {inference_time:.4f}s")
        print(f"Mask Count: {len(masks)}")
        print(f"Mask Areas: {areas}")
        print(f"Bounding Boxes: {boxes}")
        print(f"Confidence Scores: {scores}")
        print("Candidate Diagnostics:")
        for diagnostic in candidate_diagnostics:
            print(
                "  "
                f"candidate={diagnostic['index']} source={diagnostic['source']} "
                f"area={diagnostic['area_pixels']} score={diagnostic['candidate_score']} "
                f"rejected={diagnostic['rejected']} reason={diagnostic['rejection_reason']}"
            )
        print(f"Selected Foot: {metadata['selected_foot']}")
        print(f"Peak Memory Usage: {memory}")
        print(f"Saved Mask: {mask_path}")
        print(f"Saved Overlay: {overlay_path}")
        print(f"Saved Segmentation Overlay: {segmentation_overlay_path}")
        print(f"Saved Selected Foot: {selected_foot_path}")
        print(f"Saved Candidate Masks: {candidate_masks_path}")
        print(f"Saved Candidate Debug Overlay: {candidate_debug_path}")
        print(f"Saved Candidate Score Breakdown: {candidate_score_breakdown_path}")
        print(f"Saved Refined Foot Mask: {refined_mask_path}")
        print(f"Saved Refined Foot Overlay: {refined_overlay_path}")
        print(f"Saved Foot Region Refinement Debug: {refinement_debug_path}")
        print(f"Saved Heel Boundary Debug: {heel_boundary_debug_path}")
        print(f"Saved Refinement Metadata: {refinement_metadata_path}")
        print(f"Saved Metadata: {metadata_path}")
        print("PASS: SAM 2 verification completed successfully")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        tracemalloc.stop()


if __name__ == "__main__":
    raise SystemExit(main())
