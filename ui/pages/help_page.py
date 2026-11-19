"""«Справка» page (remark 30, 2026-11-17): opened from the ⋯ menu as a page in the main window,
like «Параметры» — «Назад» (←) at the top left, «Справка» title, a Win11 NavigationView-style list of
topics on the left (22–26: 232 px, items 36 high, 2 apart, the selected one filled with a 3 px accent
bar) and the topic text on the right, scrolled by the wheel and a thin bar.  Esc goes back.
Contextual help on the screens (screen 1 «Как подготовить фото», «Справка по форматам экспорта»)
stays an in-window dialog (ui/dialogs/formats_help.HelpWindow).
Remark 41 (2026-11-18): every section is a card with an icon, as in the mockups 22–26; remark 42: «Подготовка
фото» starts with the «хорошо / плохо» photo examples (mockup_r42 v2).
Stage 5 (2k_25): header and body (topics + text) are at most 1000 px wide and centred on a wide window."""
from __future__ import annotations

from ui.dialogs.formats_help import _Content, topic_blocks
from ui.theme import Theme
from ui.widgets.base import Box, Control
from ui.widgets.controls import IconButton
from ui.widgets.scroll import ScrollArea

TOPICS = ("start", "prep", "process", "batch", "formats")
NAV_W, NAV_GAP, ITEM_H, ITEM_STEP = 232, 28, 36, 38
SIDE = 56
TOP = 80
PAGE_MAX_W = 1000      # .phd / .body {max-width: 1000px; margin: 0 auto} in 2k_25


class _NavItem(Control):
    def __init__(self, master, page, topic):
        super().__init__(master, bg="bg", command=lambda: page.show_topic(topic))
        self.page, self.topic = page, topic

    def draw(self):
        w, h = self.lw, self.lh
        sel = self.page.topic == self.topic
        if sel or self.hover or self.pressed:
            tok = "ctl_press" if self.pressed else ("ctl" if sel else "ctl_hover")
            self.rrect(0, 0, w, h, 4, tok)
        if sel:
            self.rrect(0, 8, 3, h - 16, 1.5, "accent", bg="ctl")
        self.icon(f"help_{self.topic}", 12, (h - 16) / 2, 16, "accent" if sel else "muted")
        self.text(12 + 16 + 12, h / 2, self.page.app.t(f"help.nav.{self.topic}"), 13.5,
                  "semibold" if sel else "normal")


class HelpPage(Box):
    def __init__(self, master, app):
        super().__init__(master, bg="bg")
        self.app = app
        self.topic = "start"
        self.back = IconButton(self, "back", 16, bg="bg", command=app.close_help,
                               tooltip=lambda: app.t("common.back"))
        self.nav = [_NavItem(self, self, tp) for tp in TOPICS]
        self.area = ScrollArea(self)
        self.content = None
        self.content_h = 0.0

    # ------------------------------------------------------------------ state
    def blocks(self):
        t = self.app.t
        return [("title", t(f"help.nav.{self.topic}"))] + topic_blocks(self.app, self.topic)

    def show_topic(self, topic):
        if topic not in TOPICS:
            topic = "start"
        changed = topic != self.topic
        self.topic = topic
        for it in self.nav:
            it.redraw()
        self.layout_content(reset=True if changed else False)

    def on_show(self, topic="start"):
        self.topic = topic if topic in TOPICS else "start"
        self.area.bind_wheel()

    def hide(self):
        super().hide()
        self.area.hide()

    def key(self, d):
        self.area.scroll_by(d * 40)

    # ------------------------------------------------------------------ layout
    def column(self, w=None):
        """(left, width) of header + topics + text: 56 px sides, at most 1000 px, centred (2k_25)."""
        w = self.lw if w is None else w
        bw = min(w - 2 * SIDE, PAGE_MAX_W)
        return round((w - bw) / 2, 1), bw

    def layout(self, w, h):
        self.geom(0, 0, w, h)
        x0, _ = self.column(w)
        # same header geometry as «Параметры» (back 3,22; title at 56)
        self.back.geom(x0 - 53, 22, 36, 36)
        for i, it in enumerate(self.nav):
            it.geom(x0, TOP + 2 + ITEM_STEP * i, NAV_W, ITEM_H)
            it.redraw()
        self.redraw()
        self.layout_content(reset=False)

    def layout_content(self, reset=False):
        if self.lw <= 0:
            return
        x0, bw = self.column()
        cx = x0 + NAV_W + NAV_GAP
        cw = self.lw - cx                 # the area runs to the window edge (the bar overlays it there)
        text_w = x0 + bw - cx             # text stops at the column edge (56 px from the window on 1280)
        blocks = self.blocks()
        kw = dict(bg="bg", text_w=text_w, pad_l=0, pad_t=2, page=True)   # remark 41: icon cards (22–26)
        self.content_h = _Content.measure_blocks(self, blocks, **kw)
        if self.content is not None:
            self.content.destroy()
        if reset:
            self.area.scroll = 0.0
        self.area.geom(cx, TOP, cw, self.lh - TOP, self.content_h)
        self.content = _Content(self.area.inner, blocks, **kw)
        self.content.geom(0, 0, cw - 14, self.content_h)
        self.content.redraw()
        self.area.bar.lift()

    def draw(self):
        self.text(self.column()[0], 40, self.app.t("menu.help"), 20, "semibold")

    def refresh(self):
        super().refresh()
        self.area.refresh_bg()
        if self.visible:
            self.layout_content()
