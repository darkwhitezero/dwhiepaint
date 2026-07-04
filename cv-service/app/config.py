import os
from pathlib import Path

# Directory layout
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR.parent / "data"
CACHE_DIR = Path(os.getenv("CACHE_DIR", "/tmp/dwhiepaint-cache"))

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

# Contour simplification: approxPolyDP epsilon as a fraction of each region's
# perimeter, smoothing pixel-level jaggies from JPEG noise while preserving
# real corners. Capped by an ABSOLUTE pixel value too: on a thin, elongated
# region (e.g. a hair strand), perimeter is large relative to width, so the
# relative term alone can grow past the region's own width and make
# approxPolyDP collapse the two sides into a self-intersecting polygon. The
# absolute cap keeps epsilon small enough to only ever remove few-pixel noise.
CONTOUR_SIMPLIFY_EPS = float(os.getenv("CONTOUR_SIMPLIFY_EPS", "0.0015"))
CONTOUR_SIMPLIFY_MAX_PX = float(os.getenv("CONTOUR_SIMPLIFY_MAX_PX", "1.5"))

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
