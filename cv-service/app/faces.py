"""Frontal-face detection via OpenCV's bundled Haar cascade. Phase 7.

Only used to boost the detail budget on faces (eyes, mouth), so occasional
misses degrade gracefully — a missed face just isn't given extra detail. No
model download: the cascade ships inside opencv. The classifier is loaded once.
"""

from __future__ import annotations

import cv2
import numpy as np

_cascade: cv2.CascadeClassifier | None = None


def _get_cascade() -> cv2.CascadeClassifier:
    global _cascade
    if _cascade is None:
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _cascade = cv2.CascadeClassifier(path)
    return _cascade


def face_boxes(rgb: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Return (x, y, w, h) face rectangles; empty list on none/failure."""
    try:
        cascade = _get_cascade()
        if cascade.empty():
            return []
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape[:2]
        min_size = max(24, int(min(h, w) * 0.06))
        found = cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(min_size, min_size)
        )
        return [tuple(int(v) for v in box) for box in found]
    except Exception:  # noqa: BLE001 — face boost is optional
        return []
