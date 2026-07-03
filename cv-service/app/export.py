"""/export pipeline: compose a printable page (line art + numbered legend).

Layout adapts to the image orientation so the artwork uses as much of the sheet
as possible: for landscape images the legend sits in a right-hand column, for
portrait images it sits in a bottom band. The line art is re-rendered at the
target print resolution (not upscaled) for crisp outlines and numbers.
"""

from __future__ import annotations

import io
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import config, render
from .cache import ImageEntry, PaletteEntry

Rect = tuple[int, int, int, int]  # x, y, w, h

# Minimum legend column width (px @300dpi) so Russian names fit without truncation.
LEGEND_MIN_COL_W = 820
LEGEND_MAX_ROW_H = 150


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, max(8, size))
    except OSError:
        return ImageFont.load_default()


def _page_dimensions(page_size: str, landscape: bool) -> tuple[int, int]:
    pw, ph = config.PAGE_SIZES_PX.get(page_size, config.PAGE_SIZES_PX["A4"])
    return (ph, pw) if landscape else (pw, ph)


def _fit_text(font: ImageFont.FreeTypeFont, text: str, max_w: float) -> str:
    if font.getlength(text) <= max_w:
        return text
    while text and font.getlength(text + "…") > max_w:
        text = text[:-1]
    return text + "…"


def compose_export(entry: ImageEntry, page_size: str = "A4") -> bytes:
    seg = entry.segmentation
    if seg is None:
        raise ValueError("image has not been segmented yet")

    src_h, src_w = seg.label_img.shape
    landscape = src_w > src_h
    page_w, page_h = _page_dimensions(page_size, landscape)
    min_dim = min(page_w, page_h)
    margin = round(min_dim * 0.045)
    gap = margin

    page = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(page)

    # Title
    title_size = round(min_dim * 0.028)
    title_font = _load_font(config.FONT_PATH_BOLD, title_size)
    draw.text((margin, margin), "dwhiepaint — раскраска по номерам",
              fill="black", font=title_font)
    title_h = title_size + round(margin * 0.6)

    content_x, content_y = margin, margin + title_h
    content_w = page_w - 2 * margin
    content_h = page_h - content_y - margin

    n = len(seg.palette)
    if landscape:
        legend_w = round(content_w * 0.30)
        art_rect: Rect = (content_x, content_y, content_w - legend_w - gap, content_h)
        legend_rect: Rect = (content_x + content_w - legend_w, content_y, legend_w, content_h)
    else:
        cols = max(1, min(n, content_w // LEGEND_MIN_COL_W))
        rows = math.ceil(n / cols)
        legend_h = min(rows * 130, round(content_h * 0.42))
        art_rect = (content_x, content_y, content_w, content_h - legend_h - gap)
        legend_rect = (content_x, content_y + content_h - legend_h, content_w, legend_h)

    _paste_artwork(page, draw, seg, art_rect)
    _draw_legend(draw, seg.palette, legend_rect)

    buf = io.BytesIO()
    page.save(buf, format="PNG")
    return buf.getvalue()


def _paste_artwork(page: Image.Image, draw: ImageDraw.ImageDraw,
                   seg, rect: Rect) -> None:
    ax, ay, aw, ah = rect
    src_h, src_w = seg.label_img.shape

    scale = min(aw / src_w, ah / src_h)
    tw, th = max(1, round(src_w * scale)), max(1, round(src_h * scale))

    scaled_label = cv2.resize(seg.label_img.astype(np.int32), (tw, th),
                              interpolation=cv2.INTER_NEAREST)
    art = render.line_art(scaled_label, seg.palette, thickness=3, min_label_radius=11)

    ox, oy = ax + (aw - tw) // 2, ay + (ah - th) // 2
    page.paste(Image.fromarray(art), (ox, oy))
    draw.rectangle([ox - 1, oy - 1, ox + tw, oy + th], outline=(210, 210, 210))


def _draw_legend(draw: ImageDraw.ImageDraw, palette: list[PaletteEntry],
                 rect: Rect) -> None:
    lx, ly, lw, lh = rect
    n = len(palette)

    cols = max(1, min(n, int(lw // LEGEND_MIN_COL_W)))
    rows = math.ceil(n / cols)
    row_h = min(lh / rows, LEGEND_MAX_ROW_H)
    col_w = lw / cols

    swatch = max(20, int(min(row_h * 0.55, 60)))
    font = _load_font(config.FONT_PATH, int(swatch * 0.62))
    pad = int(swatch * 0.45)

    for i, c in enumerate(palette):
        col, row = i // rows, i % rows
        x = lx + col * col_w
        y = ly + row * row_h
        sy = y + (row_h - swatch) / 2

        rgb = tuple(int(c.hex[j:j + 2], 16) for j in (1, 3, 5))
        draw.rectangle([x, sy, x + swatch, sy + swatch], fill=rgb, outline="black", width=2)

        # Swatch already conveys the color, so the label is just number + name.
        label = _fit_text(font, f"{c.index}. {c.name_ru}", col_w - swatch - pad * 2)
        draw.text((x + swatch + pad, y + (row_h - font.size) / 2),
                  label, fill="black", font=font)
