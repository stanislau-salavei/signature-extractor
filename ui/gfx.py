"""Anti-aliased rendering of Win11 shapes with PIL (4x supersampling + LANCZOS), cached.

Every function returns a PIL image in *device* pixels for the current scale; ``photo()``
wraps it into a cached ``ImageTk.PhotoImage``.

Remark 96 (audit C1): large rounded plates are supersampled only around their corners and edges — the
middle of a plate is the same column / row repeated, the inside of a dashed outline is empty.  The result
is the same, pixel for pixel, as rendering the whole plate at 4×: with an integer factor LANCZOS gives every
output pixel the same weights, so a pixel depends only on the 4× pixels within ±3 output px of it.
"""
from __future__ import annotations

import functools
import logging
import math
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageTk

from ui.theme import Scale, rgb

log = logging.getLogger(__name__)

SS = 4  # supersampling
LANCZOS_REACH = 3      # output px on each side that LANCZOS (support 3) reads
ASSETS = Path(__file__).resolve().parents[1] / "assets"
# remark 97 (audit C2): least recently used images go first once the cache holds ~64 MB of pixels.  Images on
# screen stay alive anyway: every widget keeps a reference to what it shows (Box._imgs).
PHOTO_CACHE_BYTES = 64 * 1024 * 1024
_photo_cache: "OrderedDict[tuple, Tuple[ImageTk.PhotoImage, int]]" = OrderedDict()
_photo_bytes = 0


def clear_cache() -> None:
    global _photo_bytes
    _photo_cache.clear()
    _photo_bytes = 0
    _icon_mask.cache_clear()


def photo(key: tuple, factory) -> ImageTk.PhotoImage:
    global _photo_bytes
    k = key + (Scale.factor,)
    hit = _photo_cache.get(k)
    if hit is not None:
        _photo_cache.move_to_end(k)
        return hit[0]
    img = factory()
    p = ImageTk.PhotoImage(img)
    size = img.width * img.height * 4
    _photo_cache[k] = (p, size)
    _photo_bytes += size
    while _photo_bytes > PHOTO_CACHE_BYTES and len(_photo_cache) > 1:
        _old, (_p, n) = _photo_cache.popitem(last=False)
        _photo_bytes -= n
    return p


def cache_bytes() -> int:
    """Pixels held by the PhotoImage cache (tests)."""
    return _photo_bytes


def rgba(c: str, a: float = 1.0) -> Tuple[int, int, int, int]:
    r, g, b = rgb(c)
    return r, g, b, int(round(a * 255))


def _dev(v: float) -> float:
    return v * Scale.factor


@dataclass(frozen=True)
class ShapeStyle:
    """Remark 116 (audit B7): how a rounded plate looks — instead of a dozen parameters.

    ``stroke_bottom`` paints the lower ``bottom_w`` px of the outline in another colour (Win11 elevation
    border); ``stroke_top`` the upper 1 px; ``corners`` = (tl, tr, br, bl) rounded or square."""
    radius: float = 0.0
    fill: Optional[str] = None
    stroke: Optional[str] = None
    stroke_w: float = 1.0
    stroke_top: Optional[str] = None
    stroke_bottom: Optional[str] = None
    bottom_w: float = 1.0
    bg: Optional[str] = None
    corners: Tuple[bool, bool, bool, bool] = (True, True, True, True)
    fill_alpha: float = 1.0


def rrect(w: float, h: float, r: float, fill: Optional[str], stroke: Optional[str] = None,
          stroke_w: float = 1.0, stroke_top: Optional[str] = None, stroke_bottom: Optional[str] = None,
          bottom_w: float = 1.0, bg: Optional[str] = None, corners=(True, True, True, True),
          fill_alpha: float = 1.0) -> Image.Image:
    """Rounded rectangle (logical size) rendered at device scale — see :class:`ShapeStyle`."""
    return plate(w, h, ShapeStyle(r, fill, stroke, stroke_w, stroke_top, stroke_bottom, bottom_w, bg,
                                  tuple(corners), fill_alpha))


