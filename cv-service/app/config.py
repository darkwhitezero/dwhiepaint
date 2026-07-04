import os
from pathlib import Path

# Directory layout
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR.parent / "data"
CACHE_DIR = Path(os.getenv("CACHE_DIR", "/tmp/dwhiepaint-cache"))

# Redis (async job queue, Phase 6). The cv-service API enqueues jobs and reads
# per-stage progress from here; the ARQ worker runs the heavy pipeline. Ephemeral
# — only job progress/results live here, never user data (that's Postgres).
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
JOB_RESULT_TTL_SECONDS = int(os.getenv("JOB_RESULT_TTL_SECONDS", "3600"))

# Pipeline parameters
MAX_SIDE = int(os.getenv("MAX_SIDE", "2000"))          # longest image side after resize
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "1800"))
MIN_REGION_AREA_FRAC = float(os.getenv("MIN_REGION_AREA_FRAC", "0.003"))  # 0.3% of image
DELTA_E_MATCH_THRESHOLD = float(os.getenv("DELTA_E_MATCH_THRESHOLD", "10"))
MIN_K = int(os.getenv("MIN_K", "4"))
MAX_K = int(os.getenv("MAX_K", "32"))

# Bilateral pre-smoothing (edge-preserving) applied to the source photo before
# Lab conversion, to cut JPEG speckle noise that would otherwise fragment into
# spurious tiny color clusters.
DENOISE_D = int(os.getenv("DENOISE_D", "5"))
DENOISE_SIGMA_COLOR = float(os.getenv("DENOISE_SIGMA_COLOR", "40"))
DENOISE_SIGMA_SPACE = float(os.getenv("DENOISE_SIGMA_SPACE", "40"))

# --- automatic color-count selection (auto-k) -------------------------------
# v2 runs a real mini-segmentation (cluster + regions + merge) per candidate
# on a downsampled working copy, so the search cost stays bounded even with a
# denser candidate grid than the old color-only silhouette pass.
AUTO_K_WORKING_MAX_SIDE = int(os.getenv("AUTO_K_WORKING_MAX_SIDE", "480"))
AUTO_K_CANDIDATES = list(range(6, 31, 2))               # 13 candidates vs. the old 5
AUTO_K_SIL_SAMPLE = int(os.getenv("AUTO_K_SIL_SAMPLE", "3000"))
# Composite score weights: silhouette (color separation) vs. fragmentation
# penalty (too many post-merge regions) vs. dominance penalty (one region
# swallowing most of the image = under-segmentation).
AUTO_K_W_SILHOUETTE = float(os.getenv("AUTO_K_W_SILHOUETTE", "1.0"))
AUTO_K_W_FRAGMENTATION = float(os.getenv("AUTO_K_W_FRAGMENTATION", "0.6"))
AUTO_K_W_DOMINANCE = float(os.getenv("AUTO_K_W_DOMINANCE", "0.6"))
AUTO_K_TARGET_REGIONS = int(os.getenv("AUTO_K_TARGET_REGIONS", "40"))  # comfortable paintable-region count
AUTO_K_DOMINANCE_THRESHOLD = float(os.getenv("AUTO_K_DOMINANCE_THRESHOLD", "0.6"))  # top region area fraction

# --- edge-aware superpixel segmentation (Phase 5) ---------------------------
# SLIC oversegmentation replaces per-pixel k-means as the spatial primitive, so
# region boundaries follow real image edges instead of color-only clusters. The
# palette is then k-means over the area-weighted mean-Lab of superpixels, which
# is far more stable and boundary-respecting than clustering raw pixels.
# Low compactness lets superpixels bend to real edges (high compactness makes
# square blocks whose seams show up as staircased region outlines); density is
# high so the grain is fine enough that merged regions hug edges smoothly.
SLIC_COMPACTNESS = float(os.getenv("SLIC_COMPACTNESS", "6.0"))
SLIC_SIGMA = float(os.getenv("SLIC_SIGMA", "1.0"))

# Morphological open/close on the label map before region extraction, to shed
# single-pixel ragged edges left by quantization (kernel in px at working res).
MORPH_KERNEL = int(os.getenv("MORPH_KERNEL", "3"))

# Detail presets tune (superpixel density, palette-size bias, min paintable
# region size) together. The client sends a preset name; "standard" is default.
# k_bias shifts predicted_k so "detailed" gets more colors, "beginner" fewer.
DETAIL_PRESETS = {
    "beginner": {"slic_n_segments": 2000, "min_region_area_frac": 0.010, "k_bias": -4},
    "standard": {"slic_n_segments": 4500, "min_region_area_frac": 0.003, "k_bias": 0},
    "detailed": {"slic_n_segments": 9000, "min_region_area_frac": 0.0012, "k_bias": 4},
}
DEFAULT_DETAIL = os.getenv("DEFAULT_DETAIL", "standard")


def detail_preset(name: str | None) -> dict:
    """Return the tunable bundle for a detail preset, falling back to default."""
    return DETAIL_PRESETS.get(name or DEFAULT_DETAIL, DETAIL_PRESETS["standard"])


# Contour simplification: approxPolyDP epsilon as a fraction of each region's
# perimeter, smoothing pixel-level jaggies from JPEG noise while preserving
# real corners. Capped by an ABSOLUTE pixel value too: on a thin, elongated
# region (e.g. a hair strand), perimeter is large relative to width, so the
# relative term alone can grow past the region's own width and make
# approxPolyDP collapse the two sides into a self-intersecting polygon. The
# absolute cap keeps epsilon small enough to only ever remove few-pixel noise.
# Smoothing is done on the LABEL MAP (see LABEL_SMOOTH_SIGMA), not per-contour:
# a shared boundary must move identically for both neighbors, else independent
# per-region smoothing splits it into two parallel lines. So contour extraction
# only lightly simplifies (drop sub-epsilon noise) and Chaikin defaults to off.
CONTOUR_SIMPLIFY_EPS = float(os.getenv("CONTOUR_SIMPLIFY_EPS", "0.0015"))
CONTOUR_SIMPLIFY_MAX_PX = float(os.getenv("CONTOUR_SIMPLIFY_MAX_PX", "1.5"))
CONTOUR_SMOOTH_ITERS = int(os.getenv("CONTOUR_SMOOTH_ITERS", "0"))

# Gaussian-argmax smoothing of the final label map: blur each color's
# membership and re-assign each pixel to the strongest nearby color. This
# rounds superpixel-seam staircases while keeping labels discrete AND shared
# boundaries consistent (one boundary, not two). Sigma in px at working res.
LABEL_SMOOTH_SIGMA = float(os.getenv("LABEL_SMOOTH_SIGMA", "2.5"))

COLOR_DICTIONARY_PATH = DATA_DIR / "colors.json"

# Font with Cyrillic glyphs for the legend (installed via apt in the Dockerfile).
FONT_PATH = os.getenv(
    "FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
)
FONT_PATH_BOLD = os.getenv(
    "FONT_PATH_BOLD", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
)

# Printable page sizes in pixels at 600 dpi (portrait).
PAGE_SIZES_PX = {
    "A4": (4960, 7016),
    "A3": (7016, 9922),
}

CACHE_DIR.mkdir(parents=True, exist_ok=True)
