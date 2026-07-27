from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(slots=True)
class MeshLoadResult:
    path: str
    points: np.ndarray
    source_type: str
    issues: list[str]


def load_mesh_points(path: str | Path) -> MeshLoadResult:
    mesh_path = Path(path)
    suffix = mesh_path.suffix.lower()
    issues: list[str] = []
    if not mesh_path.exists():
        return MeshLoadResult(str(mesh_path), np.empty((0, 3), dtype=np.float32), "missing", ["Mesh file does not exist."])
    try:
        if suffix == ".obj":
            points = _load_obj_vertices(mesh_path)
            source_type = "obj"
        elif suffix == ".ply":
            points = _load_ascii_ply_vertices(mesh_path)
            source_type = "ply"
        elif suffix == ".npy":
            points = np.load(mesh_path)
            source_type = "npy"
        elif suffix == ".npz":
            payload = np.load(mesh_path)
            first_key = next(iter(payload.files), None)
            points = payload[first_key] if first_key else np.empty((0, 3), dtype=np.float32)
            source_type = "npz"
        else:
            return MeshLoadResult(str(mesh_path), np.empty((0, 3), dtype=np.float32), suffix.lstrip("."), ["Unsupported mesh/point file type."])
        normalized = normalize_points(points)
        if normalized.shape[0] < 3:
            issues.append("Mesh has fewer than 3 usable vertices.")
        return MeshLoadResult(str(mesh_path), normalized, source_type, issues)
    except Exception as exc:
        return MeshLoadResult(str(mesh_path), np.empty((0, 3), dtype=np.float32), suffix.lstrip("."), [f"Failed to load mesh: {exc}"])


def normalize_points(points: np.ndarray) -> np.ndarray:
    array = np.asarray(points, dtype=np.float32)
    if array.ndim > 2:
        array = array.reshape(-1, array.shape[-1])
    if array.ndim != 2 or array.shape[1] < 2:
        return np.empty((0, 3), dtype=np.float32)
    if array.shape[1] == 2:
        array = np.column_stack([array, np.zeros(array.shape[0], dtype=np.float32)])
    else:
        array = array[:, :3]
    array = array[np.all(np.isfinite(array), axis=1)]
    if array.size == 0:
        return np.empty((0, 3), dtype=np.float32)
    centered = array - np.mean(array, axis=0, keepdims=True)
    scale = float(np.max(np.ptp(centered, axis=0)))
    if scale <= 0:
        return np.empty((0, 3), dtype=np.float32)
    return centered / scale


def _load_obj_vertices(path: Path) -> np.ndarray:
    vertices: list[list[float]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.startswith("v "):
                continue
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return np.asarray(vertices, dtype=np.float32)


def _load_ascii_ply_vertices(path: Path) -> np.ndarray:
    vertices: list[list[float]] = []
    vertex_count = 0
    in_header = True
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            stripped = line.strip()
            if in_header:
                if stripped.startswith("element vertex"):
                    vertex_count = int(stripped.split()[-1])
                elif stripped == "end_header":
                    in_header = False
                continue
            if vertex_count <= 0:
                break
            parts = stripped.split()
            if len(parts) >= 3:
                vertices.append([float(parts[0]), float(parts[1]), float(parts[2])])
            if len(vertices) >= vertex_count:
                break
    return np.asarray(vertices, dtype=np.float32)