def _edge_px(style: ShapeStyle) -> int:
    """Output px from each side of a plate whose 4× pixels may differ from the plate's middle (corners,
    the shifted outlines of stroke_top / stroke_bottom) plus the reach of LANCZOS."""
    k = SS * Scale.factor
    zone = 2 * style.radius * k + max(style.stroke_w, style.bottom_w, 1.0) * k + 2
    return int(math.ceil(zone / SS)) + LANCZOS_REACH + 1


def _stretch(small: Image.Image, W: int, H: int, m: int) -> Image.Image:
    """``small`` is 2·m + 1 px wide and / or high; its middle column / row repeated up to W × H."""
    a = np.asarray(small)
    if a.shape[1] != W:
        a = np.concatenate([a[:, :m], np.repeat(a[:, m:m + 1], W - 2 * m, axis=1), a[:, -m:]], axis=1)
    if a.shape[0] != H:
        a = np.concatenate([a[:m], np.repeat(a[m:m + 1], H - 2 * m, axis=0), a[-m:]], axis=0)
    return Image.fromarray(np.ascontiguousarray(a), "RGBA")


def _reduce(im: Image.Image, W: int, H: int, full: Tuple[int, int]) -> Image.Image:
    """LANCZOS reduction of a 4× RGBA drawing to W × H with Pillow's pass order for a ``full`` size image.

    Pillow runs the vertical pass first when the height shrinks more than twice the width does, and the
    8-bit image between the passes is rounded, so a part of a plate gets exactly the pixels of the whole
    plate only with the same order."""
    fw, fh = full
    vertical_first = (fh * SS - fh) > (fw * SS - fw) * 2
    a = im.convert("RGBa")
    if vertical_first:
        a = a.resize((W * SS, H), Image.Resampling.LANCZOS).resize((W, H), Image.Resampling.LANCZOS)
    else:
        a = a.resize((W, H * SS), Image.Resampling.LANCZOS).resize((W, H), Image.Resampling.LANCZOS)
    return a.convert("RGBA")


def plate(w: float, h: float, style: ShapeStyle) -> Image.Image:
    """Rounded plate (logical size) at device scale; remark 96: a large one is drawn 2·m + 1 px wide / high
    and its straight middle repeated (the same pixels as drawing it whole)."""
    W, H = max(1, int(round(_dev(w)))), max(1, int(round(_dev(h))))
    m = _edge_px(style)
    Ws, Hs = min(W, 2 * m + 1), min(H, 2 * m + 1)
    small = _plate_px(Ws, Hs, style, (W, H))
    return small if (Ws, Hs) == (W, H) else _stretch(small, W, H, m)


def _plate_px(W: int, H: int, style: ShapeStyle, whole: Tuple[int, int]) -> Image.Image:
    """The 4× drawing of a plate of W × H device px (the 1.0 rrect)."""
    fill, stroke, stroke_w = style.fill, style.stroke, style.stroke_w
    stroke_top, stroke_bottom, bottom_w = style.stroke_top, style.stroke_bottom, style.bottom_w
    bg, corners, fill_alpha = style.bg, style.corners, style.fill_alpha
    big = (W * SS, H * SS)
    k = SS * Scale.factor
    R = style.radius * k
    base = (0, 0, 0, 0) if bg is None else rgba(bg)
    im = Image.new("RGBA", big, base)

    def shape(draw, box, rad, color):
        x0, y0, x1, y1 = box
        if rad <= 0:
            draw.rectangle(box, fill=color)
            return
        draw.rounded_rectangle(box, radius=rad, fill=color, corners=corners)

    def layer(box, rad, color):
        m = Image.new("L", big, 0)
        shape(ImageDraw.Draw(m), box, rad, 255)
        col = Image.new("RGBA", big, color)
        return m, col

    full = (0, 0, big[0] - 1, big[1] - 1)
    if stroke:
        sw = stroke_w * k
        m, col = layer(full, R, rgba(stroke))
        im.paste(col, (0, 0), m)
        if stroke_bottom:
            # outline minus the outline shifted up by bottom_w -> bottom crescent
            bw = bottom_w * k
            m2 = Image.new("L", big, 0)
            shape(ImageDraw.Draw(m2), (0, -bw, big[0] - 1, big[1] - 1 - bw), R, 255)
            crescent = Image.composite(Image.new("L", big, 0), m, m2)
            im.paste(Image.new("RGBA", big, rgba(stroke_bottom)), (0, 0), crescent)
        if stroke_top:
            m3 = Image.new("L", big, 0)
            shape(ImageDraw.Draw(m3), (0, k, big[0] - 1, big[1] - 1 + k), R, 255)
            crescent = Image.composite(Image.new("L", big, 0), m, m3)
            im.paste(Image.new("RGBA", big, rgba(stroke_top)), (0, 0), crescent)
        inner = (sw, sw, big[0] - 1 - sw, big[1] - 1 - sw)
        if fill:
            m, col = layer(inner, max(0, R - sw), rgba(fill, fill_alpha))
            if fill_alpha < 1 or bg is None:
                # punch the inside first so a translucent fill does not show the stroke colour
                hole = Image.new("RGBA", big, base)
                im.paste(hole, (0, 0), m)
                im.alpha_composite(Image.composite(col, Image.new("RGBA", big, (0, 0, 0, 0)), m))
            else:
                im.paste(col, (0, 0), m)
        else:
            m, _ = layer(inner, max(0, R - sw), (0, 0, 0, 0))
            im.paste(Image.new("RGBA", big, base), (0, 0), m)
    elif fill:
        m, col = layer(full, R, rgba(fill, fill_alpha))
        if bg is None or fill_alpha < 1:
            im.alpha_composite(Image.composite(col, Image.new("RGBA", big, (0, 0, 0, 0)), m))
        else:
            im.paste(col, (0, 0), m)
    return _reduce(im, W, H, whole)


