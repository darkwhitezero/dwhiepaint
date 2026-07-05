"""/export pipeline: compose printable page(s) as a PDF.

Page 1 is the clean coloring sheet (line art + numbers only). Page 2 is an
optional legend sheet: the mapping from each number to the closest named color
(swatch + Russian name + hex). Line art is re-rendered at the target print
resolution for crisp outlines and numbers.
"""

from __future__ import annotations

import io
import math
import zipfile

import cairosvg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import config, paints, render, vectorize
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

    pages = [_coloring_page(entry, seg, page_w, page_h)]
    if include_legend:
        pages.append(_legend_page(seg.palette, page_w, page_h))

    buf = io.BytesIO()
    pages[0].save(
        buf, format="PDF", resolution=float(DPI),
        save_all=True, append_images=pages[1:],
    )
    return buf.getvalue()


def export_svg(entry: ImageEntry) -> bytes:
    """Return the canonical scalable coloring sheet as SVG bytes (DPI-free)."""
    seg = entry.segmentation
    if seg is None:
        raise ValueError("image has not been segmented yet")
    src_h, src_w = seg.label_img.shape
    svg = vectorize.to_svg(
        seg.label_img, seg.palette,
        min_label_radius=6.0,
        stroke_px=max(1.0, min(src_h, src_w) * 0.0016),
    )
    return svg.encode("utf-8")


def compose_bundle(entry: ImageEntry, page_size: str = "A4",
                   include_legend: bool = True) -> bytes:
    """Return a ZIP with the printable PDF, the vector SVG, and the painted preview."""
    seg = entry.segmentation
    if seg is None:
        raise ValueError("image has not been segmented yet")

    painted = render.painted_preview(seg.label_img, seg.palette)
    pbuf = io.BytesIO()
    Image.fromarray(painted.astype("uint8")).save(pbuf, format="PNG")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("raskraska.pdf", compose_export(entry, page_size, include_legend))
        z.writestr("kontur.svg", export_svg(entry))
        z.writestr("predprosmotr.png", pbuf.getvalue())
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

    page = _coloring_page(entry, seg, page_w, page_h)
    buf = io.BytesIO()
    page.save(buf, format="PNG", dpi=(DPI, DPI))
    return buf.getvalue()


