from __future__ import annotations

import argparse
import shutil
import subprocess
import re
import tarfile
import zipfile
import json
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.external_dataset_service import ExternalDatasetService  # noqa: E402


RESEARCH_WARNING = "External datasets are research-only and do not prove measurement accuracy."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage research-only external foot datasets.")
    parser.add_argument("--dataset-root", default=None, help="Optional project root override.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List supported external datasets.")
    subparsers.add_parser("prepare-folders", help="Create external dataset folders.")
    subparsers.add_parser("prepare-all", help="Create folders and print all supported datasets.")
    subparsers.add_parser("inspect-all", help="Inspect every registered dataset.")
    subparsers.add_parser("manifest-all", help="Generate manifests for every registered dataset.")

    info = subparsers.add_parser("info", help="Show registry information for a dataset.")
    info.add_argument("--dataset", required=True)

    inspect = subparsers.add_parser("inspect", help="Inspect local dataset files.")
    inspect.add_argument("--dataset", required=True)

    manifest = subparsers.add_parser("manifest", help="Generate a common manifest.")
    manifest.add_argument("--dataset", required=True)

    discover = subparsers.add_parser("discover-links", help="Discover official README/project links.")
    discover.add_argument("--dataset", required=True)
    discover.add_argument("--deep", action="store_true")

    convert = subparsers.add_parser("convert", help="Convert detected files to common metadata.")
    convert.add_argument("--dataset", required=True)
    convert.add_argument("--limit", type=int, default=None)

    convert_all = subparsers.add_parser("convert-all", help="Convert all registered datasets.")
    convert_all.add_argument("--limit", type=int, default=None)

    instructions = subparsers.add_parser("print-download-instructions", help="Print safe download instructions.")
    instructions.add_argument("--dataset", required=True)

    download = subparsers.add_parser("download", help="Download only when safe, licensed, and explicit.")
    download.add_argument("--dataset", required=True)
    download.add_argument("--accept-license", action="store_true")
    download.add_argument("--explicit", action="store_true")
    download.add_argument("--dry-run", action="store_true")
    download.add_argument("--max-files", type=int, default=None)
    download.add_argument("--limit-files", type=int, default=None)
    download.add_argument("--try-all", action="store_true")
    download.add_argument("--extract", action="store_true")
    download.add_argument("--allow-large-download", action="store_true")

    extract = subparsers.add_parser("extract", help="Extract known local archives only when explicit.")
    extract.add_argument("--dataset", required=True)
    extract.add_argument("--explicit", action="store_true")
    extract.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(args.dataset_root) if args.dataset_root else PROJECT_ROOT
    service = ExternalDatasetService(project_root=project_root)
    print(RESEARCH_WARNING)

    if args.command == "list":
        print(json.dumps(service.list_supported_datasets(), indent=2))
        return 0
    if args.command in {"prepare-folders", "prepare-all"}:
        prepare_folders(service)
        payload: dict[str, Any] = {"prepared": True, "dataset_count": len(service.load_registry())}
        if args.command == "prepare-all":
            payload["datasets"] = [entry.id for entry in service.load_registry()]
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "info":
        print(json.dumps(service.get_dataset_entry(args.dataset).model_dump(mode="json"), indent=2))
        return 0
    if args.command == "inspect":
        print(json.dumps(service.inspect_dataset(args.dataset).model_dump(mode="json"), indent=2))
        return 0
    if args.command == "inspect-all":
        print(json.dumps([service.inspect_dataset(entry.id).model_dump(mode="json") for entry in service.load_registry()], indent=2))
        return 0
    if args.command == "manifest":
        output_path = service.create_common_manifest(args.dataset)
        print(json.dumps({"manifest_path": str(output_path)}, indent=2))
        return 0
    if args.command == "discover-links":
        print(json.dumps(discover_links(service, args.dataset, deep=args.deep), indent=2))
        return 0
    if args.command == "manifest-all":
        paths = [str(service.create_common_manifest(entry.id)) for entry in service.load_registry()]
        print(json.dumps({"manifest_paths": paths}, indent=2))
        return 0
    if args.command == "convert":
        print(json.dumps(service.convert_dataset(args.dataset, limit=args.limit), indent=2))
        return 0
    if args.command == "convert-all":
        print(json.dumps([service.convert_dataset(entry.id, limit=args.limit) for entry in service.load_registry()], indent=2))
        return 0
    if args.command == "print-download-instructions":
        print(service.print_download_instructions(args.dataset))
        return 0
    if args.command == "download":
        return handle_download(
            service,
            args.dataset,
            args.accept_license,
            args.explicit,
            dry_run=args.dry_run,
            max_files=args.max_files or args.limit_files,
            try_all=args.try_all,
            extract_after=args.extract,
            allow_large_download=args.allow_large_download,
        )
    if args.command == "extract":
        print(json.dumps(extract_dataset(service, args.dataset, explicit=args.explicit, overwrite=args.overwrite), indent=2))
        return 0
    return 2


