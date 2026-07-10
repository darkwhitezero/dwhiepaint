"""Helpers for the on-disk cache of rendered PNGs served under /cache."""

from __future__ import annotations

import json
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


def save_text(image_id: str, filename: str, text: str) -> str:
    """Save a text artifact (e.g. an SVG); return its /cache-relative URL."""
    path = image_dir(image_id) / filename
    path.write_text(text, encoding="utf-8")
    return f"/cache/{image_id}/{filename}"


def save_array(image_id: str, filename: str, arr: np.ndarray) -> None:
    """Save a raw numpy array (not a rendered PNG) to the cache dir — used to
    persist internal state (e.g. the label map) that a different process needs
    to reconstruct later, not to serve publicly.
    """
    np.save(image_dir(image_id) / filename, arr)


def load_array(image_id: str, filename: str) -> np.ndarray | None:
    path = image_dir(image_id) / filename
    return np.load(path) if path.exists() else None


def save_json(image_id: str, filename: str, data: dict) -> None:
    (image_dir(image_id) / filename).write_text(json.dumps(data), encoding="utf-8")


def load_json(image_id: str, filename: str) -> dict | None:
    path = image_dir(image_id) / filename
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
