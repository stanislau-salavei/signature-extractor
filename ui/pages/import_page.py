"""Screen 1 (01, 02, 03, 45, 55): Quick-Share-like drop zone, tips card, processing state."""
from __future__ import annotations

import math

from ui import gfx
from ui.theme import F, S, Theme, text_width
from ui.widgets.base import Box
from ui.widgets.controls import Button, Link


class DropZone(Box):
    """White card radius 16 (dark #2B2B2B); dashed 1.5 px frame inset 12, radius 8, dash 4/4.
    Drag-over (02): solid 2 px accent frame + ~6 % accent fill. Processing (03): spinner only."""

    def __init__(self, master, app):
        super().__init__(master, bg="bg")
        self.app = app
        self.mode = "idle"   # idle | over | busy
        self.angle = 0
        self.open_btn = Button(self, app.t("menu.open_file"), kind="primary", icon="image_btn", size="lg",
                               bg="drop", command=app.open_file_dialog,
                               tooltip=lambda: app.t("menu.open_file.tooltip"))
        self.batch_btn = Button(self, app.t("import.batch_folder"), kind="secondary", icon="folder_batch",
                                size="lg", bg="drop", command=app.open_folder_dialog)
        self._spin_job = None

    def set_mode(self, mode):
        if mode != self.mode:
            self.mode = mode
            self.redraw()
            self._place_buttons()
            if mode == "busy":
                self._tick()

    def _tick(self):
        if self.mode != "busy" or not self.winfo_exists():
            self._spin_job = None
            return
        self.angle = (self.angle + 12) % 360
        self.delete("spin")
        self._draw_spinner()
        self._spin_job = self.after(30, self._tick)

    def _place_buttons(self):
        if self.mode == "busy" or self.lw <= 0:
            self.open_btn.hide()
            self.batch_btn.hide()
            return
        fill = "drop_over" if self.mode == "over" else "drop"
        for b in (self.open_btn, self.batch_btn):
            b.set_bg(fill)
        self.open_btn.label = self.app.t("menu.open_file")
        self.batch_btn.label = self.app.t("import.batch_folder")
        w1, w2 = self.open_btn.natural_width(), self.batch_btn.natural_width()
        top = self._inner_top() + 84 + 6 + 16 + 29 + 16 + 4
        x = (self.lw - (w1 + 10 + w2)) / 2
        self.open_btn.geom(x, top, w1, 36)
        self.batch_btn.geom(x + w1 + 10, top, w2, 36)

    def _inner_top(self):
        return (self.lh - 191) / 2

    def geom(self, x, y, w, h):
        super().geom(x, y, w, h)
        self._place_buttons()

    def refresh(self):
        super().refresh()
        self._place_buttons()

    def draw(self):
        w, h = self.lw, self.lh
        over = self.mode == "over"
        fill = "drop_over" if over else "drop"
        self.rrect(0, 0, w, h, 16, fill, "card_stroke")
        if over:
            self.rrect(12, 12, w - 24, h - 24, 8, None, "accent", stroke_w=2, bg=fill)
        else:
            key = ("dash", w, h, Theme.c("drop_dash"))
            self.put_cached(12, 12, key, lambda: gfx.dashed_rrect(w - 24, h - 24, 8, Theme.c("drop_dash"), 1.5, 4, 4))
        if self.mode == "busy":
            top = (h - 112) / 2
            self._draw_spinner()
            self.text(w / 2, top + 36 + 24 + 10, self.app.t("import.progress_title"), 16, "semibold", anchor="center")
            self.text(w / 2, top + 36 + 24 + 20 + 16 + 8, self.app.t("import.progress_sub"), 13, color="muted",
                      anchor="center")
            return
        top = self._inner_top()
        self.rrect(w / 2 - 42, top, 84, 84, 8, "accent_soft_drop" if not over else "accent_soft_drop", bg=fill)
        self.icon("upload", w / 2 - 20, top + 22, 40, "accent")
        title = self.app.t("import.drop_release" if over else "import.drop_title")
        self.text(w / 2, top + 84 + 6 + 16 + 14.5, title, 24, "semibold", anchor="center")

    def _draw_spinner(self):
        w, h = self.lw, self.lh
        top = (h - 112) / 2
        x0, y0 = w / 2 - 18, top
        lw = 3
        # ring track + rotating accent arc (anti-aliased by Tk on Windows / Xft on Linux)
        self.create_oval(S(x0 + lw / 2), S(y0 + lw / 2), S(x0 + 36 - lw / 2), S(y0 + 36 - lw / 2),
                         outline=Theme.c("card_stroke"), width=S(lw), tags="spin")
        self.create_arc(S(x0 + lw / 2), S(y0 + lw / 2), S(x0 + 36 - lw / 2), S(y0 + 36 - lw / 2),
                        start=-self.angle + 45, extent=90, style="arc", outline=Theme.c("accent"),
                        width=S(lw), tags="spin")


