"""Scrollable viewport with a Notepad-like overlay scrollbar (remark 79: Windows 11 behaviour)."""
from __future__ import annotations

import logging
import sys
import tkinter as tk
from typing import Callable

from ui import gfx
from ui.theme import S, Scale, Theme, blend
from ui.widgets.base import Control

log = logging.getLogger(__name__)


# Remark 79: the Windows 11 / Notepad overlay scrollbar (stage_0_common «Полоса прокрутки»).
# At rest a rounded 2 px line 4 px from the right edge, no arrows, no track.  When the pointer is over the bar
# zone it widens smoothly (EXPAND_MS) to a 6 px thumb with small arrows at both ends and a faint track; about
# 1 s (COLLAPSE_DELAY_MS) after the pointer leaves it narrows back the same way.  Sizes as in Notepad
# (/workspace/feedback/scroll_notepad_*.png): track 12 px, thumb 6 px, arrows 8 × 6 px in the thumb colour.
ZONE_W = 12.0
REST_W, WIDE_W = 2.0, 6.0          # thumb width at rest / widened
REST_GAP, WIDE_GAP = 4.0, 3.0      # thumb gap to the right edge
END, ARROW_ZONE = 4.0, 18.0        # thumb travel margin at rest / with the arrows shown
TRACK_PAD = 2.0                    # track inset at the top and bottom
ARROW_W, ARROW_H, ARROW_TOP = 8.0, 6.0, 7.0
EXPAND_MS, STEPS = 120, 6
COLLAPSE_DELAY_MS = 1000
STEP_PX = 48.0                     # one arrow click = one wheel notch
REPEAT_FIRST_MS, REPEAT_MS = 400, 50


def bar_geometry(right: float, top: float, height: float, t: float, view: float, content: float, scroll: float,
                 rest_gap: float = REST_GAP, wide_gap: float = WIDE_GAP):
    """Track, thumb and arrows of a vertical bar whose zone ends at ``right`` (logical px, ``t`` = widening)."""
    if content <= view or height <= 0:
        return None
    m = END + (ARROW_ZONE - END) * t
    track_len = height - 2 * m
    if track_len <= 0:
        return None
    th = max(24.0, track_len * view / content)
    rng = content - view
    ty = top + m + (track_len - th) * (scroll / rng)
    w = REST_W + (WIDE_W - REST_W) * t
    gap = rest_gap + (wide_gap - rest_gap) * t
    cx = right - ZONE_W / 2
    return {
        "thumb": (right - gap - w, ty, w, th),
        "track": (right - ZONE_W, top + TRACK_PAD, ZONE_W, height - 2 * TRACK_PAD),
        "up": (cx - ARROW_W / 2, top + ARROW_TOP, ARROW_W, ARROW_H),
        "down": (cx - ARROW_W / 2, top + height - ARROW_TOP - ARROW_H, ARROW_W, ARROW_H),
        "travel": track_len - th,
        "arrows": t >= 0.5,
    }


def _tr(r):
    x, y, w, h = r
    return (y, x, h, w)


def hbar_geometry(bottom: float, left: float, width: float, t: float, view: float, content: float, scroll: float,
                  rest_gap: float = REST_GAP, wide_gap: float = WIDE_GAP):
    """Remark 86: the same bar lying on its side (the photo strip): the zone ends at ``bottom``, the arrows are
    «left» / «right».  Rects are (x, y, w, h) in the horizontal frame."""
    g = bar_geometry(bottom, left, width, t, view, content, scroll, rest_gap, wide_gap)
    if g is None:
        return None
    return {"thumb": _tr(g["thumb"]), "track": _tr(g["track"]), "left": _tr(g["up"]), "right": _tr(g["down"]),
            "travel": g["travel"], "arrows": g["arrows"], "horizontal": True}


def hbar_zone(g, x: float, left: float, width: float) -> str:
    """Which part of a horizontal bar is under ``x``: left | right | thumb | track."""
    if g["arrows"]:
        if x < left + ARROW_ZONE:
            return "left"
        if x > left + width - ARROW_ZONE:
            return "right"
    tx, _, tw, _ = g["thumb"]
    return "thumb" if tx <= x <= tx + tw else "track"


def bar_zone(g, y: float, top: float, height: float) -> str:
    """Which part of the bar is under ``y``: up | down | thumb | track."""
    if g["arrows"]:
        if y < top + ARROW_ZONE:
            return "up"
        if y > top + height - ARROW_ZONE:
            return "down"
    _, ty, _, th = g["thumb"]
    return "thumb" if ty <= y <= ty + th else "track"


