"""/export pipeline: compose a printable page (line art + numbered legend)."""

from __future__ import annotations

import io
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import config, render
from .cache import ImageEntry


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _page_dimensions(page_size: str, landscape: bool) -> tuple[int, int]:
    pw, ph = config.PAGE_SIZES_PX.get(page_size, config.PAGE_SIZES_PX["A4"])
    return (ph, pw) if landscape else (pw, ph)


def compose_export(entry: ImageEntry, page_size: str = "A4") -> bytes:
    seg = entry.segmentation
    if seg is None:
        raise ValueError("image has not been segmented yet")

    src_h, src_w = seg.label_img.shape
    landscape = src_w > src_h
    page_w, page_h = _page_dimensions(page_size, landscape)

    margin = round(page_w * 0.05)
    content_w = page_w - 2 * margin

    # --- legend geometry -------------------------------------------------
    n = len(seg.palette)
    cols = 2 if n <= 16 else 3
    rows = math.ceil(n / cols)
    swatch = round(page_w * 0.028)
    row_h = round(swatch * 1.5)
    legend_font = _load_font(config.FONT_PATH, round(swatch * 0.62))
    title_font = _load_font(config.FONT_PATH_BOLD, round(page_w * 0.028))

    title_h = round(page_w * 0.05)
    legend_h = rows * row_h
    art_h = page_h - 2 * margin - title_h - legend_h - margin

    # --- artwork rendered at print resolution ---------------------------
    scale = min(content_w / src_w, art_h / src_h)
    tw, th = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    scaled_label = cv2.resize(
        seg.label_img.astype(np.int32), (tw, th), interpolation=cv2.INTER_NEAREST
    )
    art = render.line_art(
        scaled_label, seg.palette, thickness=2, min_label_radius=10
    )

    # --- compose page ----------------------------------------------------
    page = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(page)

    draw.text((margin, round(margin * 0.4)), "dwhiepaint — раскраска по номерам",
              fill="black", font=title_font)

    art_img = Image.fromarray(art)
    art_x = (page_w - tw) // 2
    art_y = margin + title_h
    page.paste(art_img, (art_x, art_y))

    legend_top = art_y + art_h + margin
    col_w = content_w // cols
    for i, c in enumerate(seg.palette):
        col = i // rows
        row = i % rows
        x = margin + col * col_w
        y = legend_top + row * row_h

        rgb = tuple(int(c.hex[j:j + 2], 16) for j in (1, 3, 5))
        draw.rectangle([x, y, x + swatch, y + swatch], fill=rgb, outline="black", width=2)

        text = f"{c.index}. {c.name_ru}  {c.hex}"
        draw.text((x + swatch + round(swatch * 0.4), y + swatch * 0.15),
                  text, fill="black", font=legend_font)

    buf = io.BytesIO()
    page.save(buf, format="PNG")
    return buf.getvalue()
