from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.external_dataset_service import ExternalDatasetService  # noqa: E402
from scripts.build_research_splits import build_splits  # noqa: E402
from scripts.check_dataset_population import check_population  # noqa: E402
from scripts.dataset_acquisition_preflight import run_preflight  # noqa: E402
from scripts.external_dataset_manager import (  # noqa: E402
    discover_links,
    extract_dataset,
    handle_download,
    prepare_folders,
)
from scripts.setup_dataset_tools import setup_tools  # noqa: E402
from scripts.train_research_models import train_research_model  # noqa: E402


def run_pipeline(
    dataset_id: str,
    task: str,
    *,
    accept_license: bool = False,
    explicit: bool = False,
    limit: int | None = None,
    project_root: Path = PROJECT_ROOT,
    discover: bool = False,
    download: bool = False,
    extract: bool = False,
    manifest: bool = False,
    convert: bool = False,
    split: bool = False,
    train: bool = False,
    safe_auto: bool = False,
    full_auto: bool = False,
    try_all: bool = False,
    install_missing_tools: bool = False,
    allow_large_download: bool = False,
) -> dict[str, Any]:
    service = ExternalDatasetService(project_root=project_root)
    prepare_folders(service)
    tool_setup = setup_tools(install=install_missing_tools) if install_missing_tools else None
    preflight = run_preflight(project_root)
    do_all = full_auto or safe_auto or not any([discover, download, extract, manifest, convert, split, train])
    links = discover_links(service, dataset_id, deep=full_auto or try_all) if (discover or do_all) else {"links_found": []}
    download_status = None
    if download or safe_auto or full_auto:
        download_status = handle_download(
            service,
            dataset_id,
            accept_license,
            explicit,
            dry_run=safe_auto and not (accept_license and explicit),
            max_files=limit,
            try_all=try_all or full_auto,
            extract_after=extract or full_auto,
            allow_large_download=allow_large_download,
        )
    extraction = extract_dataset(service, dataset_id, explicit=explicit) if extract and not full_auto else None
    inspection = service.inspect_dataset(dataset_id)
    manifest_path = service.create_common_manifest(dataset_id) if (manifest or do_all) else service.manifest_path(dataset_id)
    conversion = service.convert_dataset(dataset_id, limit=limit) if (convert or do_all) else {"converted_sample_count": 0}
    split_result = (
        build_splits(dataset_id, task, 0.8, 0.1, 0.1, limit=limit, project_root=project_root)
        if (split or do_all)
        else {"issues": ["Split stage not requested."]}
    )
    training = (
        train_research_model(task, dataset_id, limit=limit, project_root=project_root)
        if (train or do_all) and not split_result.get("issues")
        else {"status": "skipped", "reason": "Split is not training-ready.", "research_only": True}
    )
    population = check_population(project_root=project_root)
    dataset_status = population["datasets"].get(dataset_id, {})
    status = _pipeline_status(dataset_status, training)
    report = {
        "dataset_id": dataset_id,
        "status": status,
        "preflight_ready": preflight.get("ready", False),
        "links_discovered": len(links.get("links_found", [])),
        "download_attempted": download_status is not None,
        "downloaded": bool(download_status == 0 and dataset_status.get("raw_file_count", 0) > 0),
        "manual_required": dataset_status.get("raw_file_count", 0) == 0,
        "raw_file_count": dataset_status.get("raw_file_count", 0),
        "manifest_sample_count": dataset_status.get("sample_count", 0),
        "converted_sample_count": dataset_status.get("converted_sample_count", 0),
        "training_ready": dataset_status.get("status") == "training_ready",
        "training_status": training.get("status", "skipped"),
        "model_artifacts": _model_artifacts(project_root),
        "production_enabled": False,
        "next_steps": _next_steps(dataset_id, dataset_status),
        "details": {
            "tool_setup": tool_setup,
            "preflight": preflight,
            "links": links,
            "extraction": extraction,
            "inspection": inspection.model_dump(mode="json"),
            "manifest_path": str(manifest_path),
            "conversion": conversion,
            "split": split_result,
            "training": training,
        },
        "conversion": conversion,
        "training": training,
        "research_only": True,
    }
    output_dir = project_root / "artifacts/external_dataset_pipeline"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (f"{dataset_id}_full_auto_report.json" if full_auto else f"{dataset_id}_full_pipeline_report.json")
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _model_artifacts(project_root: Path) -> list[str]:
    root = project_root / "models/research"
    if not root.exists():
        return []
    return [
        str(path)
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".json", ".joblib", ".pt"}
    ]


def _pipeline_status(dataset_status: dict[str, Any], training: dict[str, Any]) -> str:
    if dataset_status.get("raw_file_count", 0) == 0:
        return "waiting_for_dataset_files"
    if dataset_status.get("status") == "training_ready" and training.get("status") in {"trained", "rule_based_fallback"}:
        return "trained"
    if dataset_status.get("converted_sample_count", 0) > 0:
        return "converted"
    return dataset_status.get("status", "unknown")


def _next_steps(dataset_id: str, status: dict[str, Any]) -> list[str]:
    if status.get("raw_file_count", 0) == 0:
        return [
            f"Run: python backend/scripts/external_dataset_manager.py print-download-instructions --dataset {dataset_id}",
            "Download official dataset files after license review and place them in the raw folder.",
        ]
    if status.get("status") != "training_ready":
        return ["Run manifest, convert, and split commands after verifying labels."]
    return ["Run train_research_models.py for the desired research task."]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the safe external dataset acquisition/training pipeline.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--task", default="mask_quality")
    parser.add_argument("--accept-license", action="store_true")
    parser.add_argument("--explicit", action="store_true")
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--manifest", action="store_true")
    parser.add_argument("--convert", action="store_true")
    parser.add_argument("--split", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--safe-auto", action="store_true")
    parser.add_argument("--full-auto", action="store_true")
    parser.add_argument("--try-all", action="store_true")
    parser.add_argument("--install-missing-tools", action="store_true")
    parser.add_argument("--allow-large-download", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print(
        json.dumps(
            run_pipeline(
                args.dataset,
                args.task,
                accept_license=args.accept_license,
                explicit=args.explicit,
                limit=args.limit,
                discover=args.discover,
                download=args.download,
                extract=args.extract,
                manifest=args.manifest,
                convert=args.convert,
                split=args.split,
                train=args.train,
                safe_auto=args.safe_auto,
                full_auto=args.full_auto,
                try_all=args.try_all,
                install_missing_tools=args.install_missing_tools,
                allow_large_download=args.allow_large_download,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
