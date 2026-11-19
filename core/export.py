"""Export core (stage 3): size, colour, PNG / SVG / DXF writers, file names.

No UI imports here.  All sizes are in millimetres unless the name says ``px``.

Sizing rules (stage_3.md):
* «Как в исходнике» — physical size from the photo DPI (fallback 300 DPI),
  plus «Поле рамки» on every side.  PNG DPI changes only the pixel density and is capped at
  the photo DPI there (remark 36: never upscaled beyond the photo's pixels).
* «15 × 5 мм», custom size and saved templates — the file is exactly the box;
  the signature is scaled proportionally into the box minus «Поле рамки» on
  each side (default 0.5 mm: 15 × 5 → at most 14 × 4 mm).  Remark 7
  (2026-11-17): the margin field applies in every mode, not a fixed 0.5 mm.
* SVG — filled outline traced at the 50 % threshold, no artificial thickening
  (remark 8).  DXF — one centreline polyline per stroke with a chosen line
  thickness, default 0.18 mm (remark 9, see core/centerline.py).
"""

from __future__ import annotations

import io
import logging
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:  # pragma: no cover
    logging.getLogger(__name__).debug("module: ImportError caught", exc_info=True)   # remark 81
    cv2 = None

log = logging.getLogger(__name__)

MM_PER_INCH = 25.4
FALLBACK_DPI = 300.0
DEFAULT_MARGIN_MM = 0.5          # «Поле рамки» default, all size modes
MIN_STROKE_MM = 0.0              # SVG/DXF: no thickening of thin strokes (remark 8)
DEFAULT_DXF_LINE_MM = 0.18       # DXF centreline thickness (remark 9)
SVG_MODES = ("original", "stroke")     # remark 22: «Как в оригинале» | «Заданная толщина»
DEFAULT_SVG_MODE = "original"
DEFAULT_SVG_LINE_MM = 0.18
DXF_LINE_RANGE = (0.01, 5.0)
# AutoCAD standard lineweights, 1/100 mm
STD_LINEWEIGHTS = (0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211)
CHORD_STEP_MM = 0.05
TRACE_THRESHOLD = 0.5
DPI_CHOICES = (300, 600, 1200)   # remark 36: 150 removed, 1200 added
DEFAULT_PNG_DPI = 1200
DEFAULT_FORMATS = ("PNG", "DXF")
ALL_FORMATS = ("PNG", "SVG", "DXF")
PRESET_15X5 = (15.0, 5.0)
FIT_FILE_IS_BOX = True

# Size keys used in settings / ComboBox
SIZE_ORIGINAL = "original"
SIZE_15X5 = "15x5"
SIZE_CUSTOM = "custom"
TEMPLATE_PREFIX = "tpl:"

# Built-in colours, left to right (t28u, t216u–t217u). None = ink from photo.
BUILTIN_COLORS: List[Tuple[str, Optional[str]]] = [
    ("as_photo", None),
    ("black", "#000000"),
    ("blue", "#1B2A8A"),
    ("ink_blue", "#0B1F5C"),
    ("bright_blue", "#1D3FBF"),
]
DEFAULT_COLOR_KEY = "blue"
CUSTOM_COLOR_PREFIX = "custom:"

WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


# --------------------------------------------------------------------------- helpers
def round_half_up(value: float, digits: int = 0) -> float:
    q = Decimal(1).scaleb(-digits)
    return float(Decimal(repr(value)).quantize(q, rounding=ROUND_HALF_UP))


def mm_to_px(mm: float, dpi: float) -> int:
    return max(1, int(round_half_up(mm / MM_PER_INCH * dpi)))


def px_to_mm(px: float, dpi: float) -> float:
    return px / dpi * MM_PER_INCH


def format_number(value: float, lang: str, digits: int = 1) -> str:
    """Locale decimal separator: 64,1 (ru) / 64.1 (en)."""
    s = f"{round_half_up(value, digits):.{digits}f}"
    return s.replace(".", ",") if lang == "ru" else s


def format_plain_number(value: float, lang: str) -> str:
    """20 → «20», 2.5 → «2,5» (no trailing zeros)."""
    v = round_half_up(float(value), 2)
    s = f"{v:g}" if v != int(v) else str(int(v))
    return s.replace(".", ",") if lang == "ru" else s


