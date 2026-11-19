"""Scrollable viewport with a Notepad-like overlay scrollbar (thin 2 px line, 6 px on hover)."""
from __future__ import annotations

import sys
import tkinter as tk
from typing import Callable

from ui.theme import S, Scale, Theme
from ui.widgets.base import Box, Control


class ScrollBar(Control):
    W = 12

    def __init__(self, master, area: "ScrollArea"):
        super().__init__(master, bg=area.bg_token)
        self.area = area
        self._drag_y = None
        self.bind("<B1-Motion>", self._drag)

    def _thumb(self):
        a = self.area
        track = self.lh - 8
        if a.content_h <= a.view_h or track <= 0:
            return None
        th = max(24.0, track * a.view_h / a.content_h)
        rng = a.content_h - a.view_h
        ty = 4 + (track - th) * (a.scroll / rng)
        return ty, th

    def _on_press(self, e=None):
        super()._on_press(e)
        t = self._thumb()
        if not t or e is None:
            return
        y = e.y / Scale.factor
        ty, th = t
        if ty <= y <= ty + th:
            self._drag_y = (y, self.area.scroll)
        else:  # page jump
            self.area.scroll_by((self.area.view_h - 40) * (1 if y > ty else -1))
            self._drag_y = None

    def _drag(self, e):
        if not self._drag_y:
            return
        t = self._thumb()
        if not t:
            return
        y0, s0 = self._drag_y
        track = self.lh - 8
        rng = self.area.content_h - self.area.view_h
        dy = e.y / Scale.factor - y0
        self.area.scroll_to(s0 + dy * rng / max(1, track - t[1]))

    def _on_release(self, e=None):
        self._drag_y = None
        super()._on_release(None)

    def draw(self):
        t = self._thumb()
        if not t:
            return
        ty, th = t
        if self.hover or self._drag_y:
            self.rrect(self.lw - 3 - 6, ty, 6, th, 3, "scroll_thumb")
        else:
            self.rrect(self.lw - 3 - 4 + 1, ty, 2, th, 1, "scroll_thumb")


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
        from ui.widgets.overlay import Popup
        if not self.in_popup and Popup.current is not None and self.winfo_toplevel() is Popup.current.root:
            return
        self.scroll_by(-delta / 120 * 48)
