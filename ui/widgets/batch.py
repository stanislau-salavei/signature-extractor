"""Stage 4 widgets: InfoBar (38–42, 46; remark 89: reasons inside the card), photo strip (14, 16, 63) and the
dimmed main area while a batch is being written (17)."""
from __future__ import annotations

import logging
import tkinter as tk
from typing import Callable, List, Optional

from PIL import Image, ImageDraw, ImageTk

from ui import gfx
from ui.theme import F, S, Scale, Theme, elide, text_width
from ui.widgets.base import Box, Control, Tooltip
from ui.widgets.controls import Button, IconButton, Link
from ui.widgets import scroll as SB

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- InfoBar
class InfoBar(Box):
    """Win11 InfoBar.  kind: warn (38–41, yellow, no ×), ok (42, green, no ×), info (46, card colours,
    «Подробнее» + ×).  Remark 89: the message may have several lines («\\n»), one per reason, all inside the
    card; an elided line shows the full message in a tooltip."""

    FILL = {"warn": ("warn_bg", "warn_stroke"), "ok": ("ok_bg", "ok_stroke"), "info": ("card", "card_stroke")}
    LINE = 16.9

    def __init__(self, master, app, kind: str, action: Optional[Callable] = None,
                 link: Optional[Callable] = None, close: Optional[Callable] = None):
        super().__init__(master, bg="bg")
        self.app, self.kind = app, kind
        self.title, self.msg = "", ""
        self._text_right = 0.0
        bg = self.FILL[kind][0]
        self.action = Button(self, "", bg=bg, pad=12, command=action) if action else None
        if self.action:
            self.action.font_px, self.action.weight = 13, "semibold"
        self.link = Link(self, "", 13, "accent_text", bg=bg, command=link) if link else None
        self.close = IconButton(self, "dismiss", 16, bg=bg, command=close, color="muted",
                                hover_token="ctl_hover") if close else None
        self._action_text = ""
        self.bind("<Enter>", lambda e: self._tip(), add="+")
        self.bind("<Leave>", lambda e: self._untip(), add="+")

    def lines(self) -> list:
        return [ln for ln in self.msg.split("\n") if ln] if self.msg else []

    def _room(self) -> float:
        return max(10.0, self._text_right - 49)

    def elided(self) -> bool:
        room = self._room()
        return any(text_width(ln, 12.5) > room for ln in self.lines())

    def _tip(self):
        from ui.widgets.base import Tooltip
        if self.elided():
            Tooltip.schedule(self, lambda: self.msg)

    def _untip(self):
        from ui.widgets.base import Tooltip
        Tooltip.cancel(self)

    def set(self, title: str, msg: str = "", action: str = "", link: str = "") -> None:
        self.title, self.msg = title, msg
        self._action_text = action
        if self.action:
            self.action.set_text(action)
        if self.link:
            self.link.set_text(link)

    def height(self) -> float:
        n = len(self.lines())
        if n:
            return 54.8 + self.LINE * (n - 1)   # padding 8 + 1 + title 16.9 + 1 + n × 16.9 + 1 + 8 + borders
        if self.close:
            return 50.0           # the 32 px × button sets the height (46)
        return 48.0               # min-height (42)

    def layout(self, x, y, w):
        h = self.height()
        self.geom(x, y, w, h)
        right = w - 1 - 8
        if self.close:
            self.close.geom(right - 32, (h - 32) / 2, 32, 32)
            right -= 32 + 12
        if self.action and not self._action_text:
            self.action.hide()          # remark 70: one photo — the bar without «Показать»
        elif self.action:
            bw = self.action.natural_width()
            self.action.geom(right - bw, (h - 32) / 2, bw, 32)
            right -= bw + 12
        if self.link:
            lw = self.link.natural_width()
            self.link.geom(right - 8 - lw, (h - 16) / 2, lw, 16)
            right -= lw + 16 + 12
        self._text_right = right
        self.redraw()

    def draw(self):
        w, h = self.lw, self.lh
        fill, stroke = self.FILL[self.kind]
        self.rrect(0, 0, w, h, 4, fill, stroke)
        lines = self.lines()
        # icon in the middle (mockups 38–41); with several reason lines it stays by the title and the first line
        ic = min((h - 20) / 2, 1 + 8 + 1 + self.LINE - 10)
        if self.kind == "warn":
            self.icon("warn_triangle", 17, ic, 20, None)
        elif self.kind == "ok":
            self.icon("ok_circle", 17, ic, 20, None)
        else:
            self.put_cached(17, ic, ("ibinfo", Theme.c("accent"), Theme.mode),
                            lambda: _info_icon(Theme.c("accent"), Theme.c("on_accent")))
        room = self._room()
        if lines:
            self.text(49, 1 + 8 + 1 + 8.45, elide(self.title, room, 13, "semibold"), 13, "semibold")
            for i, ln in enumerate(lines):
                self.text(49, 1 + 8 + 1 + self.LINE * (i + 1) + 8.45, elide(ln, room, 12.5), 12.5)
        else:
            self.text(49, h / 2, elide(self.title, room, 13, "semibold"), 13, "semibold")