def prepare_folders(service: ExternalDatasetService) -> None:
    for entry in service.load_registry():
        for folder in [
            entry.local_raw_dir,
            entry.local_processed_dir,
            f"datasets/external/{_folder_slug(entry.id)}/metadata",
        ]:
            path = service.project_root / folder
            path.mkdir(parents=True, exist_ok=True)
            (path / ".gitkeep").touch()
    for folder in [
        "datasets/external/common/processed",
        "datasets/external/common/manifests",
        "datasets/external/common/reports",
        "datasets/external/common/splits",
    ]:
        path = service.project_root / folder
        path.mkdir(parents=True, exist_ok=True)
        (path / ".gitkeep").touch()


def handle_download(
    service: ExternalDatasetService,
    dataset_id: str,
    accept_license: bool,
    explicit: bool,
    *,
    dry_run: bool = False,
    max_files: int | None = None,
    try_all: bool = False,
    extract_after: bool = False,
    allow_large_download: bool = False,
) -> int:
    entry = service.get_dataset_entry(dataset_id)
    estimate = estimate_disk_usage(service, dataset_id)
    links = {"links_found": []}
    attempt = {
        "dataset_id": dataset_id,
        "attempted": True,
        "downloaded": False,
        "files_downloaded": 0,
        "bytes_downloaded": 0,
        "manual_required": True,
        "methods_tried": [],
        "successful_method": None,
        "links": links.get("links_found", []),
        "issues": [],
        "next_steps": [],
    }
    if not accept_license or not explicit:
        print("Download refused. Pass both --accept-license and --explicit after reviewing dataset terms.")
        print(service.print_download_instructions(dataset_id))
        print(json.dumps({"disk_usage_estimate": estimate, "max_files": max_files}, indent=2))
        attempt["issues"].append("Missing --accept-license and/or --explicit.")
        attempt["next_steps"].append("Review license and rerun with both flags, or download manually.")
        write_download_attempt(service, dataset_id, attempt)
        return 1
    try:
        links = discover_links(service, dataset_id, deep=True)
    except TypeError:
        links = discover_links(service, dataset_id)
    attempt["links"] = links.get("links_found", [])
    if dry_run:
        print("Dry run only. No files were downloaded.")
        print(service.print_download_instructions(dataset_id))
        print(json.dumps({"disk_usage_estimate": estimate, "max_files": max_files}, indent=2))
        attempt["issues"].append("Dry run only. No files downloaded.")
        attempt["next_steps"].append("Remove --dry-run only after license review and disk check.")
        write_download_attempt(service, dataset_id, attempt)
        return 0
    raw_dir = service.project_root / entry.local_raw_dir
    before_files = set(_files(raw_dir))
    before_bytes = _bytes(raw_dir)
    if try_all:
        _try_clone_repo(service, entry, attempt)
    if dataset_id == "footgait3d":
        status = handle_huggingface_download(
            service,
            entry,
            max_files=max_files,
            allow_large_download=allow_large_download,
            attempt=attempt,
        )
        _finalize_download_attempt(service, dataset_id, raw_dir, before_files, before_bytes, attempt, "huggingface" if status == 0 else None)
        write_download_attempt(service, dataset_id, attempt)
        return status
    direct_links = [link for link in links.get("links_found", []) if link.get("link_type") == "direct_archive" or link.get("kind") == "direct_archive"]
    for link in direct_links:
        if _download_direct_archive(link["url"], raw_dir, attempt):
            break
    _finalize_download_attempt(service, dataset_id, raw_dir, before_files, before_bytes, attempt, attempt.get("successful_method"))
    if attempt["downloaded"] and not [link for link in links.get("links_found", []) if link.get("kind") == "google_drive"]:
        if extract_after:
            attempt["extraction"] = extract_dataset(service, dataset_id, explicit=True)
            _finalize_download_attempt(service, dataset_id, raw_dir, before_files, before_bytes, attempt, attempt.get("successful_method"))
        write_download_attempt(service, dataset_id, attempt)
        print(json.dumps(attempt, indent=2))
        return 0
    google_links = [link for link in links.get("links_found", []) if link.get("kind") == "google_drive"]
    if google_links:
        if try_all:
            for link in google_links:
                _try_google_drive_download(link["url"], raw_dir, attempt)
        else:
            attempt["issues"].append("Google Drive links discovered. Pass --try-all to attempt gdown.")
        _finalize_download_attempt(service, dataset_id, raw_dir, before_files, before_bytes, attempt, "google_drive")
        if extract_after:
            attempt["extraction"] = extract_dataset(service, dataset_id, explicit=True)
            _finalize_download_attempt(service, dataset_id, raw_dir, before_files, before_bytes, attempt, attempt.get("successful_method"))
        write_download_attempt(service, dataset_id, attempt)
        if attempt["manual_required"]:
            write_manual_required(service, dataset_id, attempt)
        print(json.dumps(attempt, indent=2))
        return 0
    print("Automatic download is not implemented safely for this dataset.")
    print("Use the official README/project page download instructions instead.")
    print(service.print_download_instructions(dataset_id))
    attempt["issues"].append("Dataset requires manual download from official instructions.")
    attempt["next_steps"].append(f"Place files under {entry.local_raw_dir}.")
    _finalize_download_attempt(service, dataset_id, raw_dir, before_files, before_bytes, attempt, None)
    write_download_attempt(service, dataset_id, attempt)
    write_manual_required(service, dataset_id, attempt)
    return 0


