"""Map a Lab color to a Russian (primary) / English (secondary) name.

Strategy (per the plan):
  1. Nearest entry in the curated dictionary (colors.json) by CIEDE2000.
     If the distance is below a threshold, use that human name.
  2. Otherwise fall back to a procedural name: a hue bucket plus a
     lightness/saturation modifier.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
from skimage.color import deltaE_ciede2000, rgb2lab

from . import config

# --- Procedural naming vocabulary (Russian) -------------------------------

# 12 base hue buckets, centered every 30 degrees on the HSV hue wheel.
_HUE_NAMES_RU = [
    "красный",       # 0
    "оранжевый",     # 30
    "жёлтый",        # 60
    "жёлто-зелёный", # 90
    "зелёный",       # 120
    "изумрудный",    # 150
    "голубой",       # 180
    "лазурный",      # 210
    "синий",         # 240
    "фиолетовый",    # 270
    "пурпурный",     # 300
    "розовый",       # 330
]
_HUE_NAMES_EN = [
    "red", "orange", "yellow", "yellow-green", "green", "emerald",
    "cyan", "azure", "blue", "violet", "purple", "pink",
]


@lru_cache(maxsize=1)
def _dictionary() -> tuple[np.ndarray, list[str], list[str | None]]:
    """Load colors.json → (lab array [M,3], names_ru [M], names_en [M])."""
    with open(config.COLOR_DICTIONARY_PATH, encoding="utf-8") as f:
        rows = json.load(f)

    rgb = np.array([[r["R"], r["G"], r["B"]] for r in rows], dtype=np.float64) / 255.0
    lab = rgb2lab(rgb.reshape(-1, 1, 3)).reshape(-1, 3)
    names_ru = [r["Name"] for r in rows]
    names_en = [r.get("NameEn") for r in rows]
    return lab, names_ru, names_en


def _procedural_name(lab: np.ndarray) -> tuple[str, str | None]:
    """Build a name from lightness/chroma/hue when no dictionary match fits."""
    L, a, b = float(lab[0]), float(lab[1]), float(lab[2])
    chroma = float(np.hypot(a, b))

    # Achromatic: decide by lightness only.
    if chroma < 8:
        if L < 15:
            return "чёрный", "black"
        if L < 35:
            return "тёмно-серый", "dark gray"
        if L < 65:
            return "серый", "gray"
        if L < 85:
            return "светло-серый", "light gray"
        return "белый", "white"

    hue = float(np.degrees(np.arctan2(b, a))) % 360.0
    bucket = int((hue + 15) // 30) % 12
    base_ru = _HUE_NAMES_RU[bucket]
    base_en = _HUE_NAMES_EN[bucket]

    if L < 30:
        return f"тёмный {base_ru}", f"dark {base_en}"
    if L > 80:
        return f"пастельный {base_ru}", f"pale {base_en}"
    if chroma < 20:
        return f"блёклый {base_ru}", f"muted {base_en}"
    if chroma > 55:
        return f"насыщенный {base_ru}", f"vivid {base_en}"
    return base_ru, base_en


def name_for_lab(lab: tuple[float, float, float] | np.ndarray) -> tuple[str, str | None]:
    """Return (name_ru, name_en) for a Lab color."""
    lab_arr = np.asarray(lab, dtype=np.float64).reshape(3)
    dict_lab, names_ru, names_en = _dictionary()

    query = np.broadcast_to(lab_arr, dict_lab.shape)
    deltas = deltaE_ciede2000(query, dict_lab)
    idx = int(np.argmin(deltas))

    if deltas[idx] <= config.DELTA_E_MATCH_THRESHOLD:
        return names_ru[idx], names_en[idx]
    return _procedural_name(lab_arr)
