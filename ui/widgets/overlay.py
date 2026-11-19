"""In-window popups: menus, ComboBox lists, tooltips and content dialogs.

Tk cannot draw translucent shadows or anti-aliased corners over other widgets, so every
popup is a canvas laid over the window whose background is a snapshot of the window
area underneath (``ImageGrab``) with the shadow and the rounded panel composited by PIL.
No light squares behind rounded menus, no grey bar instead of the shadow.
"""
from __future__ import annotations

import logging
import math
import sys
import tkinter as tk
from typing import Callable, List, Optional, Sequence, Tuple

from PIL import Image, ImageGrab, ImageTk

from ui import gfx
from ui.theme import F, S, Scale, Theme, elide, text_width
from ui.widgets.base import Tooltip

log = logging.getLogger(__name__)

SHADOW_LIGHT = [(8, 16, 0.14), (0, 2, 0.10)]
SHADOW_DARK = [(8, 16, 0.26), (0, 2, 0.30)]
DIALOG_SHADOW = [(8, 16, 0.14), (24, 48, 0.18)]
TOOLTIP_SHADOW = [(4, 12, 0.22)]


def grab_window(root: tk.Misc, x: float = 0, y: float = 0, w: Optional[float] = None,
                h: Optional[float] = None) -> Image.Image:
    """Snapshot of the window client area (logical rect) in device px; theme bg on failure."""
    root.update_idletasks()
    W = root.winfo_width() if w is None else S(w)
    H = root.winfo_height() if h is None else S(h)
    X, Y = root.winfo_rootx() + S(x), root.winfo_rooty() + S(y)
    try:
        kw = {"all_screens": True} if sys.platform.startswith("win") else {}
        im = ImageGrab.grab(bbox=(X, Y, X + W, Y + H), **kw).convert("RGBA")
        if im.size != (W, H):
            im = im.resize((W, H))
        return im
    except Exception:
        log.debug("window snapshot failed, using plain background", exc_info=True)
        return Image.new("RGBA", (max(1, W), max(1, H)), gfx.rgba(Theme.c("bg")))


def widget_rect(root: tk.Misc, widget: tk.Misc) -> Tuple[float, float, float, float]:
    """Widget rectangle in logical px relative to the window client area."""
    root.update_idletasks()
    f = Scale.factor
    return ((widget.winfo_rootx() - root.winfo_rootx()) / f, (widget.winfo_rooty() - root.winfo_rooty()) / f,
            widget.winfo_width() / f, widget.winfo_height() / f)


def panel_image(backdrop: Image.Image, x: float, y: float, w: float, h: float, r: float, fill: str,
                stroke: str, shadow) -> Image.Image:
    """Composite a shadowed rounded panel onto a copy of the backdrop (all logical coords)."""
    out = backdrop.copy()
    pad = 40
    sh = gfx.shadow_box(w, h, r, shadow, pad)
    _paste_clip(out, sh, S(x - pad), S(y - pad))
    panel = gfx.rrect(w, h, r, fill, stroke)
    _paste_clip(out, panel, S(x), S(y))
    return out