def handle_huggingface_download(
    service: ExternalDatasetService,
    entry,
    max_files: int | None = None,
    *,
    allow_large_download: bool = False,
    attempt: dict[str, Any] | None = None,
) -> int:
    attempt = attempt if attempt is not None else {"methods_tried": [], "issues": [], "next_steps": []}
    attempt["methods_tried"].append("huggingface_hub")
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("huggingface_hub is required for this optional download path.")
        print("pip install huggingface_hub")
        attempt["issues"].append("huggingface_hub is not installed.")
        attempt["next_steps"].append("pip install huggingface_hub")
        return 1
    print("Hugging Face download support is available, but this dataset is large.")
    if not allow_large_download:
        issue = "Large Hugging Face dataset download blocked. Pass --allow-large-download after disk and license review."
        print(issue)
        attempt["issues"].append(issue)
        attempt["next_steps"].append("Rerun with --allow-large-download only if you intentionally want the full dataset.")
        return 0
    if max_files is not None:
        print("--max-files is informational for snapshot_download and is not applied to avoid partial unsafe assumptions.")
    local_dir = service.project_root / entry.local_raw_dir
    local_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id="ljw285/FootGait3D", repo_type="dataset", local_dir=str(local_dir))
    return 0


def estimate_disk_usage(service: ExternalDatasetService, dataset_id: str) -> dict[str, Any]:
    entry = service.get_dataset_entry(dataset_id)
    raw_dir = service.project_root / entry.local_raw_dir
    existing_bytes = 0
    if raw_dir.exists():
        existing_bytes = sum(path.stat().st_size for path in raw_dir.rglob("*") if path.is_file())
    known = {"footgait3d": "about 81 GB from Hugging Face page"}
    return {
        "existing_raw_bytes": existing_bytes,
        "known_remote_size": known.get(dataset_id, "unknown"),
    }


