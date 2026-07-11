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
    # Detail-importance map from segment() (None when SUBJECT_AWARE is off).
    # Persisted here (not just a local var in segment()) so a later re-export
    # (export.py) reuses the same per-contour epsilon without re-running
    # rembg/face detection.
    importance_map: np.ndarray | None = None


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

    try:
        img_dir = storage.image_dir(image_id)
    except ValueError:
        # Malformed/hostile image_id (see storage.image_dir) — treat exactly
        # like "not found" rather than letting it bubble into a 500.
        return None
    path = img_dir / "preview.png"
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


def save_segmentation(image_id: str, seg: Segmentation) -> None:
    """Persist enough of a Segmentation to reconstruct it in a DIFFERENT
    process. The async worker computes segmentation in a separate
    process/container from the cv-service API (they share only CACHE_DIR and
    Redis, never in-memory state — see project docs on the shared cv/worker
    image), so without this, /export — handled by the API container, which
    never ran segment() itself — always finds ``entry.segmentation is None``
    and 409s even though segmentation genuinely completed. Called once, right
    after segment() finishes; overwritten on every re-segmentation, same as
    the rendered PNG/SVG artifacts.

    label_img is cast to uint8 before saving: MAX_K caps the palette at 32
    colors, so every index fits, and it quarters the file size vs. its
    in-memory int32 dtype.
    """
    from . import storage  # local import: storage has no reverse dep on cache

    storage.save_array(image_id, "label.npy", seg.label_img.astype(np.uint8))
    if seg.importance_map is not None:
        storage.save_array(image_id, "importance.npy", seg.importance_map)
    storage.save_json(image_id, "segmentation.json", {
        "k": seg.k,
        "palette": [
            {"index": p.index, "hex": p.hex, "lab": list(p.lab),
             "name_ru": p.name_ru, "name_en": p.name_en}
            for p in seg.palette
        ],
        "region_map_url": seg.region_map_url,
        "painted_preview_url": seg.painted_preview_url,
        "svg_url": seg.svg_url,
    })


def ensure_segmentation(entry: ImageEntry) -> Segmentation | None:
    """Reconstruct entry.segmentation from disk if this process's copy of the
    entry never had segment() run on it directly (see save_segmentation).
    Returns None (image was never segmented, or the cache dir was pruned)
    without raising — callers decide how to react (e.g. a 409).
    """
    if entry.segmentation is not None:
        return entry.segmentation

    from . import storage  # local import: storage has no reverse dep on cache

    meta = storage.load_json(entry.image_id, "segmentation.json")
    label_img = storage.load_array(entry.image_id, "label.npy")
    if meta is None or label_img is None:
        return None

    importance_map = storage.load_array(entry.image_id, "importance.npy")
    palette = [
        PaletteEntry(
            index=p["index"], hex=p["hex"], lab=tuple(p["lab"]),
            name_ru=p["name_ru"], name_en=p.get("name_en"),
        )
        for p in meta["palette"]
    ]
    seg = Segmentation(
        k=meta["k"],
        label_img=label_img.astype(np.int32),
        palette=palette,
        region_map_url=meta.get("region_map_url"),
        painted_preview_url=meta.get("painted_preview_url"),
        svg_url=meta.get("svg_url"),
        importance_map=importance_map,
    )
    entry.segmentation = seg
    return seg
