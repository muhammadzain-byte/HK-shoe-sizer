from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import subprocess
import sys
from typing import Any


SAFE_PACKAGES = {
    "requests": "requests",
    "beautifulsoup4": "bs4",
    "gdown": "gdown",
    "huggingface_hub": "huggingface_hub",
    "scikit-learn": "sklearn",
    "joblib": "joblib",
    "tqdm": "tqdm",
    "pillow": "PIL",
    "opencv-python": "cv2",
    "numpy": "numpy",
}


def setup_tools(*, install: bool = False) -> dict[str, Any]:
    before = _status()
    install_results: dict[str, Any] = {}
    missing = [pip_name for pip_name, import_name in SAFE_PACKAGES.items() if not before[import_name]["available"]]
    if install and missing:
        for package in missing:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package],
                check=False,
                capture_output=True,
                text=True,
            )
            install_results[package] = {
                "returncode": result.returncode,
                "installed": result.returncode == 0,
                "stdout_tail": result.stdout[-1000:],
                "stderr_tail": result.stderr[-1000:],
            }
    after = _status()
    return {
        "python": sys.version.split()[0],
        "install_requested": install,
        "missing_before": missing,
        "packages": after,
        "install_results": install_results,
        "instructions": [
            "Only normal pip packages are installed.",
            "If a package failed to install, the dataset pipeline will continue with available tools.",
        ],
    }


def _status() -> dict[str, dict[str, Any]]:
    status: dict[str, dict[str, Any]] = {}
    for pip_name, import_name in SAFE_PACKAGES.items():
        available = importlib.util.find_spec(import_name) is not None
        version = None
        if available:
            try:
                version = importlib.metadata.version(pip_name)
            except importlib.metadata.PackageNotFoundError:
                version = "installed"
        status[import_name] = {
            "pip_package": pip_name,
            "available": available,
            "version": version,
        }
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description="Check or install safe dataset helper packages.")
    parser.add_argument("--install", action="store_true", help="Install missing safe pip packages.")
    args = parser.parse_args()
    print(json.dumps(setup_tools(install=args.install), indent=2))


if __name__ == "__main__":
    main()
