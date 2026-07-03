"""In-memory, TTL-bounded cache of per-image processing state.

The CV service is stateless w.r.t. user/account data. It only keeps ephemeral
intermediate state (resized pixels in Lab space + last segmentation) keyed by
``image_id`` so that re-segmenting on a new ``k`` or exporting does not require
re-uploading the image. Redis is a documented upgrade path; a process-local
dict is enough for the MVP.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import numpy as np

from . import config


@dataclass
class PaletteEntry:
    index: int          # 1-based color number shown to the user
    hex: str
    lab: tuple[float, float, float]
    name_ru: str
    name_en: str | None = None


@dataclass
class Segmentation:
    k: int
    # HxW cluster index per pixel, already cleaned (small regions merged).
    label_img: np.ndarray
    palette: list[PaletteEntry]


@dataclass
class ImageEntry:
    image_id: str
    rgb: np.ndarray          # HxWx3 uint8, resized to MAX_SIDE
    lab: np.ndarray          # HxWx3 float64 (Lab)
    created_at: float = field(default_factory=time.time)
    segmentation: Segmentation | None = None

    @property
    def height(self) -> int:
        return self.rgb.shape[0]

    @property
    def width(self) -> int:
        return self.rgb.shape[1]


class ImageCache:
    def __init__(self, ttl_seconds: int | None = None):
        self._ttl = ttl_seconds if ttl_seconds is not None else config.CACHE_TTL_SECONDS
        self._store: dict[str, ImageEntry] = {}
        self._lock = threading.Lock()

    def _prune_locked(self) -> None:
        cutoff = time.time() - self._ttl
        stale = [k for k, v in self._store.items() if v.created_at < cutoff]
        for k in stale:
            del self._store[k]

    def put(self, entry: ImageEntry) -> None:
        with self._lock:
            self._prune_locked()
            self._store[entry.image_id] = entry

    def get(self, image_id: str) -> ImageEntry | None:
        with self._lock:
            self._prune_locked()
            return self._store.get(image_id)


cache = ImageCache()