def draw_bar(box, g, t: float, under: str, put) -> None:
    """Paint ``g`` (bar_geometry) on ``box``: ``put(x, y, key, factory)`` places a cached image; ``under`` is
    the colour below the bar."""
    horizontal = g.get("horizontal", False)
    if t > 0:
        track = blend(Theme.c("scroll_track"), t, under)
        x, y, w, h = g["track"]
        put(x, y, ("sb_track", round(w, 2), round(h, 2), track, under),
            lambda: gfx.rrect(w, h, min(w, h) / 2, track, bg=under))
        if g["arrows"]:
            col = blend(Theme.c("scroll_thumb"), min(1.0, (t - 0.5) * 2), track)
            for name in (("left", "right") if horizontal else ("up", "down")):
                ax, ay, aw, ah = g[name]
                if horizontal:      # the 8 × 6 arrow turned on its side (6 × 8), pointing left / right
                    put(ax, ay, ("sb_arrow", name, col, track),
                        lambda name=name, aw=aw, ah=ah: gfx.triangle(ah, aw, col, track, True).rotate(
                            90 if name == "left" else -90, expand=True))
                else:
                    put(ax, ay, ("sb_arrow", name, col, track),
                        lambda name=name, aw=aw, ah=ah: gfx.triangle(aw, ah, col, track, name == "up"))
        under = track
    x, y, w, h = g["thumb"]
    thumb = Theme.c("scroll_thumb")
    put(x, y, ("sb_thumb", round(w, 2), round(h, 2), thumb, under),
        lambda: gfx.rrect(w, h, min(w, h) / 2, thumb, bg=under))


