"""Test setup: make the ``app`` package importable regardless of CWD, plus
synthetic image fixtures (no binary test assets committed to the repo).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from skimage.color import rgb2lab

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cache import ImageEntry  # noqa: E402


def _solid_blocks_rgb(h: int = 200, w: int = 200) -> np.ndarray:
    """Four clearly separated color blocks — a simple, unambiguous image for
    auto-k / segmentation sanity checks.
    """
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[: h // 2, : w // 2] = (230, 40, 40)     # red
    img[: h // 2, w // 2 :] = (40, 200, 60)     # green
    img[h // 2 :, : w // 2] = (40, 80, 230)     # blue
    img[h // 2 :, w // 2 :] = (230, 210, 40)    # yellow
    return img


def _busy_with_speck_rgb(h: int = 200, w: int = 200) -> np.ndarray:
    """Large background + a tiny colored speck, mimicking a decorative
    element (a star/heart on the real anime test photo) sitting inside a
    big region — the scenario that produced ragged output before this fix.
    """
    img = np.full((h, w, 3), (250, 245, 235), dtype=np.uint8)  # cream background
    img[40:140, 40:140] = (90, 60, 200)   # a large violet block
    img[60:66, 60:66] = (255, 210, 30)    # a 6x6 yellow speck ("star")
    return img


@pytest.fixture
def solid_blocks_entry() -> ImageEntry:
    rgb = _solid_blocks_rgb()
    lab = rgb2lab(rgb.astype(np.float64) / 255.0)
    return ImageEntry(image_id="test-solid-blocks", rgb=rgb, lab=lab)


@pytest.fixture
def busy_with_speck_entry() -> ImageEntry:
    rgb = _busy_with_speck_rgb()
    lab = rgb2lab(rgb.astype(np.float64) / 255.0)
    return ImageEntry(image_id="test-busy-speck", rgb=rgb, lab=lab)


@pytest.fixture
def solid_blocks_rgb() -> np.ndarray:
    return _solid_blocks_rgb()
