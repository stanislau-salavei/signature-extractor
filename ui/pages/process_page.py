"""Screen 2 (05–09, 53, 57, 62; batch 14, 15, 38–42, 46): toolbar, preview, filter cards, fine-tuning,
bottom bar; in a batch also the reason line, InfoBars, the photo strip and «Применить ко всем»."""
from __future__ import annotations

import logging
from typing import List, Optional

from core import processing as P
from ui import gfx
from ui.pages.preview import Preview
from ui.theme import S, Theme, elide, text_width
from ui.widgets.scroll import ScrollArea
from ui.widgets.base import Box, Control
from ui.widgets.batch import STRIP_H, InfoBar, PhotoStrip
from ui.widgets.controls import Button, Link, IconButton, Segmented, Slider, Toggle, ToolButton

log = logging.getLogger(__name__)

RIGHT_W = 340
EX_TITLE_Y = 182      # remark 66: «Исключить цвет» label (centre y in the ink card)
EX_HINT_Y = 202       # first hint line


def doubt_text(t, doubts, sep: str = "\n") -> str:
    """Remark 62: the reasons a photo needs attention (codes from core.processing.DOUBT_CODES).
    Remark 89: one reason per line inside the yellow card (``sep`` = line break)."""
    return sep.join(t("batch.doubt." + c) for c in doubts if c in P.DOUBT_CODES)


def attention_reason(t, job) -> str:
    """Remark 89: the second line(s) of the yellow card for the selected photo — «not found» or the doubts."""
    if job is None:
        return ""
    if job.status == "attention":
        return t("batch.reason_not_found")
    if job.status == "doubt":
        return doubt_text(t, job.doubts)
    return ""


class Toolbar(Box):
    """Card 44 high, padding 0 6; tools 32 high with 4 px gaps; separator 1×22 with 8 px margins."""

    def __init__(self, master, app, page):
        super().__init__(master, bg="bg")
        self.app, self.page = app, page
        t = app.t
        self.frame = ToolButton(self, t("process.tool.frame"), "crop", command=lambda: page.set_tool("frame"))
        self.eraser = ToolButton(self, t("process.tool.eraser"), "eraser", command=lambda: page.set_tool("eraser"))
        self.reset = ToolButton(self, t("process.tool.reset_auto"), "reset", command=page.reset_frame,
                                tooltip=lambda: app.t("process.tool.reset_auto") if self.reset.icon_only else "")
        self.undo = ToolButton(self, "", "undo", command=app.undo, tooltip=lambda: app.t("process.tool.undo"))
        self.redo = ToolButton(self, "", "redo", command=app.redo, tooltip=lambda: app.t("process.tool.redo"))
        self.zoom_out = ToolButton(self, "", "zoom_out", command=lambda: page.preview.zoom_step(-1),
                                   tooltip=lambda: app.t("process.tool.zoom_out"))
        self.zoom_in = ToolButton(self, "", "zoom_in", command=lambda: page.preview.zoom_step(1),
                                  tooltip=lambda: app.t("process.tool.zoom_in"))
        self.fit = ToolButton(self, t("process.tool.fit"), "fit", command=lambda: page.preview.fit(),
                              tooltip=lambda: app.t("process.tool.fit") if self.fit.icon_only else "")
        self.sep_x = 0.0
        self.zoom_x = 0.0

    def labels(self):
        t = self.app.t
        for b, k in ((self.frame, "process.tool.frame"), (self.eraser, "process.tool.eraser"),
                     (self.reset, "process.tool.reset_auto"), (self.fit, "process.tool.fit")):
            b.label = t(k)

    def layout(self, x, y, w):
        self.geom(x, y, w, 44)
        self.labels()
        full = [self.frame, self.eraser, self.reset]
        right_full = self.fit.natural_width()
        need = 7 + sum(b.natural_width() for b in full) + 8 + 8 + 1 + 32 + 4 + 32 + 16 + \
            32 + 4 + 48 + 4 + 32 + 4 + right_full + 7
        compact = need > w
        self.reset.icon_only = compact
        self.fit.icon_only = compact
        bx = 7
        for b in full:
            bw = b.natural_width(icon_only=b.icon_only)
            b.geom(bx, 6, bw, 32)
            b.redraw()
            bx += bw + 4
        bx += 4  # 8 px before the separator
        self.sep_x = bx
        bx += 1 + 8
        self.undo.geom(bx, 6, 32, 32)
        self.redo.geom(bx + 36, 6, 32, 32)
        rx = w - 7
        fw = self.fit.natural_width(icon_only=compact)
        rx -= fw
        self.fit.geom(rx, 6, fw, 32)
        self.fit.redraw()
        rx -= 4 + 32
        self.zoom_in.geom(rx, 6, 32, 32)
        rx -= 4 + 48
        self.zoom_x = rx
        rx -= 4 + 32
        self.zoom_out.geom(rx, 6, 32, 32)
        self.redraw()

    def draw(self):
        w, h = self.lw, self.lh
        self.rrect(0, 0, w, h, 8, "card", "card_stroke")
        if self.sep_x:
            self.create_rectangle(S(self.sep_x), S(11), S(self.sep_x + 1), S(33), fill=Theme.c("vsep"), width=0)
        z = round(self.page.preview.zoom * 100)
        self.text(self.zoom_x + 24, 22, f"{z} %", 12, anchor="center")