def triangle(w: float, h: float, color: str, bg: str, up: bool = True) -> Image.Image:
    """Remark 79: the small filled arrow of the Win11 scrollbar (logical w × h), slightly rounded tips."""
    W, H = max(1, int(round(_dev(w)))), max(1, int(round(_dev(h))))
    big = (W * SS, H * SS)
    m = Image.new("L", big, 0)
    d = ImageDraw.Draw(m)
    x0, x1, y0, y1 = 0, big[0] - 1, 0, big[1] - 1
    pts = [((x0 + x1) / 2, y0), (x1, y1), (x0, y1)] if up else [(x0, y0), (x1, y0), ((x0 + x1) / 2, y1)]
    d.polygon(pts, fill=255)
    m = m.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))     # soften the tips
    im = Image.new("RGBA", big, rgba(bg))
    im.paste(Image.new("RGBA", big, rgba(color)), (0, 0), m)
    return im.resize((W, H), Image.LANCZOS)


def shadow_box(w: float, h: float, r: float, layers: Sequence[Tuple[float, float, float]],
               pad: float) -> Image.Image:
    """Soft shadow (RGBA, black with alpha) for a w×h rounded box, image padded by ``pad`` on all sides.
    ``layers`` = [(offset_y, blur_radius, alpha), ...] like CSS box-shadow."""
    W, H = int(round(_dev(w + 2 * pad))), int(round(_dev(h + 2 * pad)))
    acc = np.zeros((H, W), dtype=np.float32)
    for oy, blur, a in layers:
        m = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(m)
        x0, y0 = _dev(pad), _dev(pad + oy)
        d.rounded_rectangle((x0, y0, x0 + _dev(w) - 1, y0 + _dev(h) - 1), radius=_dev(r), fill=int(255 * a))
        if blur > 0:
            m = m.filter(ImageFilter.GaussianBlur(_dev(blur) / 2))
        mf = np.asarray(m, dtype=np.float32)
        acc = acc + mf * (1 - acc / 255.0)
    acc = Image.fromarray(np.clip(acc, 0, 255).astype("uint8"), "L")
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.putalpha(acc)
    return out


def circle(d: float, fill: Optional[str], stroke: Optional[str] = None, stroke_w: float = 1.0,
           bg: Optional[str] = None, fill_alpha: float = 1.0) -> Image.Image:
    return rrect(d, d, d / 2, fill, stroke, stroke_w, bg=bg, fill_alpha=fill_alpha)


