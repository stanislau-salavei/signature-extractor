"""Window header: stepper (centred left of ⋯) and the ⋯ button (variant B)."""
from __future__ import annotations

from typing import Callable, List

from ui import gfx
from ui.theme import S, Scale, Theme, text_width
from ui.widgets.base import Box, Control
from ui.widgets.controls import IconButton


class Stepper(Control):
    """Track 2 px padding / 2 px gap, steps 36 high (padding 6 16 10 16), number circle 20, text 13."""

    def __init__(self, master, app, on_click: Callable[[int], None]):
        super().__init__(master, bg="bg")
        self.app = app
        self.on_click = on_click
        self.labels: List[str] = ["", "", ""]
        self.active = 0
        self.done = set()
        self.enabled = {0}
        self.hover_i = -1
        self.bind("<Motion>", self._motion)

    def seg_widths(self):
        return [16 + 20 + 8 + text_width(l, 13) + 16 for l in self.labels]

    def natural_width(self):
        return sum(self.seg_widths()) + 2 * (len(self.labels) - 1) + 4 + 2

    def set_state(self, labels, active, done, enabled):
        self.labels, self.active, self.done, self.enabled = list(labels), active, set(done), set(enabled)
        self.redraw()

    def _seg_at(self, x):
        cx = 3
        for i, w in enumerate(self.seg_widths()):
            if cx <= x < cx + w:
                return i
            cx += w + 2
        return -1

    def _motion(self, e):
        i = self._seg_at(e.x / Scale.factor)
        if i != self.hover_i:
            self.hover_i = i
            self.redraw()

    def _on_leave(self, _e=None):
        self.hover_i = -1
        super()._on_leave(_e)

    def _on_release(self, e=None):
        super()._on_release(None)
        if e is None:
            return
        i = self._seg_at(e.x / Scale.factor)
        if i >= 0 and i != self.active and i in self.enabled:
            self.on_click(i)

    def draw(self):
        w, h = self.lw, self.lh
        self.rrect(0, 0, w, h, 4, "seg_track", "seg_track_stroke")
        x = 3
        for i, sw in enumerate(self.seg_widths()):
            on = i == self.active
            if on:
                self.rrect(x, 3, sw, 36, 4, "seg_on", "seg_on_stroke", bg="seg_track")
                self.rrect(x + sw / 2 - 8, 3 + 36 - 2 - 3, 16, 3, 1.5, "accent", bg="seg_on")
            elif i == self.hover_i and i in self.enabled:
                self.rrect(x, 3, sw, 36, 4, "seg_hover", bg="seg_track")
            cbg = "seg_on" if on else ("seg_hover" if (i == self.hover_i and i in self.enabled) else "seg_track")
            cx, cy = x + 16, 3 + 6
            # number circle 20, ring 1.5 (spec) ; text baseline box 6..26
            if on:
                self.put_cached(cx, cy, ("stepc", "on", Theme.c("accent"), Theme.c(cbg)),
                                lambda cbg=cbg: gfx.circle(20, Theme.c("accent"), bg=Theme.c(cbg)))
                self.text(cx + 10, cy + 10, str(i + 1), 11, "semibold", "on_accent", anchor="center")
                tcol = "text"
            elif i in self.done:
                self.put_cached(cx, cy, ("stepc", "done", Theme.c("accent"), Theme.c(cbg)),
                                lambda cbg=cbg: gfx.circle(20, Theme.c(cbg), Theme.c("accent"), 1.5, bg=Theme.c(cbg)))
                self.icon("step_check", cx + 4, cy + 4, 12, "accent")
                tcol = "text"
            else:
                self.put_cached(cx, cy, ("stepc", "off", Theme.c("step_ring"), Theme.c(cbg)),
                                lambda cbg=cbg: gfx.circle(20, Theme.c(cbg), Theme.c("step_ring"), 1.5, bg=Theme.c(cbg)))
                self.text(cx + 10, cy + 10, str(i + 1), 11, "semibold", "muted", anchor="center")
                tcol = "muted"
            self.text(cx + 20 + 8, cy + 10, self.labels[i], 13, color=tcol)
            x += sw + 2


class Header(Box):
    """Header 64 px: padding 0 24, gap 16; ⋯ 36×36 with a 20 px glyph."""

    def __init__(self, master, app):
        super().__init__(master, bg="bg")
        self.app = app
        self.stepper = Stepper(self, app, app.on_step_click)
        self.more = IconButton(self, "more", 20, bg="bg", command=app.open_more_menu,
                               tooltip=lambda: app.t("shell.more"))

    def layout(self, w):
        self.geom(0, 0, w, 64)
        sw = self.stepper.natural_width()
        area_l, area_r = 24, w - 24 - 36 - 16
        x = area_l + (area_r - area_l - sw) / 2
        self.stepper.geom(x, 11, sw, 42)
        self.more.geom(w - 24 - 36, 14, 36, 36)

    def draw(self):
        pass
