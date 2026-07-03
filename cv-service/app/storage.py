"""Helpers for the on-disk cache of rendered PNGs served under /cache."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from . import config


def image_dir(image_id: str) -> Path:
    d = config.CACHE_DIR / image_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_rgb_png(image_id: str, filename: str, rgb: np.ndarray) -> str:
    """Save an RGB uint8 array as PNG; return its public /cache-relative URL."""
    path = image_dir(image_id) / filename
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(path), bgr)
    return f"/cache/{image_id}/{filename}"
