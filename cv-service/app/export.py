"""/export pipeline: compose printable page(s) as a PDF.

Page 1 is the clean coloring sheet (line art + numbers only). Page 2 is an
optional legend sheet: the mapping from each number to the closest named color
(swatch + Russian name + hex). Line art is re-rendered at the target print
resolution for crisp outlines and numbers.
"""

from __future__ import annotations

import io
import math

import cairosvg
from PIL import Image, ImageDraw, ImageFont

from . import config, vectorize
from .cache import ImageEntry, PaletteEntry

Rect = tuple[int, int, int, int]  # x, y, w, h

DPI = 600
# The px constants below were tuned at 300 dpi; scale them so physical sizes
# (line thickness, legend columns, swatches) stay constant as DPI changes.
_SCALE = DPI / 300

# Minimum legend column width so long Russian names fit without truncation.
LEGEND_MIN_COL_W = round(1000 * _SCALE)
LEGEND_MAX_ROW_H = round(150 * _SCALE)


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


def compose_export(entry: ImageEntry, page_size: str = "A4",
                   include_legend: bool = True) -> bytes:
    """Return a PDF: coloring sheet, plus an optional legend sheet."""
    seg = entry.segmentation
    if seg is None:
        raise ValueError("image has not been segmented yet")

    src_h, src_w = seg.label_img.shape
    landscape = src_w > src_h
    page_w, page_h = _page_dimensions(page_size, landscape)

    pages = [_coloring_page(seg, page_w, page_h)]
    if include_legend:
        pages.append(_legend_page(seg.palette, page_w, page_h))

    buf = io.BytesIO()
    pages[0].save(
        buf, format="PDF", resolution=float(DPI),
        save_all=True, append_images=pages[1:],
    )
    return buf.getvalue()


def compose_png(entry: ImageEntry, page_size: str = "A4") -> bytes:
    """Return a PNG of just the coloring sheet at the target print resolution.

    PNG is meant for on-screen use / sharing, so it carries only the coloring
    page; the legend stays a print-oriented (PDF) concept.
    """
    seg = entry.segmentation
    if seg is None:
        raise ValueError("image has not been segmented yet")

    src_h, src_w = seg.label_img.shape
    landscape = src_w > src_h
    page_w, page_h = _page_dimensions(page_size, landscape)

    page = _coloring_page(seg, page_w, page_h)
    buf = io.BytesIO()
    page.save(buf, format="PNG", dpi=(DPI, DPI))
    return buf.getvalue()


def _coloring_page(seg, page_w: int, page_h: int) -> Image.Image:
    min_dim = min(page_w, page_h)
    margin = round(min_dim * 0.04)

    page = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(page)

    title_size = round(min_dim * 0.022)
    title_font = _load_font(config.FONT_PATH, title_size)
    draw.text((margin, round(margin * 0.5)), "dwhiepaint — раскраска по номерам",
              fill=(120, 120, 120), font=title_font)

    top = margin + title_size + round(margin * 0.4)
    art_rect: Rect = (margin, top, page_w - 2 * margin, page_h - top - margin)
    _paste_artwork(page, draw, seg, art_rect)
    return page


def _legend_page(palette: list[PaletteEntry], page_w: int, page_h: int) -> Image.Image:
    min_dim = min(page_w, page_h)
    margin = round(min_dim * 0.045)

    page = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(page)

    title_font = _load_font(config.FONT_PATH_BOLD, round(min_dim * 0.028))
    sub_font = _load_font(config.FONT_PATH, round(min_dim * 0.017))
    draw.text((margin, margin), "Цвета", fill="black", font=title_font)
    sub_y = margin + round(min_dim * 0.028) + round(margin * 0.2)
    draw.text((margin, sub_y), "Номер → ближайший цвет краски",
              fill=(120, 120, 120), font=sub_font)

    top = sub_y + round(min_dim * 0.017) + margin
    legend_rect: Rect = (margin, top, page_w - 2 * margin, page_h - top - margin)
    _draw_legend(draw, palette, legend_rect)
    return page


def _paste_artwork(page: Image.Image, draw: ImageDraw.ImageDraw,
                   seg, rect: Rect) -> None:
    ax, ay, aw, ah = rect
    src_h, src_w = seg.label_img.shape

    scale = min(aw / src_w, ah / src_h)
    tw, th = max(1, round(src_w * scale)), max(1, round(src_h * scale))

    # Rasterize the canonical vector line art at the print size. Scaling a
    # vector (rather than NEAREST-upscaling the working-res label map) keeps
    # outlines razor-smooth at 600 dpi instead of staircasing every edge.
    svg = vectorize.to_svg(
        seg.label_img, seg.palette,
        min_label_radius=6.0,
        stroke_px=max(1.0, min(src_h, src_w) * 0.0016),
    )
    png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=tw, output_height=th)
    art = Image.open(io.BytesIO(png)).convert("RGB")

    ox, oy = ax + (aw - tw) // 2, ay + (ah - th) // 2
    page.paste(art, (ox, oy))
    draw.rectangle([ox - 1, oy - 1, ox + tw, oy + th], outline=(210, 210, 210))


def _draw_legend(draw: ImageDraw.ImageDraw, palette: list[PaletteEntry],
                 rect: Rect) -> None:
    lx, ly, lw, lh = rect
    n = len(palette)

    cols = max(1, min(n, int(lw // LEGEND_MIN_COL_W)))
    rows = math.ceil(n / cols)
    row_h = min(lh / rows, LEGEND_MAX_ROW_H)
    col_w = lw / cols

    swatch = max(round(24 * _SCALE), int(min(row_h * 0.6, 72 * _SCALE)))
    font = _load_font(config.FONT_PATH, int(swatch * 0.5))
    hex_font = _load_font(config.FONT_PATH, int(swatch * 0.36))
    pad = int(swatch * 0.45)

    for i, c in enumerate(palette):
        col, row = i // rows, i % rows
        x = lx + col * col_w
        y = ly + row * row_h
        sy = y + (row_h - swatch) / 2

        rgb = tuple(int(c.hex[j:j + 2], 16) for j in (1, 3, 5))
        draw.rectangle([x, sy, x + swatch, sy + swatch], fill=rgb,
                       outline="black", width=round(2 * _SCALE))

        text_x = x + swatch + pad
        max_w = col_w - swatch - pad * 2
        name = _fit_text(font, f"{c.index}. {c.name_ru}", max_w)
        draw.text((text_x, sy), name, fill="black", font=font)
        draw.text((text_x, sy + swatch * 0.55), c.hex, fill=(130, 130, 130), font=hex_font)