class FilterCard(Box):
    """Filter card: header 62 (padding 10 14 10 16), title 13.5/600, description 12, toggle 40×20."""

    def __init__(self, master, app, title_key, desc_key, value, command):
        super().__init__(master, bg="bg")
        self.app, self.title_key, self.desc_key = app, title_key, desc_key
        self.toggle = Toggle(self, value, bg="card", show_label=False, command=command)
        self.body_h = 0.0

    def height(self):
        return 64 + (self.body_h if self.body_h else 0)

    def layout(self, x, y, w):
        h = self.height()
        self.geom(x, y, w, h)
        self.toggle.geom(w - 15 - 40, 22, 40, 20)
        self.redraw()

    def draw(self):
        w, h = self.lw, self.lh
        self.rrect(0, 0, w, h, 8, "card", "card_stroke")
        t = self.app.t
        self.text(17, 15.2 + 8, t(self.title_key), 13.5, "semibold")
        self.text(17, 33.2 + 7.8, t(self.desc_key), 12, color="muted")
        if self.body_h:
            self.create_rectangle(S(1), S(63), S(w - 1), S(64), fill=Theme.c("divider"), width=0)


class InkCard(FilterCard):
    def __init__(self, master, app, page):
        super().__init__(master, app, "process.filter.ink", "process.filter.ink_desc", True,
                         lambda v: page.set_param(ink_filter=v))
        self.page = page
        t = app.t
        self.seg = Segmented(self, [t("process.filter.auto"), t("process.filter.manual")], 0, bg="card",
                             command=self._mode)
        self.pick = Button(self, t("process.filter.eyedropper"), icon="pipette", bg="card", icon_size=15,
                           command=page.toggle_pipette)
        self.swatch = _Swatch(self, app)
        # remark 66 «Исключить цвет» (manual mode only, mockup_r66): second eyedropper, swatch, «×»
        self.ex_pick = Button(self, t("process.filter.eyedropper"), icon="pipette", bg="card", icon_size=15,
                              command=page.toggle_exclude_pipette)
        self.ex_swatch = _Swatch(self, app)
        self.ex_clear = IconButton(self, "dismiss", 12, bg="card", color="muted", hover_token="card_hover",
                                   command=page.clear_exclude, tooltip=lambda: app.t("process.filter.exclude_clear"))
        self.ex_color: Optional[str] = None
        self.ex_lines: List[str] = []
        self.state = "found"
        self.manual = False

    def _mode(self, i):
        self.page.set_param(ink_mode="manual" if i == 1 else "auto")

    def update_state(self, params: P.ProcessParams, res: Optional[P.ProcessResult], pipette: bool):
        self.toggle.set(params.ink_filter)
        self.manual = params.ink_mode == "manual"
        self.seg.set_index(1 if self.manual else 0)
        self.state = res.ink_state if res else ("manual" if self.manual else "found")
        target = getattr(self.page, "pipette_target", "ink")
        self.pick.text_color = "accent" if pipette and target == "ink" else None
        self.ex_pick.text_color = "accent" if pipette and target == "exclude" else None
        ex = params.exclude_rgb if self.manual else None
        self.ex_color = "#%02X%02X%02X" % tuple(ex) if ex else None
        if res is not None:
            rgb = params.ink_rgb if (self.manual and params.ink_rgb) else res.ink_rgb
            self.swatch.color = "#%02X%02X%02X" % tuple(rgb)
        self.hint_lines = []
        if params.ink_filter and not self.manual and self.state == "same":
            from ui.dialogs.content import wrap_runs
            self.hint_lines = ["".join(t for t, _ in ln) for ln in
                               wrap_runs([(self.app.t("process.filter.ink_auto_same"), "normal")], RIGHT_W - 34, 13)]
        if not params.ink_filter:
            self.body_h = 0
        elif self.hint_lines:
            self.body_h = 12 + 36 + 10 + 18 * len(self.hint_lines) + 8 + 32 + 14 + 1
        else:
            self.body_h = 105
        self.ex_lines = []
        if params.ink_filter and self.manual:
            from ui.dialogs.content import wrap_runs
            key = "process.filter.exclude_note" if self.ex_color else "process.filter.exclude_hint"
            self.ex_lines = ["".join(t for t, _ in ln) for ln in
                             wrap_runs([(self.app.t(key), "normal")], RIGHT_W - 34, 12)]
            # ink row ends at 154; «Исключить цвет» 182; hint lines from 202; eyedropper row after them
            self.body_h = (EX_HINT_Y - 9 + 18 * len(self.ex_lines) + 8 + 32 + 15) - 64

    def _ex_top(self) -> float:
        return EX_HINT_Y - 9 + 18 * len(self.ex_lines) + 8

    def layout(self, x, y, w):
        super().layout(x, y, w)
        t = self.app.t
        if not self.body_h:
            for wd in (self.seg, self.pick, self.swatch, self.ex_pick, self.ex_swatch, self.ex_clear):
                wd.hide()
            return
        self.seg.labels = [t("process.filter.auto"), t("process.filter.manual")]
        self.seg.geom(17, 76, w - 34, 36)
        self.seg.redraw()
        self.pick.set_text(t("process.filter.eyedropper"))
        pw = self.pick.natural_width()
        if self.manual:
            self.pick.geom(17, 122, pw, 32)
            self.swatch.round, self.swatch.caption = False, ""
            self.swatch.geom(17 + pw + 10, 124, 28, 28)
        elif self.hint_lines:
            self.swatch.hide()
            self.pick.geom(17, 122 + 18 * len(self.hint_lines) + 8, pw, 32)
        else:
            self.pick.hide()
            self.swatch.round, self.swatch.caption = True, t("process.filter.ink_auto_found")
            self.swatch.geom(17, 122, w - 34, 32)
        self.pick.redraw()
        self.swatch.redraw()
        self._layout_exclude()
        self.redraw()

    def _layout_exclude(self):
        if not self.ex_lines:
            for wd in (self.ex_pick, self.ex_swatch, self.ex_clear):
                wd.hide()
            return
        top = self._ex_top()
        self.ex_pick.set_text(self.app.t("process.filter.eyedropper"))
        pw = self.ex_pick.natural_width()
        self.ex_pick.geom(17, top, pw, 32)
        self.ex_pick.redraw()
        if self.ex_color:
            self.ex_swatch.round, self.ex_swatch.caption, self.ex_swatch.color = False, "", self.ex_color
            self.ex_swatch.geom(17 + pw + 10, top + 2, 28, 28)
            self.ex_clear.geom(17 + pw + 10 + 28 + 6, top + 2, 28, 28)
            self.ex_swatch.redraw()
            self.ex_clear.redraw()
        else:
            self.ex_swatch.hide()
            self.ex_clear.hide()

    def draw(self):
        super().draw()
        for i, line in enumerate(getattr(self, "hint_lines", [])):
            self.text(17, 122 + 9 + 18 * i, line, 13, color="muted")
        if self.ex_lines and self.body_h:
            self.text(17, EX_TITLE_Y, self.app.t("process.filter.exclude"), 13)
            for i, line in enumerate(self.ex_lines):
                self.text(17, EX_HINT_Y + 18 * i, line, 12, color="muted")