class TipsCard(Box):
    """Quiet tips card: radius 4, padding 14 18 14 16, «i» 18, title 13/600, tips 12.5 (lh 18.125, gap 3)."""

    HEIGHT = 164.5

    def __init__(self, master, app):
        super().__init__(master, bg="bg")
        self.app = app
        self.link = Link(self, app.t("import.how_to_link"), 12.5, "accent_text", bg="tips", weight="medium",
                         command=app.open_help_prep)

    def draw(self):
        w, h = self.lw, self.lh
        t = self.app.t
        self.rrect(0, 0, w, h, 4, "tips", "card_stroke")
        self.put_cached(17, 16, ("ii", Theme.c("accent"), Theme.c("tips")),
                        lambda: gfx.circle(18, Theme.c("accent"), bg=Theme.c("tips")))
        self.create_text(S(17 + 9), S(16 + 9), text="i", fill=Theme.c("on_accent"),
                         font=F(12, "bold"), anchor="center")
        x = 49
        self.text(x, 15 + 8, t("import.tips_title"), 13, "semibold")
        y = 37
        for key in ("import.tip_phone", "import.tip_closeup", "import.tip_background"):
            self.text(x, y + 9.06, t(key), 12.5, color="muted")
            y += 18.125 + 3
        y += 6
        self.text(x, y + 9.06, t("import.supported"), 12.5, color="muted")
        self.link.label = t("import.how_to_link")
        lw = self.link.natural_width()
        self.link.geom(x, 134.5, lw, 15)


class ErrorBar(Box):
    """Red info bar without a close button (45): 48 high, radius 4, padding 8 8 8 16, icon 20, title 13/600."""

    def __init__(self, master, app):
        super().__init__(master, bg="bg")
        self.app = app
        self.message = ""

    def draw(self):
        w, h = self.lw, self.lh
        self.rrect(0, 0, w, h, 4, "error_bg", Theme.c("error_stroke") if False else "error_stroke")
        bg = Theme.c("error_bg")
        self.put_cached(17, 14, ("err", Theme.c("error_icon"), bg), lambda: _err_icon(Theme.c("error_icon"), bg))
        self.text(49, 15.5 + 8.45, self.message, 13, "semibold")


def _err_icon(color, bg):
    im = gfx.circle(20, color, bg=bg)
    x = gfx.icon("close", 12, "#FFFFFF" if not Theme.dark() else "#000000")
    im.alpha_composite(x, (S(4), S(4)))
    return im


class ImportPage(Box):
    def __init__(self, master, app):
        super().__init__(master, bg="bg")
        self.app = app
        self.error = ErrorBar(self, app)
        self.drop = DropZone(self, app)
        self.tips = TipsCard(self, app)
        self.error_text = ""

    def show_error(self, text: str):
        self.error_text = text
        self.error.message = text
        self.layout(self.lw, self.lh)

    def clear_error(self):
        if self.error_text:
            self.error_text = ""
            self.layout(self.lw, self.lh)

    def layout(self, w, h):
        self.geom(0, 64, w, h)
        top = 24
        if self.error_text:
            self.error.geom(24, top, w - 48, 48)
            self.error.redraw()
            top += 48 + 8
        else:
            self.error.hide()
        tips_h = TipsCard.HEIGHT
        drop_h = h - 24 - tips_h - 8 - top
        self.drop.geom(24, top, w - 48, drop_h)
        self.tips.geom(24, h - 24 - tips_h, w - 48, tips_h)

    def refresh(self):
        super().refresh()

    def draw(self):
        pass