def discover_links(service: ExternalDatasetService, dataset_id: str, *, deep: bool = False) -> dict[str, Any]:
    entry = service.get_dataset_entry(dataset_id)
    urls = [url for url in [entry.repo_url, entry.project_url, entry.paper_url] if url]
    links: list[dict[str, str | bool]] = []
    issues: list[str] = []
    for url in urls:
        try:
            text = fetch_text(readme_url(url))
        except Exception as exc:
            issues.append(f"Could not read {url}: {exc}")
            continue
        links.extend(_extract_links(text, source_page=url))
        if deep and "github.com" in url:
            links.extend(_discover_github_release_links(url, issues))
    links.extend(
        _link_payload(clean_discovered_url(url), source_page="registry", text="registry")
        for url in [entry.repo_url, entry.project_url, entry.paper_url]
        if url
    )
    unique = []
    seen = set()
    for link in links:
        if link["url"] not in seen:
            seen.add(link["url"])
            unique.append(link)
    downloadable = [link for link in unique if link.get("automatic_download_possible")]
    manual = [link for link in unique if link["kind"] in {"google_drive", "unknown", "github"}]
    payload = {
        "dataset_id": dataset_id,
        "deep": deep,
        "links_found": unique,
        "downloadable_automatically": downloadable,
        "manual_required": manual,
        "issues": issues,
    }
    metadata_dir(service, dataset_id).mkdir(parents=True, exist_ok=True)
    (metadata_dir(service, dataset_id) / "discovered_links.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    return payload


def _extract_links(text: str, *, source_page: str) -> list[dict[str, str | bool]]:
    links: list[dict[str, str | bool]] = []
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href"))
            if href.startswith("//"):
                href = "https:" + href
            if href.startswith("/") and source_page.startswith("http"):
                href = source_page.rstrip("/") + href
            if href.startswith("http"):
                links.append(_link_payload(clean_discovered_url(href), source_page=source_page, text=anchor.get_text(" ", strip=True)))
    except Exception:
        pass
    for match in sorted(set(re.findall(r"https?://[^\s)>\"]+", text))):
        url = clean_discovered_url(match)
        links.append(_link_payload(url, source_page=source_page, text=""))
    return links


def _discover_github_release_links(url: str, issues: list[str]) -> list[dict[str, str | bool]]:
    parts = clean_discovered_url(url).rstrip("/").split("/")
    if len(parts) < 5:
        return []
    owner, repo = parts[-2], parts[-1].removesuffix(".git")
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    try:
        data = json.loads(fetch_text(api_url))
    except Exception as exc:
        issues.append(f"Could not read GitHub releases for {owner}/{repo}: {exc}")
        return []
    links: list[dict[str, str | bool]] = []
    if isinstance(data, list):
        for release in data:
            for asset in release.get("assets", []):
                browser_url = asset.get("browser_download_url")
                if browser_url:
                    links.append(_link_payload(browser_url, source_page=api_url, text=asset.get("name", "release asset")))
    return links


def _link_payload(url: str, *, source_page: str, text: str = "") -> dict[str, str | bool]:
    link_type = classify_link(url)
    automatic = link_type in {"huggingface", "direct_archive"}
    reason = "Direct archive or Hugging Face link." if automatic else "Manual review or special downloader required."
    if link_type == "google_drive":
        automatic = True
        reason = "Google Drive may be automatic if gdown can access the public file/folder."
    return {
        "url": url,
        "source_page": source_page,
        "kind": link_type,
        "link_type": link_type,
        "text": text,
        "automatic_download_possible": automatic,
        "reason": reason,
    }


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "JutaSizeDatasetManager/1.0"})
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")


def clean_discovered_url(url: str) -> str:
    return url.strip().rstrip(".,]`'\"")


