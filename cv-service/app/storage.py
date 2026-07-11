"""Helpers for the on-disk cache of rendered PNGs served under /cache."""

from __future__ import annotations

import json
import re
from pathlib import Path

import cv2
import numpy as np

from . import config

# image_id is always a server-minted uuid4 in production (see analyze.analyze),
# but it round-trips through client requests on /segment, /export and /jobs
# unvalidated — CodeQL (py/path-injection) correctly flags every image_dir()
# call as a sink for a client-controlled path component. Enforce the true
# shape at the one choke point instead of trusting callers.
#
# The allowlist is alnum + "-"/"_" rather than uuid4's hex-only alphabet: test
# fixtures across the suite use short human-readable ids (e.g. "phase6",
# "test-busy-speck") passed straight to ImageEntry/storage without going
# through analyze(), and those are legitimate, not attacker input. What
# matters for the CodeQL sink is that NO path-manipulation character can slip
# through — no ".", "/", "\" — which this allowlist guarantees regardless of
# how "id-like" the value looks; the containment check below is then a
# belt-and-suspenders sanitizer CodeQL's taint tracking recognizes on top.
_IMAGE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def image_dir(image_id: str) -> Path:
    if not _IMAGE_ID_RE.fullmatch(image_id):
        raise ValueError(f"invalid image_id: {image_id!r}")
    root = config.CACHE_DIR.resolve()
    d = (root / image_id).resolve()
    if not d.is_relative_to(root):
        raise ValueError(f"invalid image_id: {image_id!r}")
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
