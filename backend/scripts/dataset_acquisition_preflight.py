from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent


OPTIONAL_PACKAGES = {
    "huggingface_hub": "huggingface_hub",
    "gdown": "gdown",
    "requests": "requests",
    "sklearn": "scikit-learn",
    "joblib": "joblib",
    "torch": "torch",
}


def run_preflight(
    project_root: Path = PROJECT_ROOT,
    *,
    install_missing_tools: bool = False,
) -> dict[str, Any]:
    internet = {
        "github.com": _check_url("https://github.com"),
        "huggingface.co": _check_url("https://huggingface.co"),
        "drive.google.com": _check_url("https://drive.google.com"),
    }
    disk = _disk(project_root)
    tool_details = {name: _package_status(name, pip_name) for name, pip_name in OPTIONAL_PACKAGES.items()}
    tools = {
        "git_lfs": shutil.which("git-lfs") is not None,
        **{name: details["available"] for name, details in tool_details.items()},
    }
    issues: list[str] = []
    instructions: list[str] = []
    if not (project_root / "datasets/external").exists():
        issues.append("datasets/external folder is missing.")
        instructions.append("Run python backend/scripts/external_dataset_manager.py prepare-all")
    for host, ok in internet.items():
        if not ok:
            issues.append(f"Internet connectivity check failed for {host}.")
    missing = [
        pip_name
        for tool, pip_name in OPTIONAL_PACKAGES.items()
        if tool != "torch" and not tools.get(tool)
    ]
    if missing:
        instructions.append(f"Install optional tools with: pip install {' '.join(missing)}")
        if install_missing_tools:
            subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=False)
            tools.update(
                {
                    name: importlib.util.find_spec(import_name) is not None
                    for name, import_name in OPTIONAL_PACKAGES.items()
                }
            )
            tool_details.update({name: _package_status(name, pip_name) for name, pip_name in OPTIONAL_PACKAGES.items()})
    if not tools["git_lfs"]:
        instructions.append("Install git-lfs if any official dataset uses LFS: https://git-lfs.com/")
    return {
        "ready": bool(all(internet.values()) and (project_root / "datasets/external").exists()),
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "platform": platform.platform(),
            "is_windows": platform.system().lower() == "windows",
        },
        "project_root": str(project_root),
        "internet": internet,
        "disk": disk,
        "tools": tools,
        "tool_versions": tool_details,
        "issues": issues,
        "instructions": instructions,
    }


def _check_url(url: str) -> bool:
    try:
        request = Request(url, headers={"User-Agent": "JutaSizeDatasetPreflight/1.0"})
        with urlopen(request, timeout=8) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def _package_status(import_name: str, pip_name: str) -> dict[str, Any]:
    available = importlib.util.find_spec(import_name) is not None
    version = None
    if available:
        try:
            version = importlib.metadata.version(pip_name)
        except importlib.metadata.PackageNotFoundError:
            version = "installed"
    return {"available": available, "version": version, "pip_package": pip_name}


def _disk(path: Path) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "free_gb": round(usage.free / (1024**3), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check readiness for external dataset acquisition.")
    parser.add_argument("--install-missing-tools", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_preflight(install_missing_tools=args.install_missing_tools), indent=2))


if __name__ == "__main__":
    main()
