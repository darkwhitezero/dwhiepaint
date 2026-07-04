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

import cv2
import numpy as np
from skimage.color import rgb2lab

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
    # Cache-relative URLs of the rendered artifacts (set by segment()).
    region_map_url: str | None = None
    painted_preview_url: str | None = None
    svg_url: str | None = None


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


def load_entry(image_id: str) -> ImageEntry | None:
    """Return the cached entry, reconstructing it from disk on a miss.

    ``analyze`` persists the resized, denoised working image as ``preview.png``
    in the shared cache dir; the Lab array is cheap to recompute from it. This
    lets a *separate* worker process — which does not share this module's
    in-memory dict — run segmentation, and lets the sync path survive a service
    restart or TTL eviction instead of returning 404. The reconstruct is
    byte-exact w.r.t. the analyzed pixels (PNG is lossless), so results match.
    """
    hit = cache.get(image_id)
    if hit is not None:
        return hit

    from . import storage  # local import: storage has no reverse dep on cache

    path = storage.image_dir(image_id) / "preview.png"
    if not path.exists():
        return None
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        return None
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    lab = rgb2lab(rgb.astype(np.float64) / 255.0)
    entry = ImageEntry(image_id=image_id, rgb=rgb, lab=lab)
    cache.put(entry)
    return entry
