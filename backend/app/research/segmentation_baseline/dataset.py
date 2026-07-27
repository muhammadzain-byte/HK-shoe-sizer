from __future__ import annotations

from pathlib import Path


def dataset_ready(manifest_path: Path) -> bool:
    return manifest_path.exists()
