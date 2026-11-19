"""Canvas-based building blocks.  Geometry is in logical px; drawing goes through ``S``."""
from __future__ import annotations

import logging
import tkinter as tk
import weakref
from typing import Callable, Optional

from PIL import Image, ImageTk

from ui import gfx
from ui.theme import F, S, Scale, Theme

log = logging.getLogger(__name__)


class Registry:
    boxes: "weakref.WeakSet[Box]" = weakref.WeakSet()

    @classmethod
    def refresh_all(cls) -> None:
        for b in list(cls.boxes):
            try:
                if b.winfo_exists():
                    b.refresh()
            except tk.TclError:
                log.debug("Registry.refresh_all: tk.TclError caught", exc_info=True)   # remark 81


class Box(tk.Canvas):
    """A themed canvas surface with logical geometry. Subclasses implement ``draw()``."""

    def __init__(self, master, bg: str = "bg", **kw):
        super().__init__(master, highlightthickness=0, bd=0, bg=Theme.c(bg), takefocus=0,
                         confine=False, **kw)
        self.bg_token = bg
        self.lx = self.ly = 0.0
        self.lw = self.lh = 0.0
        self.visible = False
        self._imgs = []  # keep PhotoImage refs alive
        Registry.boxes.add(self)

    def lift(self, aboveThis=None):  # Canvas.lift is tag_raise; raise the widget itself
        if aboveThis is None:
            self.tk.call("raise", self._w)
        else:
            self.tk.call("raise", self._w, aboveThis)

    tkraise = lift

    # geometry ---------------------------------------------------------------
    def geom(self, x: float, y: float, w: float, h: float) -> None:
        changed = (w, h) != (self.lw, self.lh)
        self.lx, self.ly, self.lw, self.lh = x, y, w, h
        X, Y = S(x), S(y)
        self.place(x=X, y=Y, width=max(1, S(x + w) - X), height=max(1, S(y + h) - Y))
        self.visible = True
        if changed:
            self.redraw()

    def hide(self) -> None:
        if self.visible:
            self.place_forget()
            self.visible = False

    def set_bg(self, token: str) -> None:
        if token != self.bg_token:
            self.bg_token = token
            self.configure(bg=Theme.c(token))
            self.redraw()

    # drawing ----------------------------------------------------------------
    def refresh(self) -> None:
        self.configure(bg=Theme.c(self.bg_token))
        if self.visible or self.lw:
            if self.visible:
                X, Y = S(self.lx), S(self.ly)
                self.place(x=X, y=Y, width=max(1, S(self.lx + self.lw) - X),
                           height=max(1, S(self.ly + self.lh) - Y))
            self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        self._imgs.clear()
        if self.lw <= 0 or self.lh <= 0:
            return
        try:
            self.draw()
        except Exception:  # never let a drawing bug kill the UI loop
            log.exception("draw failed in %s", type(self).__name__)

    def draw(self) -> None:  # pragma: no cover - abstract
        pass

    # helpers ----------------------------------------------------------------
    def put(self, x: float, y: float, img, anchor: str = "nw", tags=()) -> int:
        if isinstance(img, Image.Image):
            img = ImageTk.PhotoImage(img)
        self._imgs.append(img)
        return self.create_image(S(x), S(y), image=img, anchor=anchor, tags=tags)

    def put_cached(self, x: float, y: float, key: tuple, factory, anchor: str = "nw", tags=()) -> int:
        p = gfx.photo(key, factory)
        self._imgs.append(p)
        return self.create_image(S(x), S(y), image=p, anchor=anchor, tags=tags)

    def text(self, x: float, cy: float, s: str, px: float = 14, weight: str = "normal",
             color: str = "text", anchor: str = "w", tags=(), width: Optional[float] = None,
             justify: str = "left") -> int:
        """Text whose line box is vertically centred on ``cy`` (matches CSS line boxes)."""
        kw = {}
        if width:
            kw["width"] = S(width)
        return self.create_text(S(x), S(cy), text=s, font=F(px, weight), fill=Theme.c(color),
                                anchor=anchor, tags=tags, justify=justify, **kw)

    def rrect(self, x, y, w, h, r, fill, stroke=None, bg=None, tags=(), **kw) -> int:
        bgc = Theme.c(bg or self.bg_token)
        f = Theme.c(fill) if fill else None
        st = Theme.c(stroke) if stroke else None
        kk = {k: (Theme.c(v) if isinstance(v, str) and k.startswith("stroke_") else v) for k, v in kw.items()}
        key = ("rr", w, h, r, f, st, bgc, tuple(sorted(kk.items())))
        return self.put_cached(x, y, key, lambda: gfx.rrect(w, h, r, f, st, bg=bgc, **kk), tags=tags)

    def icon(self, name: str, x: float, y: float, size: float, color: str = "text", tags=(),
             anchor: str = "nw") -> int:
        c = Theme.c(color) if color else None
        return self.put_cached(x, y, ("ic", name, size, c), lambda: gfx.icon(name, size, c), tags=tags,
                               anchor=anchor)


class Control(Box):
    """Interactive surface: hover / pressed / disabled states, command and tooltip."""

    def __init__(self, master, bg: str = "bg", command: Optional[Callable] = None,
                 tooltip: Optional[Callable[[], str]] = None, cursor: str = ""):
        super().__init__(master, bg=bg)
        self.command = command
        self.tooltip = tooltip
        self.hover = False
        self.pressed = False
        self.disabled = False
        if cursor:
            self.configure(cursor=cursor)
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")
        self.bind("<ButtonPress-1>", self._on_press, add="+")
        self.bind("<ButtonRelease-1>", self._on_release, add="+")

    def set_disabled(self, d: bool) -> None:
        if d != self.disabled:
            self.disabled = d
            self.hover = self.hover and not d
            self.redraw()

    def _on_enter(self, _e=None):
        self.hover = True
        if not self.disabled:
            self.redraw()
        if self.tooltip:
            Tooltip.schedule(self, self.tooltip)

    def _on_leave(self, _e=None):
        self.hover = False
        self.pressed = False
        Tooltip.cancel(self)
        self.redraw()

    def _on_press(self, _e=None):
        Tooltip.cancel(self)
        if self.disabled:
            return
        self.pressed = True
        self.redraw()

    def _on_release(self, e=None):
        was = self.pressed
        self.pressed = False
        if self.disabled:
            return
        self.redraw()
        if was and e is not None and 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            if self.command:
                self.command()


class Tooltip:
    """Win11 tooltip (single shared instance), shown after a short delay."""

    owner = None
    job = None
    delay_ms = 600
    layer = None  # set by overlay module

    @classmethod
    def schedule(cls, owner, text_fn) -> None:
        cls.cancel(None)
        cls.owner = owner
        cls.job = owner.after(cls.delay_ms, lambda: cls._show(owner, text_fn))

    @classmethod
    def _show(cls, owner, text_fn):
        cls.job = None
        if cls.owner is not owner or not owner.winfo_exists():
            return
        try:
            text = text_fn() if callable(text_fn) else str(text_fn)
        except Exception:
            log.exception("tooltip text failed")
            return
        if text and cls.layer:
            cls.layer.show_tooltip(owner, text)

    @classmethod
    def cancel(cls, owner) -> None:
        if owner is not None and cls.owner is not owner:
            return
        if cls.job and cls.owner is not None:
            try:
                cls.owner.after_cancel(cls.job)
            except tk.TclError:
                log.debug("Tooltip.cancel: tk.TclError caught", exc_info=True)   # remark 81
        cls.job = None
        cls.owner = None
        if cls.layer:
            cls.layer.hide_tooltip()
