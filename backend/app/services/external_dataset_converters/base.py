from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.schemas.external_dataset import (
    ExternalDatasetInspectionResult,
    ExternalDatasetManifest,
    ExternalDatasetRegistryEntry,
    ExternalDatasetSample,
)


class ExternalDatasetConverter:
    dataset_id = "base"
    label_extensions = {
        ".jpg": "image",
        ".jpeg": "image",
        ".png": "image_or_mask",
        ".exr": "normal_or_depth",
        ".json": "metadata",
        ".npy": "array",
        ".npz": "array",
        ".ply": "point_cloud_or_mesh",
        ".obj": "mesh",
        ".pkl": "metadata",
    }
    image_suffixes = {".jpg", ".jpeg", ".png", ".webp"}
    mask_tokens = ("_mask", "mask", "masks", "seg", "segmentation", "silhouette", "alpha")
    normal_tokens = ("normal", "_normals", "normals")
    keypoint_tokens = ("keypoint", "keypoints", "joint", "joints", "landmark", "landmarks")
    dense_tokens = ("correspondence", "dense", "uv")
    mesh_suffixes = {".obj", ".ply", ".glb"}
    point_cloud_suffixes = {".ply", ".pcd", ".npz", ".npy"}
    camera_tokens = ("camera", "intrinsics", "metadata", "calibration")

    def __init__(self, entry: ExternalDatasetRegistryEntry, project_root: Path) -> None:
        self.entry = entry
        self.project_root = project_root

    @property
    def raw_dir(self) -> Path:
        return self._resolve(self.entry.local_raw_dir)

    @property
    def processed_dir(self) -> Path:
        return self._resolve(self.entry.local_processed_dir)

    def inspect(self) -> ExternalDatasetInspectionResult:
        raw_files = self._files(self.raw_dir)
        processed_files = self._files(self.processed_dir)
        detected_file_types = sorted({path.suffix.lower() for path in [*raw_files, *processed_files] if path.suffix})
        label_types = sorted(
            {
                self.label_extensions.get(suffix, suffix.lstrip("."))
                for suffix in detected_file_types
            }
        )
        issues = []
        instructions = []
        if not raw_files and not processed_files:
            issues.append("Dataset not downloaded. Use print-download-instructions.")
            instructions.append("Download manually after license review, then run inspect again.")
        return ExternalDatasetInspectionResult(
            dataset_id=self.entry.id,
            local_raw_dir=str(self.raw_dir),
            local_processed_dir=str(self.processed_dir),
            raw_exists=self.raw_dir.exists(),
            processed_exists=self.processed_dir.exists(),
            raw_file_count=len(raw_files),
            processed_file_count=len(processed_files),
            detected_file_types=detected_file_types,
            label_types=label_types,
            issues=issues,
            instructions=instructions,
        )

    def generate_manifest(self) -> ExternalDatasetManifest:
        inspection = self.inspect()
        source_url = self.entry.repo_url or self.entry.project_url
        samples = self._detect_samples()
        return ExternalDatasetManifest(
            dataset_id=self.entry.id,
            source_url=source_url,
            paper_url=self.entry.paper_url,
            local_root=str(self.raw_dir.parent),
            license_status="unknown",
            sample_count=len(samples),
            file_inventory=self._file_inventory(),
            detected_file_types=inspection.detected_file_types,
            label_types=inspection.label_types,
            research_use_only=True,
            issues=[] if samples else inspection.issues,
            samples=samples,
        )

    def convert_sample(self, sample_path: str) -> ExternalDatasetSample:
        path = Path(sample_path)
        return ExternalDatasetSample(
            sample_id=path.stem or "unknown",
            dataset_id=self.entry.id,
            image_path=str(path) if path.suffix.lower() in {".jpg", ".jpeg", ".png"} else None,
            available_labels=[],
            research_use_only=True,
            notes="Conservative manifest-based conversion. Dataset layout must be reviewed before use.",
        )

    def validate_sample(self, sample: ExternalDatasetSample) -> list[str]:
        issues: list[str] = []
        if not sample.research_use_only:
            issues.append("External samples must be marked research_use_only.")
        if sample.dataset_id != self.entry.id:
            issues.append("Sample dataset_id does not match converter dataset.")
        return issues

    def write_processed_metadata(self, manifest: ExternalDatasetManifest) -> list[Path]:
        output_dir = self.project_root / "datasets/external/common/processed" / self.entry.id
        output_dir.mkdir(parents=True, exist_ok=True)
        for stale in output_dir.glob("*.json"):
            stale.unlink()
        written: list[Path] = []
        for sample in manifest.samples:
            payload = {
                "sample_id": sample.sample_id,
                "dataset_id": sample.dataset_id,
                "source_paths": {
                    "image": sample.image_path,
                    "mask": sample.mask_path,
                    "normal": sample.normal_path,
                    "keypoints": sample.keypoints_path,
                    "mesh": sample.mesh_path,
                    "point_cloud": sample.point_cloud_path,
                    "camera_metadata": sample.camera_metadata_path,
                    "dense_correspondence": sample.dense_correspondence_path,
                },
                "available_labels": sample.available_labels,
                "research_tasks": self._research_tasks(sample),
                "research_use_only": True,
                "license_status": "unknown",
                "notes": sample.notes,
            }
            path = output_dir / f"{sample.sample_id}.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            written.append(path)
        return written

    def _detect_samples(self) -> list[ExternalDatasetSample]:
        files = self._files(self.raw_dir)
        if not files:
            return []
        grouped: dict[str, dict[str, Path]] = defaultdict(dict)
        for path in files:
            sample_id = self._sample_id(path)
            label = self._label_for_path(path)
            current = grouped[sample_id].get(label)
            if current is None or len(str(path)) < len(str(current)):
                grouped[sample_id][label] = path

        samples: list[ExternalDatasetSample] = []
        for sample_id, labels in sorted(grouped.items()):
            available_labels = sorted(label for label, path in labels.items() if path is not None)
            samples.append(
                ExternalDatasetSample(
                    sample_id=sample_id,
                    dataset_id=self.entry.id,
                    image_path=self._relative_or_none(labels.get("image")),
                    mask_path=self._relative_or_none(labels.get("mask")),
                    normal_path=self._relative_or_none(labels.get("normal")),
                    keypoints_path=self._relative_or_none(labels.get("keypoints")),
                    dense_correspondence_path=self._relative_or_none(labels.get("dense_correspondence")),
                    mesh_path=self._relative_or_none(labels.get("mesh")),
                    point_cloud_path=self._relative_or_none(labels.get("point_cloud")),
                    camera_metadata_path=self._relative_or_none(labels.get("camera_metadata")),
                    available_labels=available_labels,
                    research_use_only=True,
                    notes="Detected by conservative file inventory. Review layout before research use.",
                )
            )
        return samples

    def _file_inventory(self) -> dict[str, int]:
        inventory = {
            "images": 0,
            "masks": 0,
            "normals": 0,
            "keypoints": 0,
            "dense_correspondences": 0,
            "meshes": 0,
            "point_clouds": 0,
            "camera_metadata": 0,
            "metadata_files": 0,
            "unknown": 0,
        }
        for path in self._files(self.raw_dir):
            label = self._label_for_path(path)
            if label == "image":
                inventory["images"] += 1
            elif label == "mask":
                inventory["masks"] += 1
            elif label == "normal":
                inventory["normals"] += 1
            elif label == "keypoints":
                inventory["keypoints"] += 1
            elif label == "dense_correspondence":
                inventory["dense_correspondences"] += 1
            elif label == "mesh":
                inventory["meshes"] += 1
            elif label == "point_cloud":
                inventory["point_clouds"] += 1
            elif label == "camera_metadata":
                inventory["camera_metadata"] += 1
            elif label == "json":
                inventory["metadata_files"] += 1
            else:
                inventory["unknown"] += 1
        return inventory

    def _label_for_path(self, path: Path) -> str:
        name = path.name.lower()
        suffix = path.suffix.lower()
        if any(token in name for token in self.mask_tokens) and suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            return "mask"
        if any(token in name for token in self.normal_tokens):
            return "normal"
        if any(token in name for token in self.keypoint_tokens):
            return "keypoints"
        if any(token in name for token in self.dense_tokens):
            return "dense_correspondence"
        if any(token in name for token in self.camera_tokens) and suffix == ".json":
            return "camera_metadata"
        if suffix == ".pcd":
            return "point_cloud"
        if suffix in {".npy", ".npz"} and ("point" in name or "cloud" in name):
            return "point_cloud"
        if suffix in self.mesh_suffixes:
            return "mesh" if suffix != ".ply" or "cloud" not in name else "point_cloud"
        if suffix in self.image_suffixes:
            return "image"
        return suffix.lstrip(".") or "unknown"

    def _sample_id(self, path: Path) -> str:
        stem = path.stem.lower()
        for token in [
            "_mask",
            "-mask",
            "_segmentation",
            "-segmentation",
            "_normal",
            "-normal",
            "_normals",
            "_keypoints",
            "-keypoints",
            "_joints",
            "_landmarks",
            "_camera",
            "_intrinsics",
            "_metadata",
            "_dense",
            "_correspondence",
            "_uv",
        ]:
            stem = stem.replace(token, "")
        stem = stem.strip("_-.") or path.stem.lower()
        if stem in {"mesh", "image", "img", "mask", "normal", "data", "version", "byteorder", "metadata", "camera", "intrinsics"}:
            try:
                relative = path.relative_to(self.raw_dir).with_suffix("")
                pieces = [self._safe_id_piece(piece) for piece in relative.parts[-5:]]
                sample_id = "_".join(piece for piece in pieces if piece)
                return sample_id or stem
            except ValueError:
                return self._safe_id_piece("_".join(path.with_suffix("").parts[-3:])) or stem
        return self._safe_id_piece(stem)

    def _safe_id_piece(self, value: str) -> str:
        cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value)
        while "__" in cleaned:
            cleaned = cleaned.replace("__", "_")
        return cleaned.strip("_")

    def _research_tasks(self, sample: ExternalDatasetSample) -> list[str]:
        tasks: list[str] = []
        if sample.image_path and sample.mask_path:
            tasks.extend(["segmentation_baseline", "mask_quality"])
        if sample.image_path and sample.keypoints_path:
            tasks.append("landmark_research")
        if sample.image_path and sample.normal_path:
            tasks.append("surface_normal_research")
        if sample.point_cloud_path:
            tasks.append("point_cloud_research")
        if sample.mesh_path:
            tasks.append("mesh_reconstruction_research")
        if sample.dense_correspondence_path:
            tasks.append("dense_correspondence_research")
        return tasks

    def _files(self, root: Path) -> list[Path]:
        if not root.exists():
            return []
        return [
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.name not in {".gitkeep", ".DS_Store"}
            and not path.name.startswith("._")
            and "__MACOSX" not in path.parts
        ]

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.project_root / path

    def _relative_or_none(self, path: Path | None) -> str | None:
        if path is None:
            return None
        try:
            return str(path.relative_to(self.project_root)).replace("\\", "/")
        except ValueError:
            return str(path)

    def _payload(self) -> dict[str, Any]:
        return self.entry.model_dump(mode="json")