class _Swatch(Box):
    """Manual: 28×28 square swatch. Auto: 20 px round swatch + «Цвет чернил: найден автоматически»."""

    def __init__(self, master, app):
        super().__init__(master, bg="card")
        self.app = app
        self.color = "#1B2A8A"
        self.round = False
        self.caption = ""
        self.bind("<Enter>", lambda e: self._tip())
        self.bind("<Leave>", lambda e: _cancel_tip(self))

    def _tip(self):
        from ui.widgets.base import Tooltip
        Tooltip.schedule(self, lambda: self.color)  # HEX only in the tooltip

    def draw(self):
        if self.round:
            st = gfx.rgba("#000000", 0.26)
            self.put_cached(0, 6, ("inks", self.color, Theme.mode),
                            lambda: gfx.circle(20, self.color, "#424242" if not Theme.dark() else "#5A5A5A"))
            self.text(30, 16, self.caption, 13)
        else:
            self.rrect(0, 0, 28, 28, 4, self.color, "swatch_stroke")


def _cancel_tip(w):
    from ui.widgets.base import Tooltip
    Tooltip.cancel(w)


class FineTuneCard(Box):
    """«Тонкая настройка»: collapsed 54 (header 52), open = header 62 + body 140."""

    def __init__(self, master, app, page):
        super().__init__(master, bg="bg")
        self.app, self.page = app, page
        self.open = False
        self.reset = Link(self, app.t("process.finetune.reset"), 12.5, "accent_text", bg="card",
                          command=page.reset_finetune)
        self.chev = IconButton(self, "chev_down16", 16, bg="card", command=self.toggle, hover_token="card_hover")
        self.sliders = [
            Slider(self, 0, 100, P.DEFAULT_SENSITIVITY, bg="card", command=lambda v: self._live(),
                   on_release=lambda v: page.set_param(sensitivity=int(v))),
            Slider(self, 0, 100, P.DEFAULT_DENOISE, bg="card", command=lambda v: self._live(),
                   on_release=lambda v: page.set_param(denoise=int(v))),
            Slider(self, -3, 3, 0, bg="card", command=lambda v: self._live(),
                   on_release=lambda v: page.set_param(thickness=int(v))),
        ]
        self.bind("<ButtonRelease-1>", self._click)

    def _click(self, e):
        if e.y < S(52):
            self.toggle()

    def toggle(self):
        self.open = not self.open
        self.page.layout_right()

    def _live(self):
        self.redraw()

    def height(self):
        return 1 + 62 + 140 + 1 if self.open else 54

    def set_values(self, p: P.ProcessParams):
        for sl, v in zip(self.sliders, (p.sensitivity, p.denoise, p.thickness)):
            if sl.value != v:
                sl.set(v)

    def layout(self, x, y, w):
        self.geom(x, y, w, self.height())
        hh = 62 if self.open else 52
        self.chev.icon_name = "chev_up" if self.open else "chev_down16"
        self.chev.geom(w - 15 - 20, 1 + (hh - 20) / 2, 20, 20)
        self.chev.redraw()
        self.reset.set_text(self.app.t("process.finetune.reset"))
        rw = self.reset.natural_width()
        self.reset.geom(w - 15 - 20 - 12 - rw - 4, 1 + (hh - 15) / 2, rw, 15)
        for i, sl in enumerate(self.sliders):
            if self.open:
                top = 63 + 12 + 3 + 41 * i
                sl.geom(17 - 10, top + 25 + 2 - 10, w - 34 + 20, 20)
            else:
                sl.hide()
        self.redraw()

    def draw(self):
        w, h = self.lw, self.lh
        self.rrect(0, 0, w, h, 8, "card", "card_stroke")
        hh = 62 if self.open else 52
        self.text(17, 1 + hh / 2, self.app.t("process.finetune"), 13.5, "semibold")
        if not self.open:
            return
        self.create_rectangle(S(1), S(63), S(w - 1), S(64), fill=Theme.c("divider"), width=0)
        t = self.app.t
        for i, (key, sl) in enumerate(zip(("process.finetune.sensitivity", "process.finetune.denoise",
                                           "process.finetune.thickness"), self.sliders)):
            top = 63 + 12 + 3 + 41 * i
            self.text(17, top + 8, t(key), 13)
            v = int(sl.value)
            if i == 2:
                val = "±0" if v == 0 else (f"+{v}" if v > 0 else f"−{abs(v)}")
            else:
                val = str(v)
            self.text(w - 17, top + 8.5, val, 12, color="muted", anchor="e")


