"""/analyze pipeline: decode + resize + Lab conversion + automatic color count."""

from __future__ import annotations

import io
import uuid

import numpy as np
from PIL import Image, ImageOps
from skimage.color import rgb2lab
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import silhouette_score

from . import config, storage
from .cache import ImageEntry, cache


def _decode_and_resize(file_bytes: bytes) -> np.ndarray:
    """Decode an uploaded image to an RGB uint8 array with longest side ≤ MAX_SIDE."""
    img = Image.open(io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img)  # honor camera orientation
    img = img.convert("RGB")

    w, h = img.size
    longest = max(w, h)
    if longest > config.MAX_SIDE:
        scale = config.MAX_SIDE / longest
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)

    return np.asarray(img, dtype=np.uint8)


def _auto_k(lab_pixels: np.ndarray) -> int:
    """Pick the candidate k with the best silhouette score on a pixel sample."""
    rng = np.random.default_rng(42)

    n = lab_pixels.shape[0]
    fit_idx = rng.choice(n, size=min(n, 20000), replace=False)
    fit_sample = lab_pixels[fit_idx]

    # Silhouette is O(m^2); score on a smaller subsample.
    sil_idx = rng.choice(fit_sample.shape[0], size=min(fit_sample.shape[0], 2000), replace=False)
    sil_sample = fit_sample[sil_idx]

    best_k, best_score = config.CANDIDATE_KS[0], -1.0
    for k in config.CANDIDATE_KS:
        if k >= sil_sample.shape[0]:
            continue
        km = MiniBatchKMeans(n_clusters=k, random_state=42, n_init=3, batch_size=2048)
        km.fit(fit_sample)
        labels = km.predict(sil_sample)
        if len(np.unique(labels)) < 2:
            continue
        try:
            score = silhouette_score(sil_sample, labels)
        except ValueError:
            continue
        if score > best_score:
            best_k, best_score = k, score

    return best_k


def analyze(file_bytes: bytes) -> dict:
    """Run preprocessing + auto-k, cache the entry, and render a preview.

    Returns {image_id, predicted_k, preview_url, width, height}.
    """
    rgb = _decode_and_resize(file_bytes)
    lab = rgb2lab(rgb.astype(np.float64) / 255.0)
    lab_pixels = lab.reshape(-1, 3)

    predicted_k = _auto_k(lab_pixels)

    image_id = str(uuid.uuid4())
    entry = ImageEntry(image_id=image_id, rgb=rgb, lab=lab)
    cache.put(entry)

    preview_url = storage.save_rgb_png(image_id, "preview.png", rgb)
    return {
        "image_id": image_id,
        "predicted_k": predicted_k,
        "preview_url": preview_url,
        "width": entry.width,
        "height": entry.height,
    }