def compose_tiled(entry: ImageEntry, page_size: str = "A4", grid: int = 2,
                  include_legend: bool = True) -> bytes:
    """Tiled printing: the coloring artwork spread across grid×grid sheets.

    Big canvases don't fit one A4, so the vector artwork is rasterized across a
    canvas ``grid`` sheets wide/tall (with a shared overlap band for gluing) and
    split into per-sheet pages, each with corner crop marks and a "row-col"
    label. A first "assembly map" page shows the whole picture with the grid and
    tile numbers so the sheets are easy to lay out. Optional legend page last.
    """
    seg = entry.segmentation
    if seg is None:
        raise ValueError("image has not been segmented yet")
    grid = max(1, min(grid, 4))

    page_w, page_h = _page_dimensions(page_size, landscape=False)
    md = min(page_w, page_h)
    margin = round(md * 0.04)
    overlap = round(md * 0.03)
    usable_w, usable_h = page_w - 2 * margin, page_h - 2 * margin

    total_w = usable_w * grid - overlap * (grid - 1)
    total_h = usable_h * grid - overlap * (grid - 1)

    src_h, src_w = seg.label_img.shape
    scale = min(total_w / src_w, total_h / src_h)
    aw, ah = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    svg = vectorize.to_svg(seg.label_img, seg.palette, min_label_radius=6.0,
                           stroke_px=max(1.0, min(src_h, src_w) * 0.0016))
    art = Image.open(io.BytesIO(
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=aw, output_height=ah)
    )).convert("RGB")
    canvas = Image.new("RGB", (total_w, total_h), "white")
    canvas.paste(art, ((total_w - aw) // 2, (total_h - ah) // 2))

    pages = [_tile_map_page(seg, page_w, page_h, grid)]
    step_w, step_h = usable_w - overlap, usable_h - overlap
    label_font = _load_font(config.FONT_PATH, round(md * 0.02))
    for r in range(grid):
        for c in range(grid):
            crop = canvas.crop((c * step_w, r * step_h,
                                c * step_w + usable_w, r * step_h + usable_h))
            page = Image.new("RGB", (page_w, page_h), "white")
            page.paste(crop, (margin, margin))
            draw = ImageDraw.Draw(page)
            _draw_crop_marks(draw, margin, margin, usable_w, usable_h, md)
            draw.text((margin, page_h - round(margin * 0.75)),
                      f"Лист {r + 1}-{c + 1}  ·  ряд {r + 1}, столбец {c + 1}",
                      fill=(120, 120, 120), font=label_font)
            pages.append(page)

    if include_legend:
        pages.append(_legend_page(seg.palette, page_w, page_h))

    buf = io.BytesIO()
    pages[0].save(buf, format="PDF", resolution=float(DPI),
                  save_all=True, append_images=pages[1:])
    return buf.getvalue()


def _tile_map_page(seg, page_w: int, page_h: int, grid: int) -> Image.Image:
    page = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(page)
    md = min(page_w, page_h)
    margin = round(md * 0.05)

    draw.text((margin, margin), f"Схема сборки — {grid}×{grid} листов",
              fill="black", font=_load_font(config.FONT_PATH_BOLD, round(md * 0.028)))
    top = margin + round(md * 0.05)

    painted = render.painted_preview(seg.label_img, seg.palette)
    im = Image.fromarray(painted.astype("uint8")).convert("RGB")
    area_w, area_h = page_w - 2 * margin, page_h - top - margin
    im.thumbnail((area_w, area_h), Image.LANCZOS)
    ox, oy = margin + (area_w - im.width) // 2, top + (area_h - im.height) // 2
    page.paste(im, (ox, oy))

    line_w = max(1, round(md * 0.0025))
    for i in range(grid + 1):
        x = ox + round(im.width * i / grid)
        y = oy + round(im.height * i / grid)
        draw.line([(x, oy), (x, oy + im.height)], fill=(20, 20, 20), width=line_w)
        draw.line([(ox, y), (ox + im.width, y)], fill=(20, 20, 20), width=line_w)
    lf = _load_font(config.FONT_PATH_BOLD, round(md * 0.022))
    for r in range(grid):
        for c in range(grid):
            cx = ox + round(im.width * (c + 0.5) / grid)
            cy = oy + round(im.height * (r + 0.5) / grid)
            draw.text((cx, cy), f"{r + 1}-{c + 1}", fill=(230, 40, 40), font=lf, anchor="mm")
    return page


def _draw_crop_marks(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, md: int) -> None:
    m = round(md * 0.022)
    wdt = max(1, round(md * 0.0025))
    for cx, cy, dx, dy in [(x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)]:
        draw.line([(cx, cy), (cx + dx * m, cy)], fill=(0, 0, 0), width=wdt)
        draw.line([(cx, cy), (cx, cy + dy * m)], fill=(0, 0, 0), width=wdt)


def _coloring_page(entry: ImageEntry, seg, page_w: int, page_h: int) -> Image.Image:
    min_dim = min(page_w, page_h)
    margin = round(min_dim * 0.04)

    page = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(page)

    title_size = round(min_dim * 0.022)
    title_font = _load_font(config.FONT_PATH, title_size)
    draw.text((margin, round(margin * 0.5)), "dwhiepaint — раскраска по номерам",
              fill=(120, 120, 120), font=title_font)

    # Reference thumbnails (original photo + painted preview) in the top-right so
    # the painter can see the target while colouring.
    ref_bottom = _paste_reference(page, draw, entry, seg, page_w, margin,
                                  round(min_dim * 0.13))

    top = max(margin + title_size + round(margin * 0.4), ref_bottom + round(margin * 0.4))
    art_rect: Rect = (margin, top, page_w - 2 * margin, page_h - top - margin)
    _paste_artwork(page, draw, seg, art_rect)
    return page


def _paste_reference(page: Image.Image, draw: ImageDraw.ImageDraw,
                     entry: ImageEntry, seg, page_w: int, margin: int,
                     ref_h: int) -> int:
    """Paste original + painted-preview thumbnails top-right; return their bottom y."""
    cap_font = _load_font(config.FONT_PATH, max(8, round(ref_h * 0.14)))
    painted = render.painted_preview(seg.label_img, seg.palette)
    thumbs = [("Оригинал", entry.rgb), ("Ваш результат", painted)]

    gap = round(ref_h * 0.14)
    x_right = page_w - margin
    y = round(margin * 0.5)
    bottom = y
    for label, arr in reversed(thumbs):  # rightmost first → left-to-right order kept
        im = Image.fromarray(np.asarray(arr).astype("uint8")).convert("RGB")
        im.thumbnail((round(ref_h * 1.25), ref_h), Image.LANCZOS)
        x = x_right - im.width
        page.paste(im, (x, y))
        draw.rectangle([x - 1, y - 1, x + im.width, y + im.height], outline=(200, 200, 200))
        draw.text((x, y + im.height + round(ref_h * 0.04)), label,
                  fill=(120, 120, 120), font=cap_font)
        bottom = max(bottom, y + im.height + round(ref_h * 0.2))
        x_right = x - gap
    return bottom


def _legend_page(palette: list[PaletteEntry], page_w: int, page_h: int) -> Image.Image:
    min_dim = min(page_w, page_h)
    margin = round(min_dim * 0.045)

    page = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(page)

    title_font = _load_font(config.FONT_PATH_BOLD, round(min_dim * 0.028))
    sub_font = _load_font(config.FONT_PATH, round(min_dim * 0.017))
    draw.text((margin, margin), "Цвета", fill="black", font=title_font)
    sub_y = margin + round(min_dim * 0.028) + round(margin * 0.2)
    draw.text((margin, sub_y), f"Номер → краска из набора «{paints.set_name()}»",
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

        info = paints.describe(c.lab)
        paint_txt = (
            "смешать: " + " + ".join(info["mix"]) if info.get("mix") else "≈ " + info["paint_name"]
        )
        draw.text((text_x, sy + swatch * 0.52), _fit_text(hex_font, paint_txt, max_w),
                  fill=(90, 90, 90), font=hex_font)