def readme_url(url: str) -> str:
    if "github.com" not in url:
        return url
    parts = url.rstrip("/").split("/")
    if len(parts) >= 5:
        owner, repo = parts[-2], parts[-1]
        return f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md"
    return url


def classify_link(url: str) -> str:
    lower = url.lower()
    if "github.com" in lower or "raw.githubusercontent.com" in lower:
        return "github"
    if "huggingface.co" in lower:
        return "huggingface"
    if "drive.google.com" in lower or "docs.google.com" in lower:
        return "google_drive"
    if any(lower.endswith(ext) for ext in [".zip", ".tar", ".tar.gz", ".tgz"]):
        return "direct_archive"
    return "unknown"


def _try_clone_repo(service: ExternalDatasetService, entry, attempt: dict[str, Any]) -> None:
    if not entry.repo_url or "github.com" not in entry.repo_url:
        return
    attempt["methods_tried"].append("git_clone_repo")
    if shutil.which("git") is None:
        attempt["issues"].append("git is not available for repo clone discovery.")
        return
    clone_dir = metadata_dir(service, entry.id) / "repo_clone"
    if clone_dir.exists():
        attempt["issues"].append(f"Reusing existing repo clone cache: {clone_dir}")
    else:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", entry.repo_url, str(clone_dir)],
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
        if result.returncode != 0:
            attempt["issues"].append(f"Repo clone failed: {result.stderr[-500:]}")
            return
    data_files = [
        path
        for path in clone_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".ply", ".obj", ".npy", ".npz"}
    ]
    attempt["repo_clone_path"] = str(clone_dir)
    attempt["repo_clone_data_file_count"] = len(data_files)
    if data_files:
        attempt["issues"].append("Repo clone contains possible data files, but repo code is not treated as dataset payload automatically.")


def _try_google_drive_download(url: str, raw_dir: Path, attempt: dict[str, Any]) -> bool:
    attempt["methods_tried"].append("gdown")
    try:
        import gdown
    except ImportError:
        attempt["issues"].append("Google Drive link discovered, but gdown is not installed.")
        attempt["next_steps"].append("Install with: pip install gdown")
        return False
    raw_dir.mkdir(parents=True, exist_ok=True)
    try:
        if "/folders/" in url:
            result = gdown.download_folder(url=url, output=str(raw_dir), quiet=False, use_cookies=False)
            if result:
                attempt["successful_method"] = "gdown_folder"
                return True
            attempt["issues"].append(f"gdown folder returned no files for {url}")
            return False
        output = raw_dir / _google_drive_filename(url)
        result = gdown.download(url=url, output=str(output), quiet=False, use_cookies=False)
        if result:
            attempt["successful_method"] = "gdown_file"
            return True
        attempt["issues"].append(f"gdown file returned no file for {url}")
        return False
    except Exception as exc:
        attempt["issues"].append(f"gdown failed for {url}: {exc}")
        return False


def _google_drive_filename(url: str) -> str:
    match = re.search(r"/file/d/([^/]+)", url)
    if match:
        return f"{match.group(1)}.download"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", url.split("/")[-1] or "google_drive_file")


def _download_direct_archive(url: str, raw_dir: Path, attempt: dict[str, Any]) -> bool:
    attempt["methods_tried"].append("direct_archive")
    try:
        import requests
    except ImportError:
        attempt["issues"].append("requests is required for direct archive download.")
        return False
    raw_dir.mkdir(parents=True, exist_ok=True)
    filename = clean_discovered_url(url).split("/")[-1] or "downloaded_archive"
    target = raw_dir / filename
    try:
        with requests.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()
            with target.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        attempt["successful_method"] = "direct_archive"
        return target.exists() and target.stat().st_size > 0
    except Exception as exc:
        attempt["issues"].append(f"Direct archive download failed for {url}: {exc}")
        if target.exists() and target.stat().st_size == 0:
            target.unlink()
        return False


