from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from scripts.check_dataset_population import TRAINING_TASK_LABELS  # noqa: E402


def build_splits(
    dataset_id: str,
    task: str,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    *,
    limit: int | None = None,
    seed: int = 42,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    manifest_path = project_root / "datasets/external/common/manifests" / f"{dataset_id}_manifest.json"
    output_dir = project_root / "datasets/external/common/splits"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{dataset_id}_{task}_splits.json"
    issues: list[str] = []
    if task not in TRAINING_TASK_LABELS:
        issues.append(f"Unsupported task: {task}")
        payload = _payload(dataset_id, task, [], [], [], issues)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
    if not manifest_path.exists():
        issues.append("Manifest does not exist. Run external_dataset_manager.py manifest first.")
        payload = _payload(dataset_id, task, [], [], [], issues)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = TRAINING_TASK_LABELS[task]
    samples = [
        sample.get("sample_id")
        for sample in manifest.get("samples") or []
        if required.issubset(set(sample.get("available_labels") or []))
    ]
    samples = [sample for sample in samples if sample]
    if limit is not None:
        samples = samples[:limit]
    if len(samples) < 3:
        issues.append(f"Not enough samples with required labels for {task}.")
        payload = _payload(dataset_id, task, samples, [], [], issues)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
    total = train_ratio + val_ratio + test_ratio
    if total <= 0:
        issues.append("Split ratios must sum to a positive number.")
        payload = _payload(dataset_id, task, [], [], [], issues)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
    normalized = [train_ratio / total, val_ratio / total, test_ratio / total]
    rng = random.Random(seed)
    rng.shuffle(samples)
    train_count = max(1, int(len(samples) * normalized[0]))
    val_count = max(1, int(len(samples) * normalized[1]))
    if train_count + val_count >= len(samples):
        val_count = 1
        train_count = max(1, len(samples) - 2)
    train = samples[:train_count]
    val = samples[train_count : train_count + val_count]
    test = samples[train_count + val_count :]
    payload = _payload(dataset_id, task, train, val, test, issues)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _payload(
    dataset_id: str,
    task: str,
    train: list[str],
    val: list[str],
    test: list[str],
    issues: list[str],
) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "task": task,
        "sample_count": len(train) + len(val) + len(test),
        "train": train,
        "val": val,
        "test": test,
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic research train/val/test splits.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--train", type=float, default=0.8)
    parser.add_argument("--val", type=float, default=0.1)
    parser.add_argument("--test", type=float, default=0.1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(build_splits(args.dataset, args.task, args.train, args.val, args.test, limit=args.limit, seed=args.seed), indent=2))


if __name__ == "__main__":
    main()