@functools.lru_cache(maxsize=256)
def _icon_mask(name: str) -> Optional[Image.Image]:
    p = ASSETS / "icons" / f"{name}.png"
    if not p.exists():
        log.warning("icon %s missing", name)
        return None
    im = Image.open(p).convert("RGBA")
    return im


def icon(name: str, size: float, color: Optional[str], bg: Optional[str] = None) -> Image.Image:
    """Tinted glyph ``size`` logical px (square)."""
    D = max(1, int(round(_dev(size))))
    src = _icon_mask(name)
    if src is None:
        return Image.new("RGBA", (D, D), (0, 0, 0, 0))
    if color is None:  # coloured asset
        im = src.resize((D, D), Image.Resampling.LANCZOS)
    else:
        a = src.getchannel("A").resize((D, D), Image.Resampling.LANCZOS)
        im = Image.new("RGBA", (D, D), rgba(color))
        im.putalpha(a)
    if bg is not None:
        base = Image.new("RGBA", (D, D), rgba(bg))
        base.alpha_composite(im)
        return base
    return im


def toggle(on: bool, accent: str, off_fill: str, off_stroke: str, off_knob: str, on_knob: str,
           bg: str, hover: bool = False, disabled: bool = False, dis_color: str = "#C0C0C0") -> Image.Image:
    """Win11 toggle 40×20: one round knob 12×12 (left 4 / top 3 off, left 22 on)."""
    W, H = 40, 20
    k = SS * Scale.factor
    big = (int(round(W * k)), int(round(H * k)))
    im = Image.new("RGBA", big, rgba(bg))
    d = ImageDraw.Draw(im)
    if disabled:
        d.rounded_rectangle((0, 0, big[0] - 1, big[1] - 1), radius=10 * k, fill=rgba(off_fill),
                            outline=rgba(dis_color), width=int(round(1 * k)))
        kc = dis_color
        cx = 10 if not on else 30
    elif on:
        d.rounded_rectangle((0, 0, big[0] - 1, big[1] - 1), radius=10 * k, fill=rgba(accent))
        kc = on_knob
        cx = 28
    else:
        d.rounded_rectangle((0, 0, big[0] - 1, big[1] - 1), radius=10 * k, fill=rgba(off_fill),
                            outline=rgba(off_stroke), width=int(round(1 * k)))
        kc = off_knob
        cx = 10
    kr = 7 if hover else 6
    cy = 10
    d.ellipse(((cx - kr) * k, (cy - kr) * k, (cx + kr) * k, (cy + kr) * k), fill=rgba(kc))
    return im.resize((int(round(W * Scale.factor)), int(round(H * Scale.factor))), Image.Resampling.LANCZOS)


def radio(selected: bool, accent: str, dot: str, off_fill: str, off_stroke: str, bg: str,
          hover: bool = False) -> Image.Image:
    """Win11 radio 20 px: selected = accent disc with a 10 px dot (12 on hover)."""
    D = 20
    k = SS * Scale.factor
    n = int(round(D * k))
    im = Image.new("RGBA", (n, n), rgba(bg))
    d = ImageDraw.Draw(im)
    if selected:
        d.ellipse((0, 0, n - 1, n - 1), fill=rgba(accent))
        r = (6 if hover else 5) * k
        c = n / 2
        d.ellipse((c - r, c - r, c + r, c + r), fill=rgba(dot))
    else:
        d.ellipse((0, 0, n - 1, n - 1), fill=rgba(off_stroke))
        w = 1 * k
        d.ellipse((w, w, n - 1 - w, n - 1 - w), fill=rgba(off_fill))
    return im.resize((int(round(D * Scale.factor)),) * 2, Image.Resampling.LANCZOS)


def checkbox(checked: bool, accent: str, tick: str, off_fill: str, off_stroke: str, bg: str) -> Image.Image:
    D = 20
    if checked:
        im = rrect(D, D, 4, accent, bg=bg)
        t = icon("tick", 12, tick)
        o = int(round(4 * Scale.factor))
        im.alpha_composite(t, (o, o))
        return im
    return rrect(D, D, 4, off_fill, off_stroke, 1, bg=bg)