def _finalize_download_attempt(
    service: ExternalDatasetService,
    dataset_id: str,
    raw_dir: Path,
    before_files: set[Path],
    before_bytes: int,
    attempt: dict[str, Any],
    method: str | None,
) -> None:
    after_files = set(_files(raw_dir))
    new_files = after_files - before_files
    downloaded = len(new_files) > 0
    attempt["downloaded"] = downloaded
    attempt["files_downloaded"] = len(new_files)
    attempt["bytes_downloaded"] = max(_bytes(raw_dir) - before_bytes, 0)
    attempt["manual_required"] = not downloaded
    if downloaded and method and not attempt.get("successful_method"):
        attempt["successful_method"] = method
    if downloaded:
        attempt["next_steps"].append("Inspect files, generate manifests, convert samples, then build splits.")
    else:
        entry = service.get_dataset_entry(dataset_id)
        attempt["next_steps"].append(f"Place official dataset files under {entry.local_raw_dir} if automatic access is blocked.")


def _files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [path for path in root.rglob("*") if path.is_file() and path.name != ".gitkeep"]


def _bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in _files(root))


def extract_dataset(
    service: ExternalDatasetService,
    dataset_id: str,
    *,
    explicit: bool,
    overwrite: bool = False,
) -> dict[str, Any]:
    entry = service.get_dataset_entry(dataset_id)
    raw_dir = service.project_root / entry.local_raw_dir
    report = {
        "dataset_id": dataset_id,
        "attempted": explicit,
        "extracted": False,
        "archives_found": [],
        "files_extracted": 0,
        "issues": [],
    }
    if not explicit:
        report["issues"].append("Extraction refused. Pass --explicit.")
        write_extraction_report(service, dataset_id, report)
        return report
    archives = [
        path
        for path in raw_dir.glob("*")
        if _is_supported_archive(path)
    ]
    report["archives_found"] = [str(path) for path in archives]
    if not archives:
        report["issues"].append("No supported archives found.")
        write_extraction_report(service, dataset_id, report)
        return report
    for archive in archives:
        target = raw_dir / archive.stem.replace(".tar", "")
        if target.exists() and not overwrite:
            report["issues"].append(f"Skipped existing target: {target}")
            continue
        target.mkdir(parents=True, exist_ok=True)
        before = len(list(target.rglob("*")))
        if _is_zip_archive(archive):
            with zipfile.ZipFile(archive) as handle:
                handle.extractall(target)
        else:
            with tarfile.open(archive) as handle:
                handle.extractall(target)
        after = len(list(target.rglob("*")))
        report["files_extracted"] += max(after - before, 0)
    report["extracted"] = report["files_extracted"] > 0
    write_extraction_report(service, dataset_id, report)
    return report


def _is_supported_archive(path: Path) -> bool:
    return path.suffix.lower() == ".zip" or path.name.lower().endswith((".tar", ".tar.gz", ".tgz")) or _is_zip_archive(path)


def _is_zip_archive(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"PK\x03\x04"
    except OSError:
        return False


def metadata_dir(service: ExternalDatasetService, dataset_id: str) -> Path:
    return service.project_root / "datasets/external" / _folder_slug(dataset_id) / "metadata"


def write_download_attempt(service: ExternalDatasetService, dataset_id: str, payload: dict[str, Any]) -> None:
    path = metadata_dir(service, dataset_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "download_attempt.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_manual_required(service: ExternalDatasetService, dataset_id: str, payload: dict[str, Any]) -> None:
    path = metadata_dir(service, dataset_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "manual_download_required.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_extraction_report(service: ExternalDatasetService, dataset_id: str, payload: dict[str, Any]) -> None:
    path = metadata_dir(service, dataset_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "extraction_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _folder_slug(dataset_id: str) -> str:
    return {
        "focus_synfoot2_foot3d": "focus",
        "found_synfoot": "found",
        "find_foot3d": "find_foot3d",
        "footgait3d": "footgait3d",
    }.get(dataset_id, dataset_id)


if __name__ == "__main__":
    raise SystemExit(main())
