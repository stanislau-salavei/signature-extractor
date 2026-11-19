"""Remark 92: window size between launches (no Tk).

The window remembers its normal (not maximized) client size and whether it was maximized — in logical
pixels (at 100 % scale), so another display scale or monitor does not change the size.  The position is
not remembered: the window always opens centred in the work area.  A remembered size larger than the
current screen is reduced to fit; it is never smaller than the minimum window (if the screen allows)."""
from __future__ import annotations

from typing import Any, Optional, Tuple

DEFAULT_SIZE = (1280, 768)        # client area of the mockups (1280 × 800 with the 32 px title bar)
MIN_SIZE = (1024, 648)


def parse_saved(value: Any) -> Optional[Tuple[int, int, bool]]:
    """settings «window» → (w, h, maximized), or None for a missing / damaged value."""
    if not isinstance(value, dict):
        return None
    w, h, m = value.get("w"), value.get("h"), value.get("maximized", False)
    ok = all(isinstance(v, (int, float)) and not isinstance(v, bool) and 100 <= v <= 20000 for v in (w, h))
    if not ok:
        return None
    return int(round(w)), int(round(h)), bool(m) if isinstance(m, bool) else False


def to_saved(w: float, h: float, maximized: bool) -> dict:
    return {"w": int(round(w)), "h": int(round(h)), "maximized": bool(maximized)}


def fit_size(size: Tuple[float, float], avail: Tuple[float, float],
             minimum: Tuple[int, int] = MIN_SIZE) -> Tuple[int, int]:
    """Clamp a client size (logical px) to the available client area of the screen: not larger than the
    screen, not smaller than the minimum — unless the screen itself is smaller than the minimum."""
    out = []
    for v, a, lo in zip(size, avail, minimum, strict=True):
        a = max(1, int(a))
        out.append(int(max(min(lo, a), min(int(round(v)), a))))
    return out[0], out[1]


def min_size_for(avail: Tuple[float, float], minimum: Tuple[int, int] = MIN_SIZE) -> Tuple[int, int]:
    """Minimum window size that still fits the screen (a small screen lowers the minimum)."""
    return min(minimum[0], max(1, int(avail[0]))), min(minimum[1], max(1, int(avail[1])))


def initial_geometry(saved: Any, area_px: Tuple[int, int, int, int], frame_px: Tuple[int, int],
                     scale: float, default: Tuple[int, int] = DEFAULT_SIZE,
                     minimum: Tuple[int, int] = MIN_SIZE):
    """Start-up geometry.

    ``area_px`` — work area (left, top, width, height) in physical px, ``frame_px`` — what the title bar
    and borders add (dx, dy) in physical px, ``scale`` — window scale (1.25 at 125 %).
    Returns ``(w, h, x, y, maximized, min_w, min_h)``: client size and minimum in logical px, position of the
    outer window in physical px (centred)."""
    scale = scale if scale and scale > 0 else 1.0
    left, top, aw, ah = area_px
    fx, fy = frame_px
    avail = ((aw - fx) / scale, (ah - fy) / scale)
    p = parse_saved(saved)
    w0, h0, maximized = (p if p else (default[0], default[1], False))
    w, h = fit_size((w0, h0), avail, minimum)
    mw, mh = min_size_for(avail, minimum)
    outer_w, outer_h = round(w * scale) + fx, round(h * scale) + fy
    x = left + max(0, (aw - outer_w) // 2)
    y = top + max(0, (ah - outer_h) // 2)
    return w, h, int(x), int(y), maximized, mw, mh
