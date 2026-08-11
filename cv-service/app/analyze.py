"""/analyze pipeline: decode + resize + Lab conversion + automatic color count."""

from __future__ import annotations

import io
import uuid

import cv2
import numpy as np
from PIL import Image, ImageOps
from skimage.color import rgb2lab
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import silhouette_score

from . import config, segment, storage
from .cache import ImageEntry, cache


def _decode_and_resize(file_bytes: bytes) -> np.ndarray:
    """Decode an uploaded image to an RGB uint8 array with longest side ≤ MAX_SIDE."""
    img = Image.open(io.BytesIO(file_bytes))
    # Image.open only parses the header — no pixels are decoded yet — so the
    # size is known before the memory to hold them is ever allocated. A small
    # compressed file can declare an enormous canvas; refuse it here rather
    # than after paying for it.
    width, height = img.size
    if width * height > config.MAX_INPUT_PIXELS:
        raise ValueError(
            f"image has too many pixels: {width}x{height} exceeds {config.MAX_INPUT_PIXELS}"
        )
    img = ImageOps.exif_transpose(img)  # honor camera orientation
    img = img.convert("RGB")

    w, h = img.size
    longest = max(w, h)
    if longest > config.MAX_SIDE:
        scale = config.MAX_SIDE / longest
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    elif longest < config.UPSCALE_MIN_SIDE:
        # Upscale small inputs so tiny photos still carry paintable detail.
        scale = config.UPSCALE_MIN_SIDE / longest
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)

    rgb = np.asarray(img, dtype=np.uint8)
    # Edge-preserving smoothing: cuts JPEG compression speckle before color
    # quantization, so clustering doesn't fragment on noise that isn't really
    # part of the artwork (real thin decorative elements survive; noise doesn't).
    return cv2.bilateralFilter(
        rgb, config.DENOISE_D, config.DENOISE_SIGMA_COLOR, config.DENOISE_SIGMA_SPACE,
    )


def _downsample_lab(lab: np.ndarray, max_side: int) -> np.ndarray:
    """Spatially shrink a Lab image for the (expensive) auto-k search only.

    Used only within this module's candidate search — never fed back into
    the cached full-resolution entry.
    """
    h, w = lab.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return lab.astype(np.float32)
    scale = max_side / longest
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    return cv2.resize(lab.astype(np.float32), (new_w, new_h), interpolation=cv2.INTER_AREA)


def _score_candidate(working_lab: np.ndarray, k: int) -> float | None:
    """Composite score for one candidate k: color separation + how cleanly it
    segments in practice (few post-merge regions, no single dominating blob).

    Runs the same cluster → regions → merge path as a real ``/segment`` call,
    on the small working copy, so k is picked by how the image actually
    paints out rather than by color-cluster separation alone.
    """
    h, w = working_lab.shape[:2]
    pixels = working_lab.reshape(-1, 3)

    km = MiniBatchKMeans(n_clusters=k, random_state=42, n_init=3, batch_size=2048)
    labels_flat = km.fit_predict(pixels)
    if len(np.unique(labels_flat)) < 2:
        return None

    rng = np.random.default_rng(42)
    sil_idx = rng.choice(
        pixels.shape[0], size=min(pixels.shape[0], config.AUTO_K_SIL_SAMPLE), replace=False,
    )
    try:
        silhouette = silhouette_score(pixels[sil_idx], labels_flat[sil_idx])
    except ValueError:
        return None

    labels = labels_flat.astype(np.int32).reshape(h, w)
    region_id, region_cluster, areas = segment.connected_regions(labels, k)
    min_area = max(16, int(config.MIN_REGION_AREA_FRAC * h * w))
    cleaned = segment.merge_small_regions(
        region_id, region_cluster, areas, min_area, cluster_lab=km.cluster_centers_,
    )
    _, _, final_areas = segment.connected_regions(cleaned, k)
    region_count = len(final_areas)
    dominant_frac = float(final_areas.max()) / (h * w) if region_count else 1.0

    frag_penalty = max(0.0, region_count - config.AUTO_K_TARGET_REGIONS) / config.AUTO_K_TARGET_REGIONS
    dom_penalty = (
        max(0.0, dominant_frac - config.AUTO_K_DOMINANCE_THRESHOLD)
        / (1 - config.AUTO_K_DOMINANCE_THRESHOLD)
    )
    # Reward approaching the target region count so detail-rich images earn more
    # colors; capped at 1 so it can't outweigh separation without bound.
    detail_reward = min(1.0, region_count / config.AUTO_K_TARGET_REGIONS)

    return (
        config.AUTO_K_W_SILHOUETTE * silhouette
        - config.AUTO_K_W_FRAGMENTATION * frag_penalty
        - config.AUTO_K_W_DOMINANCE * dom_penalty
        + config.AUTO_K_W_DETAIL * detail_reward
    )


def _auto_k(lab: np.ndarray) -> int:
    """Pick the candidate k whose actual mini-segmentation scores best.

    More expensive than a pure color-silhouette scan (clusters + extracts
    regions + merges small ones for every candidate), but the result tracks
    what the user will actually see printed, not just cluster separability.
    """
    working_lab = _downsample_lab(lab, config.AUTO_K_WORKING_MAX_SIDE)
    total_px = working_lab.shape[0] * working_lab.shape[1]

    best_k, best_score = config.AUTO_K_CANDIDATES[0], float("-inf")
    for k in config.AUTO_K_CANDIDATES:
        if k >= total_px:
            continue
        score = _score_candidate(working_lab, k)
        if score is not None and score > best_score:
            best_k, best_score = k, score

    return int(np.clip(best_k, config.MIN_K, config.MAX_K))


def analyze(file_bytes: bytes) -> dict:
    """Run preprocessing + auto-k, cache the entry, and render a preview.

    Returns {image_id, predicted_k, preview_url, width, height}.
    """
    rgb = _decode_and_resize(file_bytes)
    lab = rgb2lab(rgb.astype(np.float64) / 255.0)

    predicted_k = _auto_k(lab)

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
