"""Anti-aliased rendering of Win11 shapes with PIL (4x supersampling + LANCZOS), cached.

Every function returns a PIL image in *device* pixels for the current scale; ``photo()``
wraps it into a cached ``ImageTk.PhotoImage``.
"""
from __future__ import annotations

import functools
import logging
import math
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageTk

from ui.theme import Scale, rgb

log = logging.getLogger(__name__)

SS = 4  # supersampling
ASSETS = Path(__file__).resolve().parents[1] / "assets"
_photo_cache: Dict[tuple, ImageTk.PhotoImage] = {}


def clear_cache() -> None:
    _photo_cache.clear()
    _icon_mask.cache_clear()


def photo(key: tuple, factory) -> ImageTk.PhotoImage:
    k = key + (Scale.factor,)
    p = _photo_cache.get(k)
    if p is None:
        if len(_photo_cache) > 3000:
            _photo_cache.clear()
        p = ImageTk.PhotoImage(factory())
        _photo_cache[k] = p
    return p


def rgba(c: str, a: float = 1.0) -> Tuple[int, int, int, int]:
    r, g, b = rgb(c)
    return r, g, b, int(round(a * 255))


def _dev(v: float) -> float:
    return v * Scale.factor


def rrect(w: float, h: float, r: float, fill: Optional[str], stroke: Optional[str] = None,
          stroke_w: float = 1.0, stroke_top: Optional[str] = None, stroke_bottom: Optional[str] = None,
          bottom_w: float = 1.0, bg: Optional[str] = None, corners=(True, True, True, True),
          fill_alpha: float = 1.0) -> Image.Image:
    """Rounded rectangle (logical size) rendered at device scale.

    ``stroke_bottom`` paints the lower ``bottom_w`` px of the outline in another colour
    (Win11 elevation border); ``stroke_top`` the upper 1 px. ``corners`` = (tl, tr, br, bl)."""
    W, H = max(1, int(round(_dev(w)))), max(1, int(round(_dev(h))))
    big = (W * SS, H * SS)
    k = SS * Scale.factor
    R = r * k
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
        elif bg is not None or True:
            m, _ = layer(inner, max(0, R - sw), (0, 0, 0, 0))
            im.paste(Image.new("RGBA", big, base), (0, 0), m)
    elif fill:
        m, col = layer(full, R, rgba(fill, fill_alpha))
        if bg is None or fill_alpha < 1:
            im.alpha_composite(Image.composite(col, Image.new("RGBA", big, (0, 0, 0, 0)), m))
        else:
            im.paste(col, (0, 0), m)
    return im.resize((W, H), Image.Resampling.LANCZOS)


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
    """Dashed rounded outline (transparent inside), path length based dashes."""
    k = SS * Scale.factor
    W, H = int(round(w * Scale.factor)), int(round(h * Scale.factor))
    big = (W * SS, H * SS)
    im = Image.new("RGBA", big, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lw = width * k
    inset = lw / 2
    x0, y0, x1, y1 = inset, inset, big[0] - inset, big[1] - inset
    R = r * k
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
    seg_on, seg_off = dash * k, gap * k
    pos, on, remain = 0.0, True, seg_on
    col = rgba(color)
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
                    d.line(cur, fill=col, width=int(round(lw)), joint="curve")
                on = not on
                remain = seg_on if on else seg_off
                cur = [(px, py)]
    if on and len(cur) > 1:
        d.line(cur, fill=col, width=int(round(lw)), joint="curve")
    return im.resize((W, H), Image.Resampling.LANCZOS)


def checker(w: int, h: int, cell: int, c1: str, c2: str) -> Image.Image:
    """Checkerboard in device px."""
    import numpy as np
    yy, xx = np.mgrid[0:h, 0:w]
    m = ((xx // cell + yy // cell) % 2).astype(bool)
    a, b = np.array(rgb(c1), dtype=np.uint8), np.array(rgb(c2), dtype=np.uint8)
    arr = np.where(m[..., None], b, a)
    return Image.fromarray(arr.astype("uint8"), "RGB").convert("RGBA")