class BottomBar(Box):
    """64 px, top line, «Назад» (secondary, ← icon) and «Далее: экспорт» (primary, → icon), gap 10."""

    def __init__(self, master, app, back_cmd, next_cmd, next_key="process.next", next_tip="process.next.tooltip"):
        super().__init__(master, bg="abar")
        self.app = app
        self.back = Button(self, app.t("common.back"), icon="arrow_left", bg="abar", command=back_cmd)
        self.next = Button(self, app.t(next_key), kind="primary", icon="arrow_right", icon_right=True, bg="abar",
                           command=next_cmd, tooltip=(lambda: app.t(next_tip)) if next_tip else None)
        self.next_key = next_key

    def layout(self, x, y, w):
        self.geom(x, y, w, 64)
        self.back.set_text(self.app.t("common.back"))
        self.next.set_text(self.app.t(self.next_key))
        nw = self.next.natural_width()
        bw = self.back.natural_width()
        self.next.geom(w - 24 - nw, 16.5, nw, 32)
        self.back.geom(w - 24 - nw - 10 - bw, 16.5, bw, 32)
        self.redraw()

    def draw(self):
        self.create_rectangle(0, 0, S(self.lw), S(1), fill=Theme.c("abar_line"), width=0)


class ProcessPage(Box):
    def __init__(self, master, app):
        super().__init__(master, bg="bg")
        self.app = app
        self.preview = Preview(self, app, self)
        self.toolbar = Toolbar(self, app, self)
        # remark 17: the right column scrolls (thin Win11 bar only on overflow, mouse wheel)
        self.area = ScrollArea(self)
        col = self.area.inner
        self.c_flat = FilterCard(col, app, "process.filter.flatten", "process.filter.flatten_desc", True,
                                 lambda v: self.set_param(flatten=v))
        self.c_ink = InkCard(col, app, self)
        self.c_fine = FineTuneCard(col, app, self)
        self.bar = BottomBar(self, app, app.go_home_confirm if hasattr(app, "go_home_confirm") else
                             (lambda: app.on_step_click(0)), app.go_export)
        self.meta = ""
        # stage 4 (batch)
        self.skip_bar = InfoBar(self, app, "info", link=app.show_skipped_list, close=app.close_skipped_bar)
        self.warn_bar = InfoBar(self, app, "warn", action=app.show_next_attention)
        self.ok_bar = InfoBar(self, app, "ok")
        self.strip = PhotoStrip(self, app, on_select=app.select_photo, on_add=app.add_photos_dialog,
                                on_remove=app.ask_remove_photo)
        self.apply_btn = Button(self, app.t("batch.apply_settings_all"), icon="apply_all", bg="bg", command=app.apply_to_all)
        self.bar.next.tooltip = self._next_tip
        self.bar.next.tip_wrap = 230          # 39: the long hint wraps like the mockup tooltip
        self.meta_y = 0.0
        self.pipette_target = "ink"      # remark 66: which eyedropper is active («ink» | «exclude»)
        app.root.bind_all("<ButtonPress-1>", self._outside_press, add="+")

    def _next_tip(self):
        b = self.app.batch
        if b is not None and self.bar.next.disabled:
            n = len(b.blocking())           # remark 48: only «not found» keeps «Далее» closed
            return self.app.tn("batch.attention_tooltip", n) if n else ""
        return self.app.t("process.next.tooltip")

    def _outside_press(self, e):
        """A left click anywhere outside the preview (and outside the toolbar that drives it)
        turns the active tool off (remark 6)."""
        if self.preview.tool is None or not self.visible:
            return
        w = e.widget
        if isinstance(w, str):
            return
        while w is not None:
            if w is self.preview or w is self.toolbar:
                return
            w = getattr(w, "master", None)
        self.set_tool(None)

    # ------------------------------------------------------------------ app hooks
    def hide(self):
        super().hide()
        self.area.hide()

    def refresh(self):
        super().refresh()
        self.area.refresh_bg()

    def on_show(self):
        self.area.bind_wheel()
        self.preview.fit()
        self.preview.set_tool(None)   # no tool by default (remark 6)
        self.sync_controls()
        self.layout(self.lw, self.lh)
        if self.app.batch is not None:
            self.after_idle(self.strip.ensure_visible)

    def on_result(self):
        self.preview.invalidate("all")
        self.sync_controls()
        self.layout(self.lw, self.lh)       # remark 70: the yellow bar for one photo too

    def on_switch(self):
        """Another batch photo became current (strip click, ←/→, removal)."""
        self.preview.set_tool(None)
        self.preview.set_pipette(False)
        self._pick_look(False)
        self.preview._live = None
        self.preview._await = None
        self.preview.fit()
        self.strip.ensure_visible()
        self.sync_controls()
        self.layout(self.lw, self.lh)

    def on_batch_changed(self):
        self.sync_controls()
        self.layout(self.lw, self.lh)

    def on_zoom(self):
        self.toolbar.redraw()

    def sync_controls(self):
        job = self.app.job
        if not job:
            return
        p = job.state.params
        res = job.result
        self.c_flat.toggle.set(p.flatten)
        self.c_ink.update_state(p, res, self.preview.pipette)
        self.c_fine.set_values(p)
        self.toolbar.undo.set_disabled(not job.history.can_undo())
        self.toolbar.redo.set_disabled(not job.history.can_redo())
        self.toolbar.frame.set_on(self.preview.tool == "frame")
        self.toolbar.eraser.set_on(self.preview.tool == "eraser")
        self.bar.next.set_disabled(not self.app.can_export())
        if self.app.batch is not None:
            self.apply_btn.set_disabled(len(self.app.batch.items) < 2)
            self.strip.refresh_items()
        self.layout_right()
        self.preview.redraw()
        self.redraw()

    # ------------------------------------------------------------------ actions
    def set_tool(self, tool):
        """Toolbar click: turn the tool on, or off when it is already active."""
        if tool is not None and tool == self.preview.tool:
            tool = None
        self.preview.set_tool(tool)
        self.toolbar.frame.set_on(tool == "frame")
        self.toolbar.eraser.set_on(tool == "eraser")
        if self.c_ink.pick.visible:
            self._pick_look(False)

    def toggle_pipette(self):
        self._toggle_pipette("ink")

    def toggle_exclude_pipette(self):
        """Remark 66: the second eyedropper «Исключить цвет» — only one eyedropper is active at a time."""
        self._toggle_pipette("exclude")

    def _toggle_pipette(self, target):
        on = not (self.preview.pipette and self.pipette_target == target)
        self.pipette_target = target
        self.preview.set_pipette(on)
        self._pick_look(on)

    def _pick_look(self, on):
        target = self.pipette_target
        self.c_ink.pick.text_color = "accent" if on and target == "ink" else None
        self.c_ink.ex_pick.text_color = "accent" if on and target == "exclude" else None
        self.c_ink.pick.redraw()
        self.c_ink.ex_pick.redraw()

    def on_pipette(self, rgb):
        target = self.pipette_target
        self.preview.set_pipette(False)
        self._pick_look(False)
        self.pipette_target = "ink"
        if target == "exclude":
            self.app.edit(exclude_rgb=tuple(rgb))
        else:
            self.app.edit(ink_mode="manual", ink_rgb=tuple(rgb))
        self.sync_controls()

    def clear_exclude(self):
        self.set_param(exclude_rgb=None)

    def on_erase(self, stroke):
        job = self.app.job
        self.app.edit(eraser=tuple(job.state.eraser) + (stroke,))
        self.sync_controls()

    def on_frame(self, fr):
        self.app.edit(frame=fr)
        self.sync_controls()

    def reset_frame(self):
        job = self.app.job
        if job and job.state.frame is not None:
            self.app.edit(frame=None)
            self.sync_controls()

    def set_param(self, **kw):
        job = self.app.job
        if not job:
            return
        if all(getattr(job.state.params, k) == v for k, v in kw.items()):
            return
        self.app.edit(**kw)
        self.sync_controls()

    def reset_finetune(self):
        self.set_param(sensitivity=P.DEFAULT_SENSITIVITY, denoise=P.DEFAULT_DENOISE, thickness=P.DEFAULT_THICKNESS)
        self.c_fine.redraw()

    # ------------------------------------------------------------------ layout
    def layout(self, w, h):
        if w <= 0 or h <= 0:
            return
        self.geom(0, 64, w, h)
        lw = w - 24 - 24 - 16 - RIGHT_W
        col_h = h - 64 - 16
        self.toolbar.layout(24, 0, lw)
        b = self.app.batch
        job = self.app.job
        y = 52.0
        bars = []
        # remark 89: in every «Требует внимания» case the reason is the second line (one line per reason)
        # INSIDE the yellow card, like the card of remark 74; no reason bar above the preview (40), no ⚠ line
        reason = attention_reason(self.app.t, job)
        if b is not None and job is not None:
            t, tn = self.app.t, self.app.tn
            if b.skipped_large and not b.skipped_closed:
                n = len(b.skipped_large)
                self.skip_bar.set(tn("batch.skipped_large_bar", n), link=t("common.more_info"))
                bars.append(self.skip_bar)
            else:
                self.skip_bar.hide()
            state = b.bar_state()
            if state == "warn":
                n = len(b.attention())
                # remark 89: the selected photo's reason is the second line; remark 90: without a reason of its
                # own there is no second line (no «Поправьте их или уберите из пакета…»)
                self.warn_bar.set(tn("batch.attention_bar", n), reason, action=t("common.show"))
                bars.append(self.warn_bar)
            else:
                self.warn_bar.hide()
            if state == "ok":
                self.ok_bar.set(t("batch.all_ready"))
                bars.append(self.ok_bar)
            else:
                self.ok_bar.hide()
            # bottom-up: strip, InfoBars, meta line
            by = col_h - STRIP_H
            self.strip.layout(24, by, lw)
            for bar in reversed(bars):
                by -= 8 + bar.height()
                bar.layout(24, by, lw)
            self.meta_y = by - 8 - 12
        elif job is not None and reason:
            # remarks 70 / 74 / 77 / 89: one photo (no strip) — the yellow card «Требует внимания» (no «Показать»)
            # under the image, where the batch shows its bar, with the reason(s) inside
            for wd in (self.skip_bar, self.ok_bar, self.strip):
                wd.hide()
            self.warn_bar.set(self.app.t("batch.attention"), reason, action="")
            by = col_h - self.warn_bar.height()
            self.warn_bar.layout(24, by, lw)
            self.meta_y = by - 8 - 12
        else:
            for wd in (self.skip_bar, self.warn_bar, self.ok_bar, self.strip):
                wd.hide()
            self.meta_y = col_h - 12
        ph = max(40.0, self.meta_y - 8 - y)
        self.preview.geom(24, y, lw, ph)
        self.preview.redraw()
        self.layout_right()
        self.bar.layout(0, h - 64, w)
        self.redraw()

    def layout_right(self):
        if self.lw <= 0:
            return
        x = self.lw - 24 - RIGHT_W
        y = 0.0
        for c in (self.c_flat, self.c_ink, self.c_fine):
            c.layout(0, y, RIGHT_W)
            y += c.height() + 8
        col_h = self.lh - 64 - 16
        if self.app.batch is not None:
            # «Применить ко всем» stays at the bottom of the right column; the cards scroll above it
            self.apply_btn.set_text(self.app.t("batch.apply_settings_all"))
            self.apply_btn.geom(x, col_h - 32, RIGHT_W, 32)
            self.apply_btn.redraw()
            col_h -= 32 + 8
        else:
            self.apply_btn.hide()
        self.area.geom(x, 0, RIGHT_W + 12, col_h, y - 8)

    def draw(self):
        job = self.app.job
        if not job:
            return
        app = self.app
        res = job.result
        if app.batch is not None:
            if job.status == "attention":
                txt = app.t("batch.meta_not_found", file=job.name)
            elif not job.processed:
                txt = job.name
            else:
                txt = app.tn("process.meta_batch", job.stroke_count, forms_from="process.meta", file=job.name,
                             w=app.fmt_num(job.size_mm[0]), h=app.fmt_num(job.size_mm[1]))
        else:
            if not res:
                return
            txt = app.tn("process.meta", res.stroke_count, w=app.fmt_num(res.size_mm[0]), h=app.fmt_num(res.size_mm[1]))
        if res is not None and res.frame_is_large and job.status != "attention":
            txt += " · " + app.t("process.meta.frame_large")     # remark 69: Help text got longer
        self.text(26, self.meta_y + 6, elide(txt, self.preview.lw - 4, 12), 12, color="muted")