def dashed_rrect(w: float, h: float, r: float, color: str, width: float = 1.5, dash: float = 4,
                 gap: float = 4) -> Image.Image:
    """Dashed rounded outline (transparent inside), path length based dashes.

    Remark 96: a large outline is drawn as four 4× bands along its sides (top, bottom, left, right), each a
    little wider than the outline and its corners plus the reach of LANCZOS; the inside stays empty."""
    k = SS * Scale.factor
    W, H = int(round(w * Scale.factor)), int(round(h * Scale.factor))
    lw = width * k
    R = r * k
    segments = _dash_segments(W * SS, H * SS, lw, R, dash * k, gap * k)
    T = int(math.ceil((R + lw + 2) / SS)) + LANCZOS_REACH + 1          # band, output px
    if 2 * T + 1 >= min(W, H):
        return _dash_band(segments, lw, color, 0, 0, W, H, (W, H))
    E = LANCZOS_REACH
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    full = (W, H)
    out.paste(_dash_band(segments, lw, color, 0, 0, W, T + E, full).crop((0, 0, W, T)), (0, 0))
    out.paste(_dash_band(segments, lw, color, 0, H - T - E, W, T + E, full).crop((0, E, W, T + E)), (0, H - T))
    side_h = H - 2 * T
    out.paste(_dash_band(segments, lw, color, 0, T - E, T + E, side_h + 2 * E, full).crop((0, E, T, E + side_h)),
              (0, T))
    out.paste(_dash_band(segments, lw, color, W - T - E, T - E, T + E, side_h + 2 * E, full)
              .crop((E, E, T + E, E + side_h)), (W - T, T))
    return out


def _dash_segments(bw: int, bh: int, lw: float, R: float, seg_on: float, seg_off: float):
    """Dash polylines (4× px) along the rounded outline of a bw × bh box, inset by half the line width."""
    inset = lw / 2
    x0, y0, x1, y1 = inset, inset, bw - inset, bh - inset
    # build the path as points
    pts = []

    def arc(cx, cy, a0, a1):
        n = 24
        for i in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * i / n)
            pts.append((cx + R * math.cos(a), cy + R * math.sin(a)))
    pts.append((x0 + R, y0)); pts.append((x1 - R, y0)); arc(x1 - R, y0 + R, -90, 0)
    pts.append((x1, y1 - R)); arc(x1 - R, y1 - R, 0, 90)
    pts.append((x0 + R, y1)); arc(x0 + R, y1 - R, 90, 180)
    pts.append((x0, y0 + R)); arc(x0 + R, y0 + R, 180, 270)
    # walk the path
    segments = []
    on, remain = True, seg_on
    cur = [pts[0]]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        L = math.hypot(bx - ax, by - ay)
        t = 0.0
        while L - t > 1e-6:
            step = min(remain, L - t)
            t2 = t + step
            px, py = ax + (bx - ax) * t2 / L, ay + (by - ay) * t2 / L
            if on:
                cur.append((px, py))
            remain -= step
            t = t2
            if remain <= 1e-6:
                if on and len(cur) > 1:
                    segments.append(cur)
                on = not on
                remain = seg_on if on else seg_off
                cur = [(px, py)]
    if on and len(cur) > 1:
        segments.append(cur)
    return segments


def _dash_band(segments, lw: float, color: str, x: int, y: int, w: int, h: int,
               full: Tuple[int, int]) -> Image.Image:
    """Output px (x, y, w, h) of the dashed outline: its 4× pixels drawn and LANCZOS-reduced."""
    im = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    col = rgba(color)
    ox, oy = x * SS, y * SS
    for seg in segments:
        d.line([(px - ox, py - oy) for px, py in seg] if (ox or oy) else seg, fill=col, width=int(round(lw)),
               joint="curve")
    return _reduce(im, w, h, full)


def checker(w: int, h: int, cell: int, c1: str, c2: str) -> Image.Image:
    """Checkerboard in device px."""
    import numpy as np
    yy, xx = np.mgrid[0:h, 0:w]
    m = ((xx // cell + yy // cell) % 2).astype(bool)
    a, b = np.array(rgb(c1), dtype=np.uint8), np.array(rgb(c2), dtype=np.uint8)
    arr = np.where(m[..., None], b, a)
    return Image.fromarray(arr.astype("uint8"), "RGB").convert("RGBA")
