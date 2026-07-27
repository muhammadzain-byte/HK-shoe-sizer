from __future__ import annotations

from pathlib import Path

import numpy as np

from app.research.synthetic_foot_renderer.augmentation import QUALITY_LABELS, augment_mask
from app.research.synthetic_foot_renderer.mesh_loader import load_mesh_points
from app.research.synthetic_foot_renderer.projection_renderer import render_top_down, rgb_from_mask


def write_tiny_obj(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "v -1 -2 0",
                "v 1 -2 0",
                "v 1 2 0",
                "v -1 2 0",
                "v 0 -2.5 0",
                "v 0 2.5 0",
                "f 1 2 3",
                "f 1 3 4",
            ]
        ),
        encoding="utf-8",
    )


def test_tiny_obj_can_be_loaded(tmp_path: Path) -> None:
    obj = tmp_path / "foot.obj"
    write_tiny_obj(obj)

    result = load_mesh_points(obj)

    assert result.issues == []
    assert result.points.shape[0] == 6
    assert result.points.shape[1] == 3


def test_renderer_creates_binary_mask_and_rgb(tmp_path: Path) -> None:
    obj = tmp_path / "foot.obj"
    write_tiny_obj(obj)
    points = load_mesh_points(obj).points

    rendered = render_top_down(points, image_size=(96, 64), seed=1)
    image = rgb_from_mask(rendered.mask)

    assert rendered.mask.shape == (96, 64)
    assert set(np.unique(rendered.mask)).issubset({0, 255})
    assert rendered.mask.max() == 255
    assert image.shape == (96, 64, 3)


def test_augmentations_create_damaged_classes() -> None:
    mask = np.zeros((96, 64), dtype=np.uint8)
    mask[16:82, 20:44] = 255

    for label in QUALITY_LABELS:
        augmented, _steps = augment_mask(mask, label)
        assert augmented.shape == mask.shape
        assert augmented.dtype == np.uint8
        assert augmented.max() == 255
