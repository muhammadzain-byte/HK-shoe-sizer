from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.schemas.external_dataset import (
    ExternalDatasetInspectionResult,
    ExternalDatasetManifest,
    ExternalDatasetRegistryEntry,
)
from app.services.external_dataset_converters import (
    ExternalDatasetConverter,
    FindFoot3DConverter,
    FocusDatasetConverter,
    FootGait3DConverter,
    FoundDatasetConverter,
)


class ExternalDatasetService:
    """Research-only external dataset registry and manifest service."""

    converter_classes = {
        "focus_synfoot2_foot3d": FocusDatasetConverter,
        "found_synfoot": FoundDatasetConverter,
        "find_foot3d": FindFoot3DConverter,
        "footgait3d": FootGait3DConverter,
    }

    def __init__(
        self,
        project_root: Path | None = None,
        registry_path: Path | None = None,
    ) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self.registry_path = registry_path or self.project_root / "datasets/external/registry.json"

    def load_registry(self, path: str | Path | None = None) -> list[ExternalDatasetRegistryEntry]:
        registry_path = Path(path) if path else self.registry_path
        if not registry_path.exists():
            entries = [self._generated_dataset_entry()]
            self._validate_unique_ids(entries)
            return entries
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        entries = [ExternalDatasetRegistryEntry.model_validate(item) for item in payload.get("datasets", [])]
        if not any(entry.id == "generated_foot_masks_from_focus" for entry in entries):
            entries.append(self._generated_dataset_entry())
        self._validate_unique_ids(entries)
        return entries

    def get_dataset_entry(self, dataset_id: str) -> ExternalDatasetRegistryEntry:
        for entry in self.load_registry():
            if entry.id == dataset_id:
                return entry
        raise ValueError(f"Unsupported external dataset: {dataset_id}")

    def list_supported_datasets(self) -> list[dict[str, Any]]:
        return [entry.model_dump(mode="json") for entry in self.load_registry()]

    def inspect_dataset(self, dataset_id: str) -> ExternalDatasetInspectionResult:
        return self._converter(dataset_id).inspect()

    def generate_manifest(self, dataset_id: str) -> ExternalDatasetManifest:
        return self._converter(dataset_id).generate_manifest()

    def validate_local_files(self, dataset_id: str) -> list[str]:
        entry = self.get_dataset_entry(dataset_id)
        issues: list[str] = []
        gitignore = self.project_root / "datasets/external/.gitignore"
        if not gitignore.exists():
            issues.append("datasets/external/.gitignore is missing.")
        for folder in [entry.local_raw_dir, entry.local_processed_dir]:
            path = self._resolve(folder)
            if not path.exists():
                issues.append(f"Expected dataset folder is missing: {folder}")
        return issues

    def validate_license_review(self, dataset_id: str) -> list[str]:
        entry = self.get_dataset_entry(dataset_id)
        if entry.license_review_required:
            return ["License review is required before downloading or using this dataset."]
        return []

    def create_common_manifest(self, dataset_id: str) -> Path:
        converter = self._converter(dataset_id)
        manifest = converter.generate_manifest()
        return self._write_manifest(manifest)

    def _write_manifest(self, manifest: ExternalDatasetManifest) -> Path:
        output_dir = self.project_root / "datasets/external/common/manifests"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{manifest.dataset_id}_manifest.json"
        output_path.write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return output_path

    def convert_dataset(self, dataset_id: str, limit: int | None = None) -> dict[str, Any]:
        converter = self._converter(dataset_id)
        manifest = converter.generate_manifest()
        if limit is not None:
            manifest.samples = manifest.samples[:limit]
            manifest.sample_count = len(manifest.samples)
        manifest_path = self._write_manifest(manifest)
        written = converter.write_processed_metadata(manifest)
        return {
            "dataset_id": dataset_id,
            "manifest_path": str(manifest_path),
            "converted_sample_count": len(written),
            "sample_count": manifest.sample_count,
            "issues": manifest.issues,
            "research_use_only": True,
        }

    def manifest_path(self, dataset_id: str) -> Path:
        return self.project_root / "datasets/external/common/manifests" / f"{dataset_id}_manifest.json"

    def summarize_external_datasets(self) -> dict[str, Any]:
        entries = self.load_registry()
        inspections = [self.inspect_dataset(entry.id) for entry in entries]
        return {
            "dataset_count": len(entries),
            "dataset_ids": [entry.id for entry in entries],
            "research_use_only": True,
            "license_review_required_count": sum(1 for entry in entries if entry.license_review_required),
            "downloaded_dataset_count": sum(
                1
                for inspection in inspections
                if inspection.raw_file_count > 0 or inspection.processed_file_count > 0
            ),
            "issues": [
                issue
                for inspection in inspections
                for issue in inspection.issues
            ],
        }

    def print_download_instructions(self, dataset_id: str) -> str:
        entry = self.get_dataset_entry(dataset_id)
        lines = [
            "External datasets are research-only and not accuracy proof.",
            f"Dataset: {entry.name}",
            f"Download policy: {entry.download_policy}",
            "Review the license before downloading.",
        ]
        if entry.repo_url:
            lines.append(f"Repository: {entry.repo_url}")
        if entry.project_url:
            lines.append(f"Project/dataset page: {entry.project_url}")
        if entry.paper_url:
            lines.append(f"Paper: {entry.paper_url}")
        if dataset_id == "footgait3d":
            lines.append("For Hugging Face, use the dataset page and explicit local download tooling only.")
        else:
            lines.append("Use the official README/project page download instructions. No automatic download is performed.")
        lines.append(f"Place raw files under: {entry.local_raw_dir}")
        return "\n".join(lines)

    def _converter(self, dataset_id: str) -> ExternalDatasetConverter:
        entry = self.get_dataset_entry(dataset_id)
        converter_cls = self.converter_classes.get(dataset_id, ExternalDatasetConverter)
        return converter_cls(entry, self.project_root)

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.project_root / path

    def _validate_unique_ids(self, entries: list[ExternalDatasetRegistryEntry]) -> None:
        ids = [entry.id for entry in entries]
        if len(ids) != len(set(ids)):
            raise ValueError("External dataset registry contains duplicate ids.")

    def _generated_dataset_entry(self) -> ExternalDatasetRegistryEntry:
        return ExternalDatasetRegistryEntry.model_validate(
            {
                "id": "generated_foot_masks_from_focus",
                "name": "Generated Foot Masks From FOCUS Meshes",
                "repo_url": None,
                "project_url": None,
                "paper_url": "https://arxiv.org/abs/2502.06367",
                "dataset_type": ["synthetic_rgb", "masks", "quality_labels", "mesh_projection"],
                "intended_use": ["research", "mask_quality", "segmentation_baseline"],
                "not_for": ["production_accuracy_claims", "real_phone_measurement_benchmark", "shoe_size_accuracy_claims"],
                "download_policy": "generated_locally_from_focus_meshes",
                "license_review_required": True,
                "local_raw_dir": "datasets/external/generated_foot_masks",
                "local_processed_dir": "datasets/external/generated_foot_masks/metadata",
            }
        )