def parse_number(text: str) -> Optional[float]:
    t = (text or "").strip().replace(",", ".")
    if not t:
        return None
    try:
        v = float(t)
    except ValueError:
        log.debug("parse_number: ValueError caught", exc_info=True)   # remark 81
        return None
    if not math.isfinite(v):
        return None
    return v


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ValueError(f"bad colour {hex_color!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb: Sequence[int]) -> str:
    r, g, b = (max(0, min(255, int(c))) for c in rgb[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


def resolve_color(key: str, custom_colors: Sequence[dict], photo_ink: Optional[Sequence[int]]) -> Tuple[int, int, int]:
    """Colour key → RGB.  Unknown keys fall back to «Синий»."""
    if key == "as_photo":
        if photo_ink is not None:
            return tuple(int(c) for c in photo_ink[:3])  # type: ignore[return-value]
        return hex_to_rgb(dict(BUILTIN_COLORS)[DEFAULT_COLOR_KEY])
    for k, hx in BUILTIN_COLORS:
        if k == key and hx:
            return hex_to_rgb(hx)
    if key.startswith(CUSTOM_COLOR_PREFIX):
        cid = key[len(CUSTOM_COLOR_PREFIX):]
        for c in custom_colors:
            if str(c.get("id")) == cid:
                try:
                    return hex_to_rgb(c.get("hex", ""))
                except ValueError:
                    log.debug("resolve_color: ValueError caught", exc_info=True)   # remark 81
                    break
    return hex_to_rgb(dict(BUILTIN_COLORS)[DEFAULT_COLOR_KEY])


def remove_custom_color(custom_colors: List[dict], color_id: str, default_key: str) -> Tuple[List[dict], str]:
    """Delete a user colour; if it was the default, the default becomes «Синий»."""
    left = [c for c in custom_colors if str(c.get("id")) != str(color_id)]
    if default_key == CUSTOM_COLOR_PREFIX + str(color_id):
        default_key = DEFAULT_COLOR_KEY
    return left, default_key


def remove_custom_size(custom_sizes: List[dict], size_id: str, default_key: str) -> Tuple[List[dict], str]:
    """Delete a saved template; if it was the default, «15 × 5 мм» is default again."""
    left = [s for s in custom_sizes if str(s.get("id")) != str(size_id)]
    if default_key == TEMPLATE_PREFIX + str(size_id):
        default_key = SIZE_15X5
    return left, default_key


def new_item_id(existing: Iterable[dict]) -> str:
    used = {str(e.get("id")) for e in existing}
    n = 1
    while str(n) in used:
        n += 1
    return str(n)


# --------------------------------------------------------------------------- size
@dataclass
class SizeChoice:
    kind: str  # "original" | "box"
    box_w_mm: float = 0.0
    box_h_mm: float = 0.0
    is_cell_15x5: bool = False

    @staticmethod
    def original() -> "SizeChoice":
        return SizeChoice("original")

    @staticmethod
    def box(w_mm: float, h_mm: float) -> "SizeChoice":
        is_cell = abs(w_mm - PRESET_15X5[0]) < 1e-9 and abs(h_mm - PRESET_15X5[1]) < 1e-9
        return SizeChoice("box", float(w_mm), float(h_mm), is_cell)


def size_choice_for_key(key: str, custom_sizes: Sequence[dict], custom_wh: Tuple[float, float] = (20.0, 8.0)) -> SizeChoice:
    if key == SIZE_ORIGINAL:
        return SizeChoice.original()
    if key == SIZE_CUSTOM:
        return SizeChoice.box(*custom_wh)
    if key.startswith(TEMPLATE_PREFIX):
        sid = key[len(TEMPLATE_PREFIX):]
        for s in custom_sizes:
            if str(s.get("id")) == sid:
                try:
                    return SizeChoice.box(float(s["w_mm"]), float(s["h_mm"]))
                except (KeyError, TypeError, ValueError):
                    log.debug("size_choice_for_key: (KeyError, TypeError, ValueError) caught", exc_info=True)   # remark 81
                    break
    return SizeChoice.box(*PRESET_15X5)


def valid_box_size(w: Optional[float], h: Optional[float], margin_mm: float = DEFAULT_MARGIN_MM) -> bool:
    """A box must leave room inside «Поле рамки» on every side."""
    m = max(0.0, float(margin_mm or 0.0))
    return w is not None and h is not None and w > 2 * m and h > 2 * m and w <= 2000 and h <= 2000


def margin_fits(size: "SizeChoice", margin_mm: float) -> bool:
    """«Поле рамки» must leave room for the signature inside a box (always true for «Как в исходнике»)."""
    if size.kind == "original":
        return margin_mm >= 0
    return valid_box_size(size.box_w_mm, size.box_h_mm, margin_mm)


@dataclass
class Geometry:
    content_w_mm: float
    content_h_mm: float
    file_w_mm: float
    file_h_mm: float
    box_mm: Optional[Tuple[float, float]] = None  # the cell outline for preview

    @property
    def offset_mm(self) -> Tuple[float, float]:
        return ((self.file_w_mm - self.content_w_mm) / 2, (self.file_h_mm - self.content_h_mm) / 2)


def compute_geometry(src_w_px: int, src_h_px: int, src_dpi: float, size: SizeChoice, margin_mm: float) -> Geometry:
    src_w_px = max(1, int(src_w_px))
    src_h_px = max(1, int(src_h_px))
    if size.kind == "original":
        dpi = src_dpi if src_dpi and src_dpi > 0 else FALLBACK_DPI
        cw, ch = px_to_mm(src_w_px, dpi), px_to_mm(src_h_px, dpi)
        m = max(0.0, float(margin_mm or 0.0))
        return Geometry(cw, ch, cw + 2 * m, ch + 2 * m, None)
    m = max(0.0, float(margin_mm or 0.0))
    inner_w = size.box_w_mm - 2 * m
    inner_h = size.box_h_mm - 2 * m
    if inner_w <= 0 or inner_h <= 0:
        raise ValueError("box too small")
    s = min(inner_w / src_w_px, inner_h / src_h_px)
    cw, ch = src_w_px * s, src_h_px * s
    if FIT_FILE_IS_BOX:
        return Geometry(cw, ch, size.box_w_mm, size.box_h_mm, (size.box_w_mm, size.box_h_mm))
    return Geometry(cw, ch, cw, ch, (size.box_w_mm, size.box_h_mm))


# --------------------------------------------------------------------------- source
@dataclass
class ExportSource:
    mask: np.ndarray            # bool, tight crop around the ink
    dpi: float                  # DPI used for «Как в исходнике»
    has_dpi: bool
    ink_rgb: Optional[Tuple[int, int, int]] = None
    name: str = ""
    alpha: Optional[np.ndarray] = None  # uint8 soft mask, same crop as ``mask`` (PNG anti-aliasing)

    @property
    def size_px(self) -> Tuple[int, int]:
        return int(self.mask.shape[1]), int(self.mask.shape[0])


def tight_bbox(mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def source_from_mask(mask: np.ndarray, dpi: Optional[float], ink_rgb=None, name: str = "") -> ExportSource:
    has_dpi = bool(dpi and dpi > 0)
    bb = tight_bbox(mask)
    if bb is None:
        crop = np.zeros((1, 1), dtype=bool)
    else:
        x0, y0, x1, y1 = bb
        crop = mask[y0:y1, x0:x1].astype(bool)
    return ExportSource(crop, float(dpi) if has_dpi else FALLBACK_DPI, has_dpi, ink_rgb, name)


def source_from_result(result) -> ExportSource:
    """Build the export source from a stage-2 ProcessResult (mask honours eraser).

    ``source_dpi`` is the DPI stored in the photo (already converted to the working
    resolution); without it the 300 DPI fallback is applied to the *original* pixels,
    i.e. ``work_dpi`` when the photo was downscaled for processing."""
    dpi = getattr(result, "source_dpi", None)
    src = source_from_mask(result.mask, dpi, getattr(result, "ink_color", None), getattr(result, "source_name", ""))
    work_dpi = getattr(result, "work_dpi", None)
    if not src.has_dpi and work_dpi:
        src.dpi = float(work_dpi)
    alpha = getattr(result, "alpha", None)
    bb = tight_bbox(result.mask)
    if alpha is not None and bb is not None and alpha.shape == result.mask.shape:
        x0, y0, x1, y1 = bb
        src.alpha = np.asarray(alpha[y0:y1, x0:x1], dtype=np.uint8)
    return src


# --------------------------------------------------------------------------- PNG
def render_png(source: ExportSource, geom: Geometry, rgb: Sequence[int], dpi: float) -> Image.Image:
    """Transparent RGBA; soft anti-aliased edges (alpha) — PNG only."""
    fw, fh = mm_to_px(geom.file_w_mm, dpi), mm_to_px(geom.file_h_mm, dpi)
    cw, ch = mm_to_px(geom.content_w_mm, dpi), mm_to_px(geom.content_h_mm, dpi)
    cw, ch = min(cw, fw), min(ch, fh)
    if source.alpha is not None and source.alpha.shape == source.mask.shape:
        alpha_src = Image.fromarray(source.alpha, "L")
    else:
        alpha_src = Image.fromarray((source.mask.astype(np.uint8) * 255), "L")
    alpha = alpha_src.resize((cw, ch), Image.Resampling.LANCZOS)
    out_alpha = Image.new("L", (fw, fh), 0)
    ox, oy = (fw - cw) // 2, (fh - ch) // 2
    out_alpha.paste(alpha, (ox, oy))
    r, g, b = (int(c) for c in rgb[:3])
    img = Image.new("RGBA", (fw, fh), (r, g, b, 0))
    img.putalpha(out_alpha)
    return img


def effective_png_dpi(source: Optional["ExportSource"], size: Optional[SizeChoice], dpi: float) -> float:
    """Remark 36: in «Как в исходнике» the PNG is never upscaled beyond the photo's own pixels.

    The size in mm stays as computed from the photo DPI; the pixel density is capped at that DPI
    (photo DPI at working resolution, or the 300 DPI fallback), so the file holds at most the
    cropped pixels and its DPI metadata is the effective value.  Box sizes keep the chosen DPI."""
    dpi = float(dpi)
    if source is not None and size is not None and size.kind == "original" and source.dpi and source.dpi > 0:
        return min(dpi, float(source.dpi))
    return dpi


def dpi_label(dpi: float) -> int:
    """Whole-number DPI for labels and badges."""
    return int(round_half_up(dpi))


def png_bytes(img: Image.Image, dpi: float) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", dpi=(dpi, dpi), optimize=False, compress_level=6)
    return buf.getvalue()


def estimate_kb(data_len: int) -> int:
    return max(1, int(round_half_up(data_len / 1024)))


# --------------------------------------------------------------------------- tracing
@dataclass
class TracedOutline:
    """Potrace result mapped to millimetres (y axis down, origin top-left of file)."""
    curves: list = field(default_factory=list)  # list of list of segments (see _map_curve)
    file_w_mm: float = 0.0
    file_h_mm: float = 0.0


def _trace_resolution(source: ExportSource, geom: Geometry) -> float:
    """Pixels per mm for the trace bitmap (SVG and DXF).

    Remark 40 (2026-11-18): never below the source resolution — the 40 px/mm cap only limits upsampling.
    Downsampling thin strokes (~1 px after resize) let the DXF blur drop them below the 50 % threshold
    (фото 3 15 × 5: 7.8 mm of centreline instead of ~37 mm)."""
    sw, _ = source.size_px
    src_ppm = sw / max(geom.content_w_mm, 1e-6)
    ppm = max(min(40.0, max(src_ppm, 20.0)), src_ppm)
    longest = max(geom.content_w_mm, geom.content_h_mm) * ppm
    if longest > 3000:
        ppm *= 3000 / longest
    return ppm


def thicken_thin_strokes(mask: np.ndarray, min_width_px: float) -> np.ndarray:
    """Make strokes thinner than ``min_width_px`` at least that wide (SVG/DXF only)."""
    if cv2 is None or min_width_px <= 1.0 or not mask.any():
        return mask
    m = mask.astype(np.uint8)
    k = max(2, int(math.ceil(min_width_px)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    opened = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel)
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    # corners of thick strokes also vanish on opening — keep only pixels whose
    # neighbourhood has no thick core (local max of the distance is small)
    local_max = cv2.dilate(dist, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
    thin = (m > 0) & (opened == 0) & (local_max < min_width_px / 2.0)
    if not thin.any():
        return mask
    width_est = 2.0 * float(np.percentile(dist[thin], 90))
    r = int(math.ceil(max(0.0, (min_width_px - width_est) / 2.0)))
    if r <= 0:
        return mask
    dil = cv2.dilate(thin.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    return (m > 0) | (dil > 0)


def trace_bitmap(source: ExportSource, geom: Geometry, min_stroke_mm: float = MIN_STROKE_MM) -> Tuple[np.ndarray, float, float]:
    """Single pass: resample the mask to trace resolution, 50 % threshold.

    ``min_stroke_mm`` > 0 would thicken thin strokes; the export uses 0 (remark 8: stroke
    thickness as in the source)."""
    ppm = _trace_resolution(source, geom)
    tw = max(1, int(round(geom.content_w_mm * ppm)))
    th = max(1, int(round(geom.content_h_mm * ppm)))
    alpha = Image.fromarray(source.mask.astype(np.uint8) * 255, "L").resize((tw, th), Image.Resampling.LANCZOS)
    bm = np.asarray(alpha) >= int(round(255 * TRACE_THRESHOLD))
    ppm_x, ppm_y = tw / geom.content_w_mm, th / geom.content_h_mm
    if min_stroke_mm > 0:
        bm = thicken_thin_strokes(bm, min_stroke_mm * min(ppm_x, ppm_y))
    return bm, ppm_x, ppm_y


def trace_outline(source: ExportSource, geom: Geometry) -> TracedOutline:
    import potrace  # potracer (GPL)

    bm, ppm_x, ppm_y = trace_bitmap(source, geom)
    pad = 2
    padded = np.pad(bm, pad, mode="constant", constant_values=False)
    path = potrace.Bitmap(~padded).trace(turdsize=2, turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY,
                                         alphamax=1.0, opticurve=True, opttolerance=0.2)
    ox, oy = geom.offset_mm

    def mp(p) -> Tuple[float, float]:
        return (ox + (p.x - pad) / ppm_x, oy + (p.y - pad) / ppm_y)

    curves = []
    for curve in path:
        segs = []
        start = mp(curve.start_point)
        for seg in curve:
            if seg.is_corner:
                segs.append(("L", mp(seg.c), mp(seg.end_point)))
            else:
                segs.append(("C", mp(seg.c1), mp(seg.c2), mp(seg.end_point)))
        if segs:
            curves.append((start, segs))
    return TracedOutline(curves, geom.file_w_mm, geom.file_h_mm)


def _bezier_points(p0, p1, p2, p3, chord: float) -> List[Tuple[float, float]]:
    approx = (math.dist(p0, p1) + math.dist(p1, p2) + math.dist(p2, p3))
    n = max(1, int(math.ceil(approx / chord)))
    pts = []
    for i in range(1, n + 1):
        t = i / n
        mt = 1 - t
        x = mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0]
        y = mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]
        pts.append((x, y))
    return pts


def outline_polygons(outline: TracedOutline, chord_mm: float = CHORD_STEP_MM) -> List[List[Tuple[float, float]]]:
    """Flatten curves to closed polylines with chord step ≈ 0.05 mm."""
    polys = []
    for start, segs in outline.curves:
        pts = [start]
        cur = start
        for seg in segs:
            if seg[0] == "L":
                _, c, end = seg
                pts.extend([c, end])
                cur = end
            else:
                _, c1, c2, end = seg
                pts.extend(_bezier_points(cur, c1, c2, end, chord_mm))
                cur = end
        # drop duplicate closing point
        if len(pts) > 1 and math.dist(pts[0], pts[-1]) < 1e-9:
            pts.pop()
        dedup = [pts[0]]
        for p in pts[1:]:
            if math.dist(p, dedup[-1]) > 1e-9:
                dedup.append(p)
        if len(dedup) >= 3:
            polys.append(dedup)
    return polys


# --------------------------------------------------------------------------- SVG
def _f(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def svg_document(outline: TracedOutline, rgb: Sequence[int]) -> str:
    """Solid outlines in the chosen colour, no alpha; size in mm + viewBox."""
    w, h = outline.file_w_mm, outline.file_h_mm
    parts = []
    for start, segs in outline.curves:
        d = [f"M{_f(start[0])} {_f(start[1])}"]
        for seg in segs:
            if seg[0] == "L":
                _, c, end = seg
                d.append(f"L{_f(c[0])} {_f(c[1])}L{_f(end[0])} {_f(end[1])}")
            else:
                _, c1, c2, end = seg
                d.append(f"C{_f(c1[0])} {_f(c1[1])} {_f(c2[0])} {_f(c2[1])} {_f(end[0])} {_f(end[1])}")
        d.append("Z")
        parts.append("".join(d))
    path = f'  <path fill="{rgb_to_hex(rgb)}" fill-rule="evenodd" d="{" ".join(parts)}"/>\n' if parts else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{_f(w)}mm" height="{_f(h)}mm" '
        f'viewBox="0 0 {_f(w)} {_f(h)}">\n'
        f"{path}"
        "</svg>\n"
    )


def svg_stroke_document(centerline: "Centerline", rgb: Sequence[int], width_mm: float = DEFAULT_SVG_LINE_MM) -> str:
    """SVG «Заданная толщина» (remark 22): the stroke centrelines as open paths, no fill,
    ``stroke-width`` in millimetres (the viewBox unit), round caps and joins."""
    width_mm = clamp_dxf_line(width_mm)
    w, h = centerline.file_w_mm, centerline.file_h_mm
    parts = []
    for pts, closed in centerline.paths:
        if len(pts) < 2:
            continue
        d = f"M{_f(pts[0][0])} {_f(pts[0][1])}" + "".join(f"L{_f(x)} {_f(y)}" for x, y in pts[1:])
        parts.append(d + ("Z" if closed else ""))
    body = ""
    if parts:
        body = (f'  <g fill="none" stroke="{rgb_to_hex(rgb)}" stroke-width="{_f(width_mm)}" '
                'stroke-linecap="round" stroke-linejoin="round">\n'
                + "".join(f'    <path d="{d}"/>\n' for d in parts) + "  </g>\n")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{_f(w)}mm" height="{_f(h)}mm" '
        f'viewBox="0 0 {_f(w)} {_f(h)}">\n'
        f"{body}"
        "</svg>\n"
    )


def clamp_svg_mode(mode) -> str:
    return mode if mode in SVG_MODES else DEFAULT_SVG_MODE


def resolve_svg_mode(last_export, default) -> str:
    """Mode the SVG card opens with (remark 29): the choice remembered from the last export, else the
    default from Settings › «Форматы по умолчанию» (svg_mode), else «Как в оригинале»."""
    last = last_export.get("svg_mode") if isinstance(last_export, dict) else None
    return clamp_svg_mode(last or default or DEFAULT_SVG_MODE)


def resolve_svg_line(last_export, default) -> float:
    """SVG «Толщина линии» the card opens with (remark 32): the value changed on screen 3 and remembered
    in last_export, else the default from Settings › «Толщина SVG» (svg_line_mm), else 0,18 mm."""
    last = last_export.get("svg_line_mm") if isinstance(last_export, dict) else None
    for v in (last, default):
        if isinstance(v, (int, float)) and not isinstance(v, bool) and DXF_LINE_RANGE[0] <= v <= DXF_LINE_RANGE[1]:
            return round(float(v), 2)
    return DEFAULT_SVG_LINE_MM


# --------------------------------------------------------------------------- centreline (DXF)
@dataclass
class Centerline:
    """Stroke centrelines in millimetres (y axis down, origin top-left of file)."""
    paths: list = field(default_factory=list)   # list of (points [(x, y)], closed)
    file_w_mm: float = 0.0
    file_h_mm: float = 0.0


def trace_centerline(source: ExportSource, geom: Geometry) -> Centerline:
    """Skeleton of the 50 % mask at trace resolution, lightly blurred first so the edge
    noise does not grow spurs; then mapped to millimetres."""
    from core.centerline import centerline_paths

    ppm = _trace_resolution(source, geom)
    tw = max(1, int(round(geom.content_w_mm * ppm)))
    th = max(1, int(round(geom.content_h_mm * ppm)))
    alpha = np.asarray(Image.fromarray(source.mask.astype(np.uint8) * 255, "L").resize((tw, th), Image.Resampling.LANCZOS))
    if cv2 is not None:
        alpha = cv2.GaussianBlur(alpha, (0, 0), 0.8)
    bm = alpha >= int(round(255 * TRACE_THRESHOLD))
    ppm_x, ppm_y = tw / geom.content_w_mm, th / geom.content_h_mm
    ox, oy = geom.offset_mm
    paths = []
    for pts, closed in centerline_paths(bm):
        paths.append(([(ox + x / ppm_x, oy + y / ppm_y) for x, y in pts], closed))
    return Centerline(paths, geom.file_w_mm, geom.file_h_mm)


def resolve_dxf_line(last_export, default) -> float:
    """Remark 50: DXF «Толщина линии» the card opens with — a quick change on screen 3 remembered in
    last_export, else the default from Settings › «Толщина DXF» (dxf_line_mm), else 0,18 mm."""
    last = last_export.get("dxf_line_mm") if isinstance(last_export, dict) else None
    for v in (last, default):
        if isinstance(v, (int, float)) and not isinstance(v, bool) and DXF_LINE_RANGE[0] <= v <= DXF_LINE_RANGE[1]:
            return round(float(v), 2)
    return DEFAULT_DXF_LINE_MM


def clamp_dxf_line(width_mm) -> float:
    try:
        v = float(width_mm)
    except (TypeError, ValueError):
        log.debug("clamp_dxf_line: (TypeError, ValueError) caught", exc_info=True)   # remark 81
        return DEFAULT_DXF_LINE_MM
    if not math.isfinite(v):
        return DEFAULT_DXF_LINE_MM
    return min(DXF_LINE_RANGE[1], max(DXF_LINE_RANGE[0], v))


def extend_ends(pts, d: float):
    """Lengthen an open polyline by ``d`` at both ends along its end tangents."""
    if len(pts) < 2 or d <= 0:
        return list(pts)
    out = list(pts)
    for idx, nb in ((0, 1), (-1, -2)):
        (x0, y0), (x1, y1) = out[idx], out[nb]
        L = math.hypot(x0 - x1, y0 - y1)
        if L > 1e-9:
            out[idx] = (x0 + (x0 - x1) / L * d, y0 + (y0 - y1) / L * d)
    return out


def nearest_lineweight(width_mm: float) -> int:
    """Closest AutoCAD standard lineweight (1/100 mm) for the LWDISPLAY view."""
    hund = width_mm * 100
    return min(STD_LINEWEIGHTS[1:], key=lambda lw: (abs(lw - hund), lw))


# --------------------------------------------------------------------------- DXF
def dxf_document(centerline: Centerline, rgb: Sequence[int], width_mm: float = DEFAULT_DXF_LINE_MM):
    """DXF R2010, mm: one open LWPOLYLINE along each stroke centre (closed for loops).

    The thickness is written twice so every viewer shows it: a constant polyline width
    (AutoCAD draws it regardless of the lineweight display) and the nearest standard
    lineweight with ``$LWDISPLAY`` on.  No HATCH, no SPLINE."""
    import ezdxf
    from ezdxf import colors as ezcolors

    width_mm = clamp_dxf_line(width_mm)
    doc = ezdxf.new("R2010", setup=False)
    doc.units = ezdxf.units.MM
    doc.header["$INSUNITS"] = 4
    doc.header["$MEASUREMENT"] = 1
    doc.header["$LUNITS"] = 2
    doc.header["$LWDISPLAY"] = 1
    msp = doc.modelspace()
    h = centerline.file_h_mm
    true_color = ezcolors.rgb2int(tuple(int(c) for c in rgb[:3]))
    attrs = {"true_color": true_color, "color": 7, "const_width": width_mm,
             "lineweight": nearest_lineweight(width_mm)}
    for pts, closed in centerline.paths:
        if not closed:
            pts = extend_ends(pts, width_mm / 2)   # butt ends of a wide polyline → cover the joint / tip
        poly = [(x, h - y) for x, y in pts]
        if len(poly) >= 2:
            msp.add_lwpolyline(poly, close=bool(closed), dxfattribs=dict(attrs))
    doc.header["$EXTMIN"] = (0, 0, 0)
    doc.header["$EXTMAX"] = (centerline.file_w_mm, centerline.file_h_mm, 0)
    return doc


def vector_sizes_kb(outline: Optional["TracedOutline"], centerline: Optional[Centerline], rgb: Sequence[int],
                    width_mm: float = DEFAULT_DXF_LINE_MM, svg_mode: str = DEFAULT_SVG_MODE,
                    svg_line_mm: float = DEFAULT_SVG_LINE_MM) -> dict:
    """≈ file size in KB of the SVG and DXF for the preview badge."""
    out = {}
    if svg_mode == "stroke" and centerline is not None:
        out["SVG"] = estimate_kb(len(svg_stroke_document(centerline, rgb, svg_line_mm).encode("utf-8")))
    elif outline is not None:
        out["SVG"] = estimate_kb(len(svg_document(outline, rgb).encode("utf-8")))
    if centerline is not None:
        out["DXF"] = estimate_kb(len(dxf_bytes(dxf_document(centerline, rgb, width_mm))))
    return out


def dxf_bytes(doc) -> bytes:
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


# --------------------------------------------------------------------------- names
def expand_template(template: str, name: str, when: Optional[datetime] = None) -> str:
    when = when or datetime.now()
    date = when.strftime("%Y-%m-%d")
    out = template or ""
    for tok in ("{имя}", "{name}"):
        out = out.replace(tok, name)
    for tok in ("{дата}", "{date}"):
        out = out.replace(tok, date)
    return out


def sanitize_filename(name: str, fallback: str = "signature") -> str:
    """Neutralise characters Windows forbids; never raise."""
    s = _INVALID_CHARS.sub("_", name or "")
    s = s.strip().rstrip(". ")
    if not s:
        s = fallback
    stem = s.split(".")[0].upper()
    if stem in WINDOWS_RESERVED:
        s = "_" + s
    if len(s) > 180:
        s = s[:180].rstrip(". ")
    return s


def strip_known_ext(name: str) -> str:
    low = name.lower()
    for ext in (".png", ".svg", ".dxf"):
        if low.endswith(ext):
            return name[: -len(ext)]
    return name


def target_paths(folder: Path, base: str, formats: Sequence[str]) -> List[Path]:
    return [Path(folder) / f"{base}.{fmt.lower()}" for fmt in formats]


def existing_targets(folder: Path, base: str, formats: Sequence[str]) -> List[Path]:
    return [p for p in target_paths(folder, base, formats) if p.exists()]


def numbered_base(folder: Path, base: str, formats: Sequence[str]) -> str:
    """«name (2)», «name (3)» … — first number free for every selected format."""
    if not existing_targets(folder, base, formats):
        return base
    n = 2
    while existing_targets(folder, f"{base} ({n})", formats):
        n += 1
    return f"{base} ({n})"


def resolve_base(folder: Path, base: str, formats: Sequence[str], mode: str) -> Tuple[str, List[Path]]:
    """Return (base to use, conflicts needing a question).

    mode: add_number | replace | ask.  For ``ask`` with conflicts the caller
    shows dialog 43 and then calls again with add_number / replace.
    """
    conflicts = existing_targets(folder, base, formats)
    if not conflicts or mode == "replace":
        return base, []
    if mode == "ask":
        return base, conflicts
    return numbered_base(folder, base, formats), []


# --------------------------------------------------------------------------- job
@dataclass
class ExportJob:
    source: ExportSource
    size: SizeChoice
    margin_mm: float
    rgb: Tuple[int, int, int]
    png_dpi: int
    formats: Tuple[str, ...]
    dxf_line_mm: float = DEFAULT_DXF_LINE_MM
    svg_mode: str = DEFAULT_SVG_MODE
    svg_line_mm: float = DEFAULT_SVG_LINE_MM


def build_outputs(job: ExportJob, outline: Optional[TracedOutline] = None,
                  centerline: Optional[Centerline] = None) -> dict:
    """Render every selected format into bytes {fmt: bytes}."""
    sw, sh = job.source.size_px
    geom = compute_geometry(sw, sh, job.source.dpi, job.size, job.margin_mm)
    out = {}
    if "PNG" in job.formats:
        dpi = effective_png_dpi(job.source, job.size, job.png_dpi)
        out["PNG"] = png_bytes(render_png(job.source, geom, job.rgb, dpi), dpi)
    if "SVG" in job.formats:
        if job.svg_mode == "stroke":
            if centerline is None:
                centerline = trace_centerline(job.source, geom)
            out["SVG"] = svg_stroke_document(centerline, job.rgb, job.svg_line_mm).encode("utf-8")
        else:
            if outline is None:
                outline = trace_outline(job.source, geom)
            out["SVG"] = svg_document(outline, job.rgb).encode("utf-8")
    if "DXF" in job.formats:
        if centerline is None:
            centerline = trace_centerline(job.source, geom)
        out["DXF"] = dxf_bytes(dxf_document(centerline, job.rgb, job.dxf_line_mm))
    return out


def write_outputs(folder: Path, base: str, outputs: dict) -> List[Path]:
    """Atomic-ish write: temp file in the same folder, then os.replace."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for fmt in ALL_FORMATS:
        if fmt not in outputs:
            continue
        target = folder / f"{base}.{fmt.lower()}"
        tmp = folder / f".{base}.{fmt.lower()}.tmp"
        try:
            with open(tmp, "wb") as f:
                f.write(outputs[fmt])
            os.replace(tmp, target)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    log.warning("could not remove temp file %s", tmp)
        written.append(target)
    return written
