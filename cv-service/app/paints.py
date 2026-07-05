"""Map palette colours to a real acrylic paint set (Phase 10).

For each segmented colour we find the perceptually nearest paint (CIEDE2000) from
a curated set, and — when nothing is close enough to use straight from the tube —
suggest the two paints whose 50/50 mix lands closest. This is what turns a screen
palette into something a person can actually buy and paint with.
"""

from __future__ import annotations

import functools
import json

import numpy as np
from skimage.color import deltaE_ciede2000, rgb2lab

from . import config

# Above this CIEDE2000 distance the nearest single paint isn't a faithful match,
# so we also offer a two-paint mixing suggestion.
DIRECT_MATCH_THRESHOLD = 6.0


def _hex_to_lab(hex_str: str) -> np.ndarray:
    rgb = np.array([int(hex_str[i : i + 2], 16) for i in (1, 3, 5)], dtype=np.float64) / 255.0
    return rgb2lab(rgb.reshape(1, 1, 3)).reshape(3)


@functools.lru_cache(maxsize=1)
def _load() -> tuple[list[dict], np.ndarray, str]:
    data = json.loads((config.DATA_DIR / "paints_acrylic.json").read_text(encoding="utf-8"))
    paints = data["paints"]
    labs = np.array([_hex_to_lab(p["hex"]) for p in paints])
    return paints, labs, data.get("set", "")


def set_name() -> str:
    return _load()[2]


def _distances(lab: tuple[float, float, float], labs: np.ndarray) -> np.ndarray:
    target = np.repeat(np.asarray(lab, dtype=np.float64).reshape(1, 3), len(labs), axis=0)
    return deltaE_ciede2000(target, labs)


def nearest(lab: tuple[float, float, float]) -> tuple[dict, float]:
    """Return (paint, CIEDE2000 distance) of the closest single paint."""
    paints, labs, _ = _load()
    d = _distances(lab, labs)
    i = int(np.argmin(d))
    return paints[i], float(d[i])


def mixing_suggestion(lab: tuple[float, float, float]) -> dict | None:
    """Best 50/50 two-paint mix for a colour with no close single match."""
    paints, labs, _ = _load()
    target = np.asarray(lab, dtype=np.float64).reshape(1, 3)
    best: tuple[float, int, int] | None = None
    n = len(paints)
    for i in range(n):
        for j in range(i + 1, n):
            mix = ((labs[i] + labs[j]) / 2.0).reshape(1, 3)
            dd = float(deltaE_ciede2000(target, mix)[0])
            if best is None or dd < best[0]:
                best = (dd, i, j)
    if best is None:
        return None
    dd, i, j = best
    return {"delta_e": round(dd, 1), "paints": [paints[i]["name_ru"], paints[j]["name_ru"]]}


def describe(lab: tuple[float, float, float]) -> dict:
    """Nearest paint (+ a mixing hint when the direct match is poor)."""
    paint, de = nearest(lab)
    out: dict = {"paint_name": paint["name_ru"], "paint_hex": paint["hex"], "delta_e": round(de, 1)}
    if de > DIRECT_MATCH_THRESHOLD:
        mix = mixing_suggestion(lab)
        if mix and mix["delta_e"] < de:
            out["mix"] = mix["paints"]
    return out