class Widening:
    """The smooth 2 → 6 px animation with the 1 s delay before narrowing (shared by the bars)."""

    def __init__(self, widget, redraw: Callable[[], None], busy: Callable[[], bool]):
        self.widget = widget
        self.redraw = redraw
        self.busy = busy           # True while the pointer is on the bar or the thumb is dragged
        self.t = 0.0
        self.target = 0.0
        self._anim = self._delay = None

    def _cancel(self, attr):
        job = getattr(self, attr)
        if job is not None:
            try:
                self.widget.after_cancel(job)
            except tk.TclError:
                log.debug("after_cancel failed", exc_info=True)
            setattr(self, attr, None)

    def expand(self):
        self._cancel("_delay")
        self._go(1.0)

    def collapse_later(self):
        self._cancel("_delay")
        self._delay = self.widget.after(COLLAPSE_DELAY_MS, self._collapse_now)

    def _collapse_now(self):
        self._delay = None
        if not self.busy():
            self._go(0.0)

    def _go(self, target: float):
        self.target = target
        if self._anim is None and abs(self.t - target) > 1e-6:
            self._anim = self.widget.after(EXPAND_MS // STEPS, self._tick)

    def _tick(self):
        self._anim = None
        step = 1.0 / STEPS
        self.t = min(self.target, self.t + step) if self.t < self.target else max(self.target, self.t - step)
        if abs(self.t - self.target) < 1e-3:
            self.t = self.target
        self.redraw()
        if abs(self.t - self.target) > 1e-6:
            self._anim = self.widget.after(EXPAND_MS // STEPS, self._tick)

    def stop(self):
        self._cancel("_anim")
        self._cancel("_delay")


class BarMixin:
    """Remark 118 (audit A14): what the vertical bar of ScrollArea and the horizontal bar of the photo strip
    (ui/widgets/batch.py) have in common.  The class provides ``_geo()`` (None = nothing to scroll) and ``wide``."""

    @property
    def t(self) -> float:
        return self.wide.t

    def thumb_rect(self):
        """Test hook: (x, y, w, h) of the thumb in logical px."""
        g = self._geo()
        return g["thumb"] if g else None

    def arrows_shown(self) -> bool:
        """Test hook: the arrow buttons are drawn."""
        g = self._geo()
        return bool(g and g["arrows"])

    def _on_enter(self, e=None):
        super()._on_enter(e)
        if self._geo() is not None:
            self.wide.expand()


class ScrollBar(BarMixin, Control):
    """Overlay bar of a ScrollArea («Параметры», «Справка», screen 2, screen 3, window 21): drag the thumb, click the
    track to page, the arrows step (and repeat while held), the wheel works over the whole page."""
    W = ZONE_W

    def __init__(self, master, area: "ScrollArea"):
        super().__init__(master, bg=area.bg_token)
        self.area = area
        self._drag_y = None
        self._repeat = None
        self.wide = Widening(self, self.redraw, lambda: self.hover or self._drag_y is not None)
        self.bind("<B1-Motion>", self._drag)

    def _geo(self):
        a = self.area
        return bar_geometry(self.lw, 0.0, self.lh, self.wide.t, a.view_h, a.content_h, a.scroll)

    # mouse ---------------------------------------------------------------------
    def _on_leave(self, e=None):
        self.hover = False
        self.pressed = False
        if self._drag_y is None:
            self.wide.collapse_later()
        self._stop_repeat()

    def _on_press(self, e=None):
        super()._on_press(e)
        g = self._geo()
        if not g or e is None:
            return
        y = e.y / Scale.factor
        zone = bar_zone(g, y, 0.0, self.lh)
        self._drag_y = None
        if zone == "thumb":
            self._drag_y = (y, self.area.scroll)
        elif zone in ("up", "down"):
            self._step(-1 if zone == "up" else 1, first=True)
        else:  # page jump
            self.area.scroll_by((self.area.view_h - 40) * (1 if y > g["thumb"][1] else -1))

    def _step(self, d: int, first: bool = False):
        self.area.scroll_by(d * STEP_PX)
        self._repeat = self.after(REPEAT_FIRST_MS if first else REPEAT_MS, lambda: self._step(d))

    def _stop_repeat(self):
        if self._repeat is not None:
            try:
                self.after_cancel(self._repeat)
            except tk.TclError:
                log.debug("after_cancel failed", exc_info=True)
            self._repeat = None

    def _drag(self, e):
        if not self._drag_y:
            return
        g = self._geo()
        if not g:
            return
        y0, s0 = self._drag_y
        rng = self.area.content_h - self.area.view_h
        self.area.scroll_to(s0 + (e.y / Scale.factor - y0) * rng / max(1.0, g["travel"]))

    def _on_release(self, e=None):
        self._stop_repeat()
        was_drag = self._drag_y is not None
        self._drag_y = None
        super()._on_release(None)
        if was_drag and e is not None and not (0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height()):
            self.hover = False
            self.wide.collapse_later()

    def draw(self):
        g = self._geo()
        if g:
            draw_bar(self, g, self.wide.t, Theme.c(self.bg_token),
                     lambda x, y, key, f: self.put_cached(x, y, key, f))


class ScrollArea(tk.Frame):
    """Clip frame; children go into ``self.inner`` which moves with the scroll position."""

    def __init__(self, master, bg: str = "bg", on_scroll: Callable[[], None] = None):
        super().__init__(master, bd=0, highlightthickness=0, bg=Theme.c(bg))
        self.bg_token = bg
        self.inner = tk.Frame(self, bd=0, highlightthickness=0, bg=Theme.c(bg))
        self.bar = ScrollBar(master, self)
        self.scroll = 0.0
        self.content_h = 0.0
        self.view_h = 0.0
        self.view_w = 0.0
        self.x = self.y = 0.0
        self.on_scroll = on_scroll
        self._bound = False
        self.in_popup = False          # True for an area inside an in-window dialog (help, remarks 24–25)

    def refresh_bg(self):
        self.configure(bg=Theme.c(self.bg_token))
        self.inner.configure(bg=Theme.c(self.bg_token))

    def geom(self, x, y, w, h, content_h):
        self.x, self.y, self.view_w, self.view_h = x, y, w, h
        self.content_h = content_h
        X, Y = S(x), S(y)
        self.place(x=X, y=Y, width=S(x + w) - X, height=S(y + h) - Y)
        self.scroll = max(0.0, min(self.scroll, max(0.0, content_h - h)))
        self._place_inner()
        self.bar.geom(x + w - ScrollBar.W, y, ScrollBar.W, h)
        self.bar.redraw()               # content height may change without a size change
        self.bar.lift()

    def _place_inner(self):
        self.inner.place(x=0, y=-S(self.scroll), width=S(self.view_w), height=S(max(self.content_h, self.view_h)))

    def scroll_to(self, v):
        v = max(0.0, min(v, max(0.0, self.content_h - self.view_h)))
        if abs(v - self.scroll) < 0.01:
            return
        self.scroll = v
        self._place_inner()
        self.bar.redraw()
        if self.on_scroll:
            self.on_scroll()

    def scroll_by(self, d):
        self.scroll_to(self.scroll + d)

    def hide(self):
        self.place_forget()
        self.bar.hide()
        self.unbind_wheel()

    # wheel -------------------------------------------------------------------
    # one global dispatcher: the wheel scrolls the area under the pointer
    _areas: list = []
    _global_bound = set()

    def bind_wheel(self):
        if self not in ScrollArea._areas:
            ScrollArea._areas.append(self)
        root = self._tk_root()
        key = str(root)
        if key in ScrollArea._global_bound:
            return
        ScrollArea._global_bound.add(key)
        if sys.platform.startswith("linux"):
            root.bind_all("<Button-4>", lambda e: ScrollArea._dispatch(e, 120), add="")
            root.bind_all("<Button-5>", lambda e: ScrollArea._dispatch(e, -120), add="")
        else:
            root.bind_all("<MouseWheel>", lambda e: ScrollArea._dispatch(e, e.delta), add="")

    def _tk_root(self):
        return self.nametowidget(".")

    def unbind_wheel(self):
        if self in ScrollArea._areas:
            ScrollArea._areas.remove(self)

    @classmethod
    def _dispatch(cls, e, delta):
        try:
            w = e.widget.winfo_containing(e.x_root, e.y_root)
        except (tk.TclError, AttributeError, KeyError):
            log.debug("ScrollArea._dispatch: (tk.TclError, AttributeError, KeyError) caught", exc_info=True)   # remark 81
            w = None
        while w is not None:
            handler = getattr(w, "wheel_handler", None)   # stage 4: the photo strip scrolls sideways
            if callable(handler):
                handler(delta)
                return
            for a in cls._areas:
                if w is a or w is a.bar:
                    a._wheel(delta)
                    return
            w = getattr(w, "master", None)

    def _wheel(self, delta):
        from ui.widgets.overlay import Popup     # remark 114: lazy — overlay imports this module
        if not self.in_popup and Popup.current is not None and self.winfo_toplevel() is Popup.current.root:
            return
        self.scroll_by(-delta / 120 * 48)