def _info_icon(accent: str, on: str) -> Image.Image:
    """46: accent circle with an «i» (mockup .ico-info: circle r 9, stroke 1.8)."""
    D = max(1, S(20))
    ss = 4
    im = Image.new("RGBA", (D * ss, D * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = D * ss / 20
    d.ellipse((1 * k, 1 * k, 19 * k, 19 * k), fill=gfx.rgba(accent))
    lw = 1.8 * k
    d.line((10 * k, 9 * k, 10 * k, 14 * k), fill=gfx.rgba(on), width=int(round(lw)))
    d.ellipse((10 * k - lw / 2, 6.35 * k - lw / 2, 10 * k + lw / 2, 6.35 * k + lw / 2), fill=gfx.rgba(on))
    for yy in (9, 14):
        d.ellipse((10 * k - lw / 2, yy * k - lw / 2, 10 * k + lw / 2, yy * k + lw / 2), fill=gfx.rgba(on))
    return im.resize((D, D), Image.Resampling.LANCZOS)


# --------------------------------------------------------------------------- strip
TILE = 64          # thumbnail tile (mockup .th 64 × 64, radius 4)
PITCH = 70         # tile + 6 px gap
FILM_TOP = 49      # card padding 8 + header 32 + gap 8 (+1 border)
RING = 3           # selection ring outside the tile (1 px border + 2 px shadow)
STRIP_H = 131


class _Film(Control):
    """Tiles of the strip (one canvas; arrows and badges are hit-tested here so that nothing
    paints a square background over the thumbnails)."""

    def __init__(self, strip: "PhotoStrip"):
        super().__init__(strip, bg="card")
        self.strip = strip
        self.hot = None          # hovered part: ("tile", i) | ("badge", i) | ("prev",) | ("next",)
        self.tooltip = self._tip_text
        self.tip_rect_value = None
        self.bind("<Motion>", self._motion, add="+")
        self.wheel_handler = strip.wheel

    # hit testing ---------------------------------------------------------------
    def _arrow_rects(self):
        h = self.lh
        y = (h - 28) / 2
        s = self.strip
        rects = {}
        if s.scroll > 0.5:
            rects["prev"] = (6, y, 28, 28)
        if s.scroll < s.max_scroll() - 0.5:
            rects["next"] = (self.lw - 6 - 28, y, 28, 28)
        return rects

    def part_at(self, x, y):
        for k, (ax, ay, aw, ah) in self._arrow_rects().items():
            if ax <= x <= ax + aw and ay <= y <= ay + ah:
                return (k,)
        s = self.strip
        cx = x + s.scroll
        i = int(cx // PITCH)
        if 0 <= i < len(s.items()) and cx - i * PITCH <= TILE and RING <= y <= RING + TILE:
            bx = i * PITCH + TILE - 20 - 4 - s.scroll
            if bx - 2 <= x <= bx + 22 and RING + 2 <= y <= RING + 26 and s.badge_kind(s.items()[i]):
                return ("badge", i)
            return ("tile", i)
        return None

    def _motion(self, e):
        part = self.part_at(e.x / Scale.factor, e.y / Scale.factor)
        if part != self.hot:
            self.hot = part
            Tooltip.cancel(self)
            if part and part[0] in ("badge", "prev", "next"):
                Tooltip.schedule(self, self._tip_text)
            self.redraw()

    def _on_enter(self, _e=None):
        self.hover = True

    def _on_leave(self, _e=None):
        super()._on_leave(_e)
        self.hot = None
        self.redraw()

    def tip_rect(self):
        part = self.hot
        if not part:
            return None
        s = self.strip
        if part[0] in ("prev", "next"):
            return self._arrow_rects().get(part[0])
        if part[0] == "badge":
            return (part[1] * PITCH + TILE - 24 - s.scroll, RING + 4, 20, 20)
        return None

    def _tip_text(self):
        part = self.hot
        if not part:
            return ""
        t = self.strip.app.t
        if part[0] == "prev":
            return t("batch.prev")
        if part[0] == "next":
            return t("batch.next")
        if part[0] == "badge":
            kind = self.strip.badge_kind(self.strip.items()[part[1]])
            return t("batch.attention") if kind == "warn" else t("batch.ready")
        return ""

    def _on_release(self, e=None):
        was = self.pressed
        self.pressed = False
        if not was or e is None:
            return
        part = self.part_at(e.x / Scale.factor, e.y / Scale.factor)
        if not part:
            return
        if part[0] == "prev":
            self.strip.page(-1)
        elif part[0] == "next":
            self.strip.page(1)
        else:
            self.strip.click(part[1])

    # drawing -------------------------------------------------------------------
    def draw(self):
        s = self.strip
        items = s.items()
        if not items:
            return
        first = max(0, int(s.scroll // PITCH) - 1)
        last = min(len(items), int((s.scroll + self.lw) // PITCH) + 2)
        for i in range(first, last):
            x = i * PITCH - s.scroll
            job = items[i]
            sel = i == s.index()
            key = s.tile_key(job, sel)
            self.put_cached(x - RING, 0, key, lambda job=job, sel=sel: s.tile_image(job, sel))
            if s.badge_kind(job) == "warn":   # «!» 13 px on the yellow badge (Semibold: weight 700 is not used)
                self.create_text(S(x + TILE - 14), S(RING + 14.5), text="!", font=F(13, "semibold"),
                                 fill=Theme.c("badge_warn_text"), anchor="center")
        for k, (ax, ay, aw, ah) in self._arrow_rects().items():
            hov = self.hot == (k,)
            self.put_cached(ax - 6, ay - 6, ("strip_arrow", k, hov, Theme.mode), lambda k=k, hov=hov: _arrow_image(k, hov))


def _arrow_image(kind: str, hover: bool) -> Image.Image:
    """28 px round arrow (ctl fill, 1 px stroke, shadow 0 1 4 .16) with a 6 px shadow margin."""
    pad = 6
    out = Image.new("RGBA", (S(28 + 2 * pad), S(28 + 2 * pad)), (0, 0, 0, 0))
    sh = gfx.shadow_box(28, 28, 14, [(1, 4, 0.16)], pad)
    out.alpha_composite(sh.resize(out.size) if sh.size != out.size else sh)
    disc = gfx.circle(28, Theme.c("ctl_hover" if hover else "ctl"), Theme.c("ctl_stroke"))
    out.alpha_composite(disc, (S(pad), S(pad)))
    ic = gfx.icon("strip_prev" if kind == "prev" else "strip_next", 16, Theme.c("text"))
    out.alpha_composite(ic, (S(pad + 6), S(pad + 6)))
    return out


class _HBar(Control):
    """Horizontal scrollbar under the thumbnails.  Remark 86: works like the other Windows 11 bars (remark 79,
    ui/widgets/scroll.py): at rest a 2 px line about 4 px under the tiles; on hover it widens smoothly to a 6 px
    thumb with a 12 px track and arrows at both ends; it narrows about 1 s after the pointer leaves.  An arrow
    scrolls by one tile (and repeats while held), a click on the track by a page, the thumb can be dragged.
    The round «‹» / «›» buttons of the strip stay."""

    H = SB.ZONE_W                  # 12 px zone (the track when widened)
    REST_GAP = 7.5                 # rest line 2.5–4.5 px from the top of the zone (≈ 4 px under the tiles, as before)
    WIDE_GAP = 3.0                 # widened 6 px thumb centred in the 12 px track

    def __init__(self, strip: "PhotoStrip"):
        super().__init__(strip, bg="card")
        self.strip = strip
        self._drag = None
        self._repeat = None
        self.wide = SB.Widening(self, self.redraw, lambda: self.hover or self._drag is not None)
        self.bind("<B1-Motion>", self._move)
        self.wheel_handler = strip.wheel

    @property
    def t(self) -> float:
        return self.wide.t

    def _geo(self):
        s = self.strip
        return SB.hbar_geometry(self.lh, 0.0, self.lw, self.wide.t, s.view_w(), s.content_w(), s.scroll,
                                self.REST_GAP, self.WIDE_GAP)

    def _thumb(self):
        g = self._geo()
        return (g["thumb"][0], g["thumb"][2]) if g else None

    def thumb_rect(self):
        g = self._geo()
        return g["thumb"] if g else None

    def arrows_shown(self) -> bool:
        g = self._geo()
        return bool(g and g["arrows"])

    # mouse ---------------------------------------------------------------------
    def _on_enter(self, e=None):
        super()._on_enter(e)
        if self._geo() is not None:
            self.wide.expand()

    def _on_leave(self, e=None):
        self.hover = False
        self.pressed = False
        if self._drag is None:
            self.wide.collapse_later()
        self._stop_repeat()

    def _on_press(self, e=None):
        super()._on_press(e)
        g = self._geo()
        if not g or e is None:
            return
        x = e.x / Scale.factor
        zone = SB.hbar_zone(g, x, 0.0, self.lw)
        self._drag = None
        if zone == "thumb":
            self._drag = (x, self.strip.scroll)
        elif zone in ("left", "right"):
            self._step(-1 if zone == "left" else 1, first=True)
        else:
            self.strip.page(1 if x > g["thumb"][0] else -1)

    def _step(self, d: int, first: bool = False):
        self.strip.scroll_to(self.strip.scroll + d * PITCH)
        self._repeat = self.after(SB.REPEAT_FIRST_MS if first else SB.REPEAT_MS, lambda: self._step(d))

    def _stop_repeat(self):
        if self._repeat is not None:
            try:
                self.after_cancel(self._repeat)
            except tk.TclError:
                log.debug("_HBar._stop_repeat: after_cancel failed", exc_info=True)   # remark 81
            self._repeat = None

    def _move(self, e):
        g = self._geo()
        if not self._drag or not g:
            return
        x0, s0 = self._drag
        s = self.strip
        rng = s.content_w() - s.view_w()
        s.scroll_to(s0 + (e.x / Scale.factor - x0) * rng / max(1.0, g["travel"]))

    def _on_release(self, e=None):
        self._stop_repeat()
        was_drag = self._drag is not None
        self._drag = None
        super()._on_release(None)
        if was_drag and e is not None and not (0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height()):
            self.hover = False
            self.wide.collapse_later()

    def draw(self):
        g = self._geo()
        if g:
            SB.draw_bar(self, g, self.wide.t, Theme.c("card"), lambda x, y, key, f: self.put_cached(x, y, key, f))


class PhotoStrip(Box):
    """Card «Фото N из M» + «Добавить» / «Убрать» + one row of thumbnails (14, 16, 63)."""

    def __init__(self, master, app, on_select: Callable[[int], None], on_add: Optional[Callable] = None,
                 on_remove: Optional[Callable] = None):
        super().__init__(master, bg="bg")
        self.app = app
        self.on_select = on_select
        self.add = Button(self, "", icon="add", bg="card", command=on_add) if on_add else None
        self.remove = Button(self, "", icon="subtract", bg="card", command=on_remove)
        for b in (self.add, self.remove):
            if b:
                b.font_px = 13
        self.film = _Film(self)
        self.bar = _HBar(self)
        self.scroll = 0.0
        self.show_add = True
        self.show_dots = False     # 63: grey dot on photos without DPI («Как в исходнике»)
        self.wheel_handler = self.wheel

    # data ----------------------------------------------------------------------
    def batch(self):
        return self.app.batch

    def items(self):
        b = self.batch()
        return b.items if b else []

    def index(self):
        b = self.batch()
        return b.index if b else 0

    def badge_kind(self, job):
        st = job.status
        if st in ("attention", "doubt"):    # remark 48: doubts get the same mark
            return "warn"
        if st == "ready":
            return "ok"
        return None

    def tile_key(self, job, sel):
        return ("tile", job.id, id(job.thumb), self.badge_kind(job), sel,
                self.show_dots and job.processed and not job.has_dpi, Theme.mode)

    def tile_image(self, job, sel) -> Image.Image:
        """Tile with its selection ring: (TILE + 2·RING)² logical px."""
        full = TILE + 2 * RING
        D = S(full)
        out = Image.new("RGBA", (D, D), (0, 0, 0, 0))
        warn = self.badge_kind(job) == "warn"
        acc = Theme.c("accent")
        if sel:
            out.alpha_composite(gfx.rrect(TILE + 4, TILE + 4, 6, acc), (S(RING - 2), S(RING - 2)))
        bw = 2 if warn else 1
        stroke = Theme.c("badge_warn") if warn else (acc if sel else Theme.c("card_stroke"))
        out.alpha_composite(gfx.rrect(TILE, TILE, 4, stroke), (S(RING), S(RING)))
        inner = TILE - 2 * bw
        base = gfx.rrect(inner, inner, 4 if not warn else 3, Theme.c("thumb"))
        if job.thumb is not None:
            ph = job.thumb.convert("RGBA").resize(base.size, Image.Resampling.LANCZOS)
            mask = base.getchannel("A")
            base = Image.new("RGBA", base.size, (0, 0, 0, 0))
            base.paste(ph, (0, 0), mask)
        out.alpha_composite(base, (S(RING + bw), S(RING + bw)))
        kind = self.badge_kind(job)
        if kind:
            bx, by = RING + TILE - 24, RING + 4
            sh = gfx.shadow_box(20, 20, 10, [(1, 2, 0.18)], 4)
            _paste(out, sh, S(bx - 4), S(by - 4))
            out.alpha_composite(gfx.circle(20, Theme.c("card")), (S(bx), S(by)))
            out.alpha_composite(gfx.circle(16, Theme.c("badge_ok" if kind == "ok" else "badge_warn")), (S(bx + 2), S(by + 2)))
            if kind == "ok":
                out.alpha_composite(gfx.icon("badge_check", 11, "#FFFFFF"), (S(bx + 4.5), S(by + 4.5)))
        if self.show_dots and job.processed and not job.has_dpi:
            out.alpha_composite(gfx.circle(11, Theme.c("card")), (S(RING + 5.5), S(RING + 47.5)))
            out.alpha_composite(gfx.circle(8, Theme.c("dpi_dot")), (S(RING + 7), S(RING + 49)))
        return out

    # geometry --------------------------------------------------------------------
    def view_w(self):
        return max(1.0, self.lw - 22)

    def content_w(self):
        n = len(self.items())
        return max(0.0, n * PITCH - 6)

    def max_scroll(self):
        return max(0.0, self.content_w() - self.view_w())

    def scroll_to(self, v):
        v = max(0.0, min(float(v), self.max_scroll()))
        if abs(v - self.scroll) > 0.01:
            self.scroll = v
            self.film.redraw()
            self.bar.redraw()

    def page(self, d):
        self.scroll_to(self.scroll + d * max(PITCH, (self.view_w() // PITCH - 1) * PITCH))

    def wheel(self, delta):
        from ui.widgets.overlay import Popup
        if Popup.current is not None:
            return
        self.scroll_to(self.scroll - delta / 120 * PITCH)

    def ensure_visible(self, i=None, center=True):
        """Bring photo ``i`` into view; by default centred like the mockups (14, 16)."""
        i = self.index() if i is None else i
        if center:
            self.scroll_to(i * PITCH + TILE / 2 - self.view_w() / 2)
            return
        x0, x1 = i * PITCH, i * PITCH + TILE
        if x0 - RING < self.scroll:
            self.scroll_to(x0 - RING - 4)
        elif x1 + RING > self.scroll + self.view_w():
            self.scroll_to(x1 + RING + 4 - self.view_w())

    def click(self, i):
        if self.on_select:
            self.on_select(i)

    def layout(self, x, y, w):
        self.geom(x, y, w, STRIP_H)
        t = self.app.t
        right = w - 13
        self.remove.set_text(t("common.remove"))
        rw = self.remove.natural_width()
        self.remove.geom(right - rw, 9, rw, 32)
        right -= rw + 12
        if self.add and self.show_add:
            self.add.set_text(t("common.add"))
            aw = self.add.natural_width()
            self.add.geom(right - aw, 9, aw, 32)
        elif self.add:
            self.add.hide()
        self.film.geom(11, FILM_TOP - RING, w - 22, TILE + 2 * RING)
        # remark 86: the 12 px bar zone starts under the selection ring; the rest line stays where it was
        self.bar.geom(13, FILM_TOP + TILE + RING, w - 26, _HBar.H)
        self.scroll = max(0.0, min(self.scroll, self.max_scroll()))
        self.film.redraw()
        self.bar.redraw()
        self.redraw()

    def refresh_items(self):
        self.scroll = max(0.0, min(self.scroll, self.max_scroll()))
        self.film.redraw()
        self.bar.redraw()
        self.redraw()

    def draw(self):
        self.rrect(0, 0, self.lw, self.lh, 8, "card", "card_stroke")
        items = self.items()
        if items:
            self.text(13, 9 + 16, self.app.t("batch.counter", i=self.index() + 1, n=len(items)), 12.5, "semibold")


def _paste(dst, src, X, Y):
    from ui.widgets.overlay import _paste_clip
    _paste_clip(dst, src, X, Y)


# --------------------------------------------------------------------------- dim (17)
class DimLayer:
    """While a batch is written the main area is shown at 42 % opacity and takes no input (17)."""

    def __init__(self, app):
        self.app = app
        self.cv: Optional[tk.Canvas] = None
        self.rect = None
        self._img = None

    def show(self, x, y, w, h):
        self.rect = (x, y, w, h)
        self._render()

    def _render(self):
        from ui.widgets.overlay import grab_window
        if self.rect is None:
            return
        x, y, w, h = self.rect
        root = self.app.root
        if self.cv is not None:
            self.cv.place_forget()
        snap = grab_window(root, x, y, w, h)
        bg = Image.new("RGBA", snap.size, gfx.rgba(Theme.c("bg")))
        img = Image.blend(bg, snap, 0.42)
        if self.cv is None:
            self.cv = tk.Canvas(root, highlightthickness=0, bd=0, takefocus=0)
            for ev in ("<ButtonPress-1>", "<ButtonRelease-1>", "<ButtonPress-3>", "<Double-Button-1>"):
                self.cv.bind(ev, lambda e: "break")
            self.cv.wheel_handler = lambda d: None
        self._img = ImageTk.PhotoImage(img)
        self.cv.delete("all")
        self.cv.create_image(0, 0, image=self._img, anchor="nw")
        self.cv.place(x=S(x), y=S(y), width=snap.width, height=snap.height)
        self.cv.tk.call("raise", self.cv._w)

    def relayout(self, x, y, w, h):
        if self.cv is None:
            return
        self.rect = (x, y, w, h)
        self.app.root.after(60, self._render)

    def hide(self):
        self.rect = None
        if self.cv is not None:
            try:
                self.cv.destroy()
            except tk.TclError:
                log.debug("DimLayer.hide: tk.TclError caught", exc_info=True)   # remark 81
            self.cv = None

    @property
    def active(self):
        return self.cv is not None