def _paste_clip(dst: Image.Image, src: Image.Image, X: int, Y: int) -> None:
    sx0, sy0 = max(0, -X), max(0, -Y)
    sx1, sy1 = min(src.width, dst.width - X), min(src.height, dst.height - Y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    dst.alpha_composite(src.crop((sx0, sy0, sx1, sy1)), (X + sx0, Y + sy0))


class Popup:
    """Full-window canvas with a snapshot backdrop. Closes on outside click / Esc / resize."""

    current: Optional["Popup"] = None

    grab_over_next = False   # stage 5: the next popup keeps the open one in its backdrop (menu over a list)

    def __init__(self, app, on_close: Optional[Callable] = None):
        self.app = app
        self.root = app.root
        self.on_close = on_close
        if Popup.grab_over_next:
            Popup.grab_over_next = False
            self.backdrop = grab_window(self.root)
            Popup.close_current()
        else:
            Popup.close_current()
            self.backdrop = grab_window(self.root)
        self.cv = tk.Canvas(self.root, highlightthickness=0, bd=0, takefocus=1)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.cv.tk.call("raise", self.cv._w)
        self._imgs = []
        self.closed = False
        Popup.current = self
        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<ButtonPress-3>", self._press)
        self.cv.bind("<Motion>", self._motion)
        self.cv.bind("<Leave>", lambda e: self._motion(None))
        self.cv.bind("<ButtonRelease-1>", self._release)
        self.cv.bind("<MouseWheel>", self._wheel)
        self.cv.bind("<Button-4>", lambda e: self._wheel_delta(1))
        self.cv.bind("<Button-5>", lambda e: self._wheel_delta(-1))
        self.cv.bind("<Escape>", lambda e: self.close())
        self.cv.bind("<Up>", lambda e: self.key(-1))
        self.cv.bind("<Down>", lambda e: self.key(1))
        self.cv.bind("<Return>", lambda e: self.key(0))
        self.cv.focus_set()

    # geometry of the panel (logical)
    px = py = pw = ph = 0.0

    @classmethod
    def close_current(cls) -> None:
        if cls.current is not None:
            cls.current.close()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if Popup.current is self:
            Popup.current = None
        try:
            self.cv.destroy()
        except tk.TclError:
            log.debug("Popup.close: tk.TclError caught", exc_info=True)   # remark 81
        if self.on_close:
            self.on_close()

    def inside(self, e) -> bool:
        x, y = e.x / Scale.factor, e.y / Scale.factor
        return self.px <= x < self.px + self.pw and self.py <= y < self.py + self.ph

    def _press(self, e):
        if not self.inside(e):
            self.close()
            return
        self.press(e.x / Scale.factor - self.px, e.y / Scale.factor - self.py)

    def _release(self, e):
        if self.closed:
            return
        if self.inside(e):
            self.release(e.x / Scale.factor - self.px, e.y / Scale.factor - self.py)

    def _motion(self, e):
        if e is None or not self.inside(e):
            self.motion(None, None)
        else:
            self.motion(e.x / Scale.factor - self.px, e.y / Scale.factor - self.py)

    def _wheel(self, e):
        self._wheel_delta(1 if e.delta > 0 else -1)

    def _wheel_delta(self, d):
        self.wheel(d)

    # to override
    def press(self, x, y): pass
    def release(self, x, y): pass
    def motion(self, x, y): pass
    def wheel(self, d): pass
    def key(self, d): pass

    def show_base(self, x, y, w, h, r, fill="menu", stroke="menu_stroke"):
        self.px, self.py, self.pw, self.ph = x, y, w, h
        shadow = SHADOW_DARK if Theme.dark() else SHADOW_LIGHT
        img = panel_image(self.backdrop, x, y, w, h, r, Theme.c(fill), Theme.c(stroke), shadow)
        p = ImageTk.PhotoImage(img)
        self._imgs = [p]
        self.cv.delete("all")
        self.cv.create_image(0, 0, image=p, anchor="nw", tags="base")

    def put(self, x, y, img, tags=(), anchor="nw"):
        p = ImageTk.PhotoImage(img) if isinstance(img, Image.Image) else img
        self._imgs.append(p)
        return self.cv.create_image(S(self.px + x), S(self.py + y), image=p, anchor=anchor, tags=tags)

    def put_cached(self, x, y, key, factory, tags=(), anchor="nw"):
        """Remark 118 (audit B11): a static image from the gfx cache (no new PhotoImage per redraw)."""
        return self.put(x, y, gfx.photo(key, factory), tags=tags, anchor=anchor)

    def text(self, x, cy, s, px=14, color="text", tags=(), anchor="w", weight="normal"):
        return self.cv.create_text(S(self.px + x), S(self.py + cy), text=s, font=F(px, weight),
                                   fill=Theme.c(color), anchor=anchor, tags=tags)


class MenuItem:
    def __init__(self, text: str, command: Optional[Callable] = None, icon: Optional[str] = None,
                 disabled: bool = False):
        self.text, self.command, self.icon, self.disabled = text, command, icon, disabled



class MenuPopup(Popup):
    """Task-Manager-like menu: radius 8, items 36 / step 38, icons 16, gap 12, text 14."""

    def __init__(self, app, items: Sequence[Optional[MenuItem]], x: float, y: float,
                 align_right: bool = False, min_width: float = 160, on_close=None):
        super().__init__(app, on_close)
        self.items = list(items)
        has_icons = any(it and it.icon for it in self.items)
        tw = max((text_width(it.text, 14) for it in self.items if it), default=60)
        # item: padding 0 19 0 9 inside the 4 px menu padding; icon 16 + gap 12
        w = 1 + 4 + 9 + (16 + 12 if has_icons else 3) + tw + 19 + 4 + 1
        w = max(min_width, round(w + 0.4, 1))
        w = min(w, max(min_width, app.width() - 16))   # remark 35: never wider than the window (− 8 a side)
        self.rows: List[Tuple[float, Optional[MenuItem]]] = []
        cy = 1 + 2
        for it in self.items:
            if it is None:
                self.rows.append((cy, None))
                cy += 2 + 1 + 2
            else:
                self.rows.append((cy + 2, it))   # item top (2 px margin above)
                cy += 38
        h = cy + 2 + 1
        W, H = app.width(), app.height()
        if align_right:
            x = x - w
        x = max(8, min(x, W - w - 8))
        if y + h > H - 8:
            y = max(36, H - 8 - h)
        self.has_icons = has_icons
        self.hover_i = -1
        self.show_base(x, y, w, h, 8)
        self.draw_items()

    def draw_items(self):
        self.cv.delete("items")
        for i, (top, it) in enumerate(self.rows):
            if it is None:
                self.cv.create_rectangle(S(self.px + 1), S(self.py + top + 2), S(self.px + self.pw - 1),
                                         S(self.py + top + 3), fill=Theme.c("menu_sep"), width=0, tags="items")
                continue
            if i == self.hover_i and not it.disabled:
                hov, mbg = Theme.c("menu_hover"), Theme.c("menu")
                self.put_cached(5, top, ("rr", self.pw - 10, 36, 4, hov, None, mbg, ()),
                                lambda hov=hov, mbg=mbg: gfx.rrect(self.pw - 10, 36, 4, hov, bg=mbg), tags="items")
            color = "disabled" if it.disabled else "text"
            tx = 5 + 9
            if self.has_icons:
                if it.icon:
                    ic, icc = it.icon, Theme.c(color)
                    self.put_cached(tx, top + 10, ("ic", ic, 16, icc), lambda ic=ic, icc=icc: gfx.icon(ic, 16, icc),
                                    tags="items")
                tx += 16 + 12
            else:
                tx += 3
            room = self.pw - tx - 19 - 4 - 1
            self.text(tx, top + 18, elide(it.text, room, 14), 14, color, tags="items")

    def _row_at(self, y):
        for i, (top, it) in enumerate(self.rows):
            if it is not None and top <= y < top + 36:
                return i
        return -1

    def motion(self, x, y):
        i = -1 if y is None else self._row_at(y)
        if i != self.hover_i:
            self.hover_i = i
            self.draw_items()

    def release(self, x, y):
        i = self._row_at(y)
        if i >= 0:
            it = self.rows[i][1]
            if it and not it.disabled:
                self.close()
                if it.command:
                    self.root.after(1, it.command)


class ListPopup(Popup):
    """Win11 ComboBox list opened over the field: the selected item sits on the field."""

    ITEM_H, STEP, MAX_H, MIN_TOP = 36, 38, 392, 3

    def __init__(self, app, labels: Sequence[Optional[str]], selected: int, field: Tuple[float, float, float, float],
                 on_select: Callable[[int], None], min_width: float = 0, swatches=None, on_close=None,
                 context_fn: Optional[Callable[[int, float, float], None]] = None):
        super().__init__(app, on_close)
        self.labels = list(labels)
        # stage 5: right click on an item → context menu (Settings › «Цвет подписи по умолчанию»:
        # «Удалить» on own colours, as on screen 3); ``context_fn(index, x, y)`` in window coordinates
        self.context_fn = context_fn
        self.cv.bind("<ButtonPress-3>", self._context)
        self.on_select = on_select
        self.swatches = swatches or {}
        fx, fy, fw, fh = field
        self.rows = []  # (top in content, index or None)
        cy = 1 + 2
        for i, lab in enumerate(self.labels):
            if lab is None:
                self.rows.append((cy, None))
                cy += 5
            else:
                self.rows.append((cy + 2, i))
                cy += self.STEP
        content_h = cy + 2 + 1
        h = min(content_h, self.MAX_H)
        self.content_h = content_h
        self.scroll = 0.0
        W, H = app.width(), app.height()
        w = max(self.needed_width(self.labels, self.swatches, content_h > h), fw + 8, min_width)
        w = min(w, W - 8)                       # remark 35: fits the window; longer items get «…»
        sel_top = next((t for t, i in self.rows if i == selected), self.rows[0][0] if self.rows else 3)
        # put the selected item centre on the field centre
        want_top = fy + fh / 2 - (sel_top + self.ITEM_H / 2)
        if content_h > h and want_top < self.MIN_TOP and sel_top + self.ITEM_H > h - 4:
            # selected item would be below the visible list: scroll just enough to show it on the field
            self.scroll = min(content_h - h, max(0.0, self.MIN_TOP - want_top))
            want_top = fy + fh / 2 - (sel_top - self.scroll + self.ITEM_H / 2)
        y = max(self.MIN_TOP, min(want_top, H - 8 - h))
        x = max(4, min(fx - 4, W - w - 4))
        self.selected = selected
        self.hover_i = -1
        # remark 79: the list bar widens on hover like the page bars (arrows, track, 1 s delay)
        self._sb_hover = False
        self._sb_drag = None
        self._sb_pressed = False
        self._sb_repeat = None
        from ui.widgets.scroll import Widening
        self.sb = Widening(self.cv, self._sb_redraw, lambda: self._sb_hover or self._sb_drag is not None)
        self.show_base(x, y, w, h, 8)
        self.draw_items()

    SB_W = 8   # room kept free for the scrollbar (2 px thumb 4 px from the edge)

    @classmethod
    def needed_width(cls, labels, swatches=None, scrolls: bool = False) -> float:
        """Remark 35: every item measured with the real font —
        5 (menu pad) + 12 + swatch 16+8 + text + 12 + 5, + scrollbar room when the list scrolls."""
        swatches = swatches or {}
        best = 0.0
        for i, lab in enumerate(labels):
            if lab is None:
                continue
            best = max(best, (24 if swatches.get(i) else 0) + text_width(lab, 14))
        return float(math.ceil(5 + 12 + best + 12 + 5 + (cls.SB_W if scrolls else 0)))

    def text_room(self, i) -> float:
        return self.pw - 5 - 12 - (24 if self.swatches.get(i) else 0) - 12 - 5 - \
            (self.SB_W if self.content_h > self.ph else 0)

    def draw_items(self):
        self.cv.delete("items")
        menu = Theme.c("menu")
        for top, i in self.rows:
            t = top - self.scroll
            if t + self.ITEM_H < 1 or t > self.ph - 1:
                continue
            if i is None:
                y0 = S(self.py + t + 2)
                if 1 < t + 2 < self.ph - 1:
                    self.cv.create_rectangle(S(self.px + 13), y0, S(self.px + self.pw - 13), y0 + max(1, S(1)),
                                             fill=Theme.c("menu_sep"), width=0, tags="items")
                continue
            vis_top, vis_bot = max(t, 1.0), min(t + self.ITEM_H, self.ph - 1)
            if vis_bot <= vis_top:
                continue
            if i == self.selected or i == self.hover_i:
                sel, c0, c1 = Theme.c("menu_sel"), S(vis_top - t), S(vis_bot - t)

                def sel_img(sel=sel, menu=menu, c0=c0, c1=c1, cut=vis_top > t or vis_bot < t + self.ITEM_H):
                    im = gfx.rrect(self.pw - 10, self.ITEM_H, 4, sel, bg=menu)
                    return im.crop((0, c0, im.width, c1)) if cut else im
                self.put_cached(5, vis_top, ("lsel", self.pw - 10, self.ITEM_H, sel, menu, c0, c1,
                                             vis_top > t or vis_bot < t + self.ITEM_H), sel_img, tags="items")
            if i == self.selected and 1 < t + 10 and t + 26 < self.ph - 1:
                acc, sel = Theme.c("accent"), Theme.c("menu_sel")
                self.put_cached(5, t + 10, ("rr", 3, 16, 1.5, acc, None, sel, ()),
                                lambda acc=acc, sel=sel: gfx.rrect(3, 16, 1.5, acc, bg=sel), tags="items")
            cy = t + self.ITEM_H / 2
            if 4 < cy < self.ph - 4:
                tx = 5 + 12
                sw = self.swatches.get(i)
                if sw:
                    sst = Theme.c("swatch_stroke")
                    sbg = Theme.c("menu_sel") if i in (self.selected, self.hover_i) else menu
                    self.put_cached(tx, cy - 8, ("rr", 16, 16, 4, sw, sst, sbg, ()),
                                    lambda sw=sw, sst=sst, sbg=sbg: gfx.rrect(16, 16, 4, sw, sst, bg=sbg), tags="items")
                    tx += 24
                self.text(tx, cy, elide(self.labels[i], self.text_room(i), 14), 14, "text", tags="items")
        # cover overflow under the rounded border (redraw the border band)
        if self.content_h > self.ph:
            self._draw_scrollbar()

    # remark 79: Win11 bar (ui/widgets/scroll.py) inside the list, right of the items, 1 px inside the border
    def _sb_geo(self):
        from ui.widgets.scroll import bar_geometry
        return bar_geometry(self.pw - 1, 0.0, self.ph, self.sb.t, self.ph, self.content_h, self.scroll)

    def _sb_in_zone(self, x) -> bool:
        from ui.widgets.scroll import ZONE_W
        return x is not None and self.content_h > self.ph and x >= self.pw - 1 - ZONE_W

    def _sb_redraw(self):
        if not self.closed:
            self.draw_items()

    def _draw_scrollbar(self):
        from ui.widgets.scroll import draw_bar
        g = self._sb_geo()
        if g:
            draw_bar(self.cv, g, self.sb.t, Theme.c("menu"), lambda x, y, key, f: self.put_cached(x, y, key, f, tags="items"))

    def _sb_step(self, d, first=False):
        if self.closed:
            return
        from ui.widgets.scroll import REPEAT_FIRST_MS, REPEAT_MS
        self.wheel(-d)
        self._sb_repeat = self.root.after(REPEAT_FIRST_MS if first else REPEAT_MS, lambda: self._sb_step(d))

    def _sb_stop(self):
        if self._sb_repeat is not None:
            try:
                self.root.after_cancel(self._sb_repeat)
            except tk.TclError:
                log.debug("after_cancel failed", exc_info=True)
            self._sb_repeat = None

    def press(self, x, y):
        if not self._sb_in_zone(x):
            return
        from ui.widgets.scroll import bar_zone
        self._sb_pressed = True
        self.sb.expand()
        g = self._sb_geo()
        if not g:
            return
        zone = bar_zone(g, y, 0.0, self.ph)
        if zone == "thumb":
            self._sb_drag = (y, self.scroll, g["travel"])
        elif zone in ("up", "down"):
            self._sb_step(-1 if zone == "up" else 1, first=True)
        else:
            page = self.ph - 2 * self.ITEM_H
            self.scroll = max(0.0, min(self.content_h - self.ph, self.scroll + (page if y > g["thumb"][1] else -page)))
            self.draw_items()

    def _release(self, e):
        if self._sb_pressed and not self.closed and not self.inside(e):     # the thumb let go outside the list
            self.release(None, None)
            return
        super()._release(e)

    def close(self) -> None:
        self.sb.stop()
        self._sb_stop()
        super().close()

    def _row_at(self, y):
        for top, i in self.rows:
            t = top - self.scroll
            if i is not None and t <= y < t + self.ITEM_H:
                return i
        return -1

    def motion(self, x, y):
        if self._sb_drag is not None and y is not None:
            y0, s0, travel = self._sb_drag
            rng = self.content_h - self.ph
            self.scroll = max(0.0, min(rng, s0 + (y - y0) * rng / max(1.0, travel)))
            self.draw_items()
            return
        on_bar = self._sb_in_zone(x)
        if on_bar != self._sb_hover:
            self._sb_hover = on_bar
            if on_bar:
                self.sb.expand()
            else:
                self.sb.collapse_later()
        i = -1 if y is None or on_bar else self._row_at(y)
        if i != self.hover_i:
            self.hover_i = i
            self.draw_items()

    def wheel(self, d):
        if self.content_h <= self.ph:
            return
        self.scroll = max(0.0, min(self.content_h - self.ph, self.scroll - d * 38))
        self.draw_items()

    def key(self, d):
        idx = [i for _, i in self.rows if i is not None]
        if not idx:
            return
        cur = self.hover_i if self.hover_i in idx else self.selected
        if d == 0:
            self.release(0, None, index=cur)
            return
        pos = idx.index(cur) if cur in idx else 0
        self.hover_i = idx[max(0, min(len(idx) - 1, pos + d))]
        self.draw_items()

    def release(self, x, y, index=None):
        if self._sb_pressed and index is None:          # remark 79: a click on the bar picks no item
            self._sb_pressed = False
            self._sb_drag = None
            self._sb_stop()
            if not self._sb_in_zone(x):
                self._sb_hover = False
                self.sb.collapse_later()
            return
        i = self._row_at(y) if index is None else index
        if i >= 0:
            self.close()
            self.root.after(1, lambda: self.on_select(i))

    def _context(self, e):
        if not self.inside(e):
            self.close()
            return
        X, Y = e.x / Scale.factor, e.y / Scale.factor
        i = self._row_at(Y - self.py)
        if i >= 0 and self.context_fn is not None:
            self.context_fn(i, X, Y)


class TooltipLayer:
    """Small snapshot canvas for Win11 tooltips (doesn't take input)."""

    def __init__(self, app):
        self.app = app
        self.cv: Optional[tk.Canvas] = None
        self._img = None
        Tooltip.layer = self

    def show_tooltip(self, owner, text: str):
        self.hide_tooltip()
        root = self.app.root
        ox, oy, ow, oh = widget_rect(root, owner)
        rect_fn = getattr(owner, "tip_rect", None)    # stage 4: a part of a canvas (strip arrow, badge)
        if callable(rect_fn):
            r = rect_fn()
            if r:
                ox, oy, ow, oh = ox + r[0], oy + r[1], r[2], r[3]
        # stage 4 (39): long tooltips wrap at the Win11 width (230 px box, padding 7 10, line 16.2)
        wrap = getattr(owner, "tip_wrap", None)
        lines = [text]
        if wrap and text_width(text, 12) > wrap - 20:
            from ui.dialogs.content import wrap_runs
            lines = ["".join(t for t, _ in ln).strip() for ln in wrap_runs([(text, "normal")], wrap - 20, 12)]
        tw = max(text_width(ln, 12) for ln in lines)
        w = round(tw + 18 + 2 + 0.5) if len(lines) == 1 else round(wrap)
        h = 30 if len(lines) == 1 else round(14 + 16.2 * len(lines) + 2)
        W, H = self.app.width(), self.app.height()
        x = ox + ow / 2 - w / 2
        y = oy + oh + 8
        if y + h > H - 4:
            y = oy - h - 8
        x = max(4, min(x, W - w - 4))
        pad = 16
        bx, by = x - pad, y - pad
        bw, bh = w + 2 * pad, h + 2 * pad
        bx = max(0, min(bx, W - bw))
        by = max(0, min(by, H - bh))
        back = grab_window(root, bx, by, bw, bh)
        lx, ly = x - bx, y - by
        sh = gfx.shadow_box(w, h, 4, TOOLTIP_SHADOW if not Theme.dark() else [(4, 12, 0.40)], pad)
        _paste_clip(back, sh, S(lx - pad), S(ly - pad))
        _paste_clip(back, gfx.rrect(w, h, 4, Theme.c("tooltip"), Theme.c("tooltip_stroke")), S(lx), S(ly))
        self.cv = tk.Canvas(root, highlightthickness=0, bd=0, width=back.width, height=back.height)
        self._img = ImageTk.PhotoImage(back)
        self.cv.create_image(0, 0, image=self._img, anchor="nw")
        if len(lines) == 1:
            self.cv.create_text(S(lx + w / 2), S(ly + h / 2), text=text, font=F(12), fill=Theme.c("text"))
        else:
            for i, ln in enumerate(lines):
                self.cv.create_text(S(lx + 11), S(ly + 8 + 8.1 + 16.2 * i), text=ln, font=F(12),
                                    fill=Theme.c("text"), anchor="w")
        self.cv.place(x=S(bx), y=S(by))
        self.cv.tk.call("raise", self.cv._w)
        self.cv.bind("<Enter>", lambda e: self.hide_tooltip())

    def hide_tooltip(self):
        if self.cv is not None:
            try:
                self.cv.destroy()
            except tk.TclError:
                log.debug("TooltipLayer.hide_tooltip: tk.TclError caught", exc_info=True)   # remark 81
            self.cv = None
