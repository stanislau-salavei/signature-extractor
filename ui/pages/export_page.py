"""Screen 3 (11–13, 33–35, 48, 54, 58–61; batch 16–18, 44, 63): size, colour, PNG / SVG / DXF, preview,
single save; in a batch also the photo strip, the file count card and «Сохранить в папку…»."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from tkinter import filedialog
from typing import Dict, List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageTk

from core import batch as B
from core import export as ex
from ui import gfx
from ui.theme import F, S, Scale, Theme, blend, elide, text_width
from ui.widgets.base import Box, Control, Tooltip
from ui.widgets.controls import Button, ComboBox, IconButton, Link, Radio, Segmented, TextBox, Toggle
from ui.widgets.overlay import MenuItem, MenuPopup, _paste_clip
from ui.widgets.scroll import ScrollArea
from ui.widgets.batch import STRIP_H, DimLayer, PhotoStrip

log = logging.getLogger(__name__)

LEFT_W = 424
MARGIN_ROW_H = 73   # «Поле рамки» row in the expanded «Размер подписи» card
NUM_FIT = "12,34"   # remark 33: number fields show this in full with «×» visible
CUSTOM_GAP = 16     # remark 33: «Свой размер» gap between the Width field and «Высота» (24 → 16)
SIZE_COMBO_W = 210
TEMPLATE_ROW_H = 8 + 17 + 16   # remark 34: «Удалить шаблон» link row (same link as «Сохранить как шаблон»)
TILE = {  # format tile colours (light, dark): fg, bg
    "PNG": (("#0F7B0F", "#E7F5EA"), ("#6CCB5F", "#1E3A23")),
    "SVG": (("#8A5A00", "#FFF3D6"), ("#FCE100", "#3D3414")),
    "DXF": (("#005FB8", "#E3F0FB"), ("#60CDFF", "#16304A")),
}
CHECKER = {"light": ("#FFFFFF", "#E6E8EC"), "dark": ("#2A2A2A", "#1C1C1C")}


def _num_allowed(text: str) -> bool:
    import re
    return re.fullmatch(r"\d{0,3}([.,]\d?)?", text) is not None


def _line_allowed(text: str) -> bool:
    """DXF line thickness: up to 5 mm with two decimals (0,18)."""
    import re
    return re.fullmatch(r"\d?([.,]\d{0,2})?", text) is not None


class Card(Box):
    """Rounded card with an optional expandable body (header height ``head_h``)."""

    def __init__(self, master, page, head_h):
        super().__init__(master, bg="bg")
        self.page, self.head_h = page, head_h
        self.body_h = 0.0

    def height(self):
        return self.head_h + (self.body_h if self.body_h else 0)

    def draw_base(self):
        w, h = self.lw, self.lh
        self.rrect(0, 0, w, h, 8, "card", "card_stroke")
        if self.body_h:
            self.create_rectangle(S(1), S(self.head_h - 1), S(w - 1), S(self.head_h), fill=Theme.c("divider"), width=0)


class SizeCard(Card):
    def __init__(self, master, page):
        super().__init__(master, page, 58)
        app = page.app
        # remark 35: the field stays 210 wide (no room in the card header); long template names get «…»,
        # the list measures its items and grows up to the window width
        self.combo = ComboBox(self, app, bg="card", width=SIZE_COMBO_W, max_width=SIZE_COMBO_W, font_px=13, chev_px=12,
                              min_list_width=236, command=page.select_size_index)
        # remark 33: number fields fit «12,34» with «×» visible
        self.w_box = TextBox(self, app, "20", width=0, fit=NUM_FIT, bg="card", allow=_num_allowed,
                             on_apply=lambda t: page.set_custom("w", t))
        self.h_box = TextBox(self, app, "8", width=0, fit=NUM_FIT, bg="card", allow=_num_allowed,
                             on_apply=lambda t: page.set_custom("h", t))
        self.save_link = Link(self, "", 13, "accent_text", bg="card", command=page.save_template)
        # remark 34: a saved template is selected → «Удалить шаблон», same blue link as «Сохранить как шаблон»
        self.delete_link = Link(self, "", 13, "accent_text", bg="card", command=page.delete_template)
        # remark 15: «Поле рамки» lives here (it applies to every size mode and format)
        self.chev = IconButton(self, "chev_down16", 16, bg="card", command=page.toggle_size, hover_token="card_hover")
        self.margin = TextBox(self, app, "0,5", width=0, fit=NUM_FIT, bg="card", allow=_num_allowed,
                              on_apply=page.apply_margin)
        self.bind("<ButtonRelease-1>", lambda e: page.toggle_size() if e.y < S(58) else None)
        self.mode = "none"   # none | custom | nodpi | template
        self._mt = 0.0       # top of the margin row
        self._x2 = 0.0       # x of «Высота» in «Свой размер» (remark 33: set before the first draw)

    def layout(self, x, y, w):
        p = self.page
        t = p.app.t
        if p.size_key == ex.SIZE_CUSTOM:
            self.mode = "custom"
        elif p.size_key == ex.SIZE_ORIGINAL and p.source is not None and not p.source.has_dpi \
                and p.app.batch is None:   # decision 6: a batch shows the line under the preview (63)
            self.mode = "nodpi"
        elif p.selected_template() is not None:
            self.mode = "template"
        else:
            self.mode = "none"
        mode_h = {"custom": 85.9, "nodpi": 41.8, "template": TEMPLATE_ROW_H, "none": 0}[self.mode]
        self._mt = 58 + mode_h
        self.body_h = mode_h + (MARGIN_ROW_H if p.size_open else 0)
        self.geom(x, y, w, self.height())
        self.chev.icon_name = "chev_up" if p.size_open else "chev_down16"
        self.chev.geom(w - 15 - 20, 19, 20, 20)
        self.chev.redraw()
        cbw = self.combo.natural_width()
        self.combo.geom(w - 15 - 20 - 12 - cbw, 13, cbw, 32)
        self.combo.redraw()
        if p.size_open:
            self.margin.set(ex.format_plain_number(p.margin_mm, p.app.i18n.lang))
            self.margin.geom(w - 17 - self.margin.natural_width(), self._mt + 20, self.margin.natural_width(), 32)
        else:
            self.margin.hide()
        if self.mode == "custom":
            lw1 = text_width(t("export.size.width"), 13)
            self.w_box.geom(17 + lw1 + 10, 72, self.w_box.natural_width(), 32)
            x2 = 17 + lw1 + 10 + self.w_box.natural_width() + CUSTOM_GAP
            lw2 = text_width(t("export.size.height"), 13)
            self.h_box.geom(x2 + lw2 + 10, 72, self.h_box.natural_width(), 32)
            self._x2 = x2
            self.save_link.set_text(t("export.size.save_template"))
            self.save_link.geom(17, 116, self.save_link.natural_width(), 17)
        else:
            for wd in (self.w_box, self.h_box, self.save_link):
                wd.hide()
        if self.mode == "template":
            self.delete_link.set_text(t("export.size.delete_template"))
            self.delete_link.geom(17, 58 + 8, self.delete_link.natural_width(), 17)
        else:
            self.delete_link.hide()
        self.redraw()

    def draw(self):
        self.draw_base()
        t = self.page.app.t
        self.text(17, 29, t("export.size"), 13.5, "semibold")
        if self.mode == "custom":
            self.text(17, 88, t("export.size.width"), 13)
            self.text(self._x2, 88, t("export.size.height"), 13)
        elif self.mode == "nodpi":
            self.text(17, 72 + 8.4, t("export.size.no_dpi"), 12, color="muted")
        if self.page.size_open:
            mt = self._mt
            if self.mode != "none":   # hairline between the size options and the margin row
                self.create_rectangle(S(1), S(mt - 1), S(self.lw - 1), S(mt), fill=Theme.c("divider"), width=0)
            self.text(17, mt + 20, t("export.png.margin"), 13)
            self.create_text(S(17), S(mt + 29), text=t("settings.margin.desc"), font=F(12), fill=Theme.c("muted"),
                             anchor="nw", width=S(270))


class Swatch(Control):
    """Colour circle 28 (selected: 2 px card ring + 2 px accent ring); «Как на фото» and «+» variants."""

    def __init__(self, master, page, key, kind, hx, tip, custom):
        super().__init__(master, bg="card", command=lambda: page.select_color(key),
                         tooltip=lambda: tip)
        self.page, self.key, self.kind, self.hx, self.custom = page, key, kind, hx, custom
        if custom:
            self.bind("<ButtonPress-3>", self._ctx)

    def _ctx(self, e):
        from ui.widgets.overlay import widget_rect
        x, y, w, h = widget_rect(self.page.app.root, self)
        MenuPopup(self.page.app, [MenuItem(self.page.app.t("common.delete"),
                                           lambda: self.page.ask_delete_color(self.key), "trash")],
                  x + e.x / Scale.factor + 2, y + e.y / Scale.factor + 8)

    def draw(self):
        sel = self.key == self.page.color_key
        bgc = Theme.c("card")
        cx = cy = 16  # widget 32×32, circle 28 centred
        if sel:
            self.put_cached(0, 0, ("swr", Theme.mode), lambda: gfx.circle(32, Theme.c("accent"), bg=bgc))
            self.put_cached(2, 2, ("swr2", Theme.mode), lambda: gfx.circle(28, bgc, bg=None))
        d = 24 if sel else 28
        o = (32 - d) / 2
        if self.kind == "photo":
            self.put_cached(o, o, ("swp", d, Theme.mode, self.hover),
                            lambda: gfx.circle(d, Theme.c("ctl_hover" if self.hover else "ctl"), Theme.c("ctl_stroke_bottom")))
            self.icon("pipette", 16 - 7, 16 - 7, 14, "text")
        elif self.kind == "add":
            self.put_cached(2, 2, ("swa", Theme.mode, self.hover),
                            lambda: gfx.dashed_rrect(28, 28, 14, Theme.c("check_off_stroke"), 1, 3, 2.2))
            self.icon("plus", 16 - 6, 16 - 6, 12, "muted")
        else:
            st = blend("#000000", 0.26, self.hx) if not Theme.dark() else blend("#FFFFFF", 0.35, self.hx)
            self.put_cached(o, o, ("swc", d, self.hx, Theme.mode), lambda: gfx.circle(d, self.hx, st))


SWATCH_STEP = 38             # swatch 32 + gap 6
COLOR_DELETE_ROW_H = 26      # remark 58: «Удалить цвет» under the swatches (6 + link 17 + 14 − the usual 11)


class ColorCard(Card):
    def __init__(self, master, page):
        super().__init__(master, page, 58)
        self.chev = IconButton(self, "chev_down16", 16, bg="card", command=page.toggle_color, hover_token="card_hover")
        self.swatches: List[Swatch] = []
        # remark 58: an own colour is selected → «Удалить цвет», the same blue link as «Удалить шаблон»
        self.delete_link = Link(self, "", 13, "accent_text", bg="card",
                                command=lambda: page.ask_delete_color(page.color_key))
        self.rows = 1
        self.bind("<ButtonRelease-1>", lambda e: page.toggle_color() if e.y < S(58) else None)

    def rebuild(self):
        for s in self.swatches:
            s.destroy()
        p = self.page
        self.swatches = [Swatch(self, p, k, kind, hx, tip, custom) for k, kind, hx, tip, custom in p.color_items()]
        t = p.app.t
        self.swatches.append(Swatch(self, p, "__add__", "add", None, t("color.custom"), False))
        self.swatches[-1].command = p.add_color

    def per_row(self, w) -> int:
        """Remark 58: swatches wrap to the next line instead of running past the card edge."""
        return max(1, int((w - 15 - 15 + 6) // SWATCH_STEP))

    def layout(self, x, y, w):
        p = self.page
        n = len(self.swatches)
        per = self.per_row(w)
        self.rows = max(1, -(-n // per))
        own = p.color_key.startswith(ex.CUSTOM_COLOR_PREFIX)
        self.body_h = (51 + SWATCH_STEP * (self.rows - 1) + (COLOR_DELETE_ROW_H if own else 0)) if p.color_open else 0
        self.geom(x, y, w, self.height())
        self.chev.icon_name = "chev_up" if p.color_open else "chev_down16"
        self.chev.geom(w - 15 - 20, 19, 20, 20)
        self.chev.redraw()
        for i, s in enumerate(self.swatches):
            if p.color_open:
                s.geom(17 + SWATCH_STEP * (i % per) - 2, 66 + SWATCH_STEP * (i // per), 32, 32)
                s.redraw()
            else:
                s.hide()
        if p.color_open and own:
            self.delete_link.set_text(p.app.t("export.color.delete"))
            self.delete_link.geom(17, 66 + 32 + SWATCH_STEP * (self.rows - 1) + 6, self.delete_link.natural_width(), 17)
        else:
            self.delete_link.hide()
        self.redraw()

    def draw(self):
        self.draw_base()
        p = self.page
        t = p.app.t
        w = self.lw
        self.text(17, 29, t("export.color"), 13.5, "semibold")
        label, hx = p.color_label()
        x = w - 15 - 20 - 12
        tw = text_width(label, 12.5)
        self.text(x, 29, label, 12.5, color="muted", anchor="e")
        if hx:
            self.rrect(x - tw - 8 - 16, 21, 16, 16, 4, hx, "swatch_stroke")
        else:
            self.icon("pipette", x - tw - 8 - 16, 21, 16, "muted")


SVG_MODES_H = 112      # «Толщина» + two radio buttons
SVG_LINE_H = 72        # «Толщина линии» row (only in «Заданная толщина»)


class FormatCard(Card):
    def __init__(self, master, page, code, desc_key):
        super().__init__(master, page, 62)
        self.code, self.desc_key = code, desc_key
        self.toggle = Toggle(self, page.formats[code], bg="card", show_label=False,
                             command=lambda v: page.toggle_format(code, v))
        self.chev = None
        if code == "DXF":
            self.chev = IconButton(self, "chev_down16", 16, bg="card", command=page.toggle_dxf, hover_token="card_hover")
            self.line = TextBox(self, page.app, "0,18", width=0, fit=NUM_FIT, bg="card", allow=_line_allowed,
                                on_apply=page.apply_dxf_line)
            self.bind("<ButtonRelease-1>", lambda e: page.toggle_dxf() if e.y < S(62) else None)
        if code == "SVG":
            self.chev = IconButton(self, "chev_down16", 16, bg="card", command=page.toggle_svg, hover_token="card_hover")
            self.modes = [Radio(self, "", bg="card", command=lambda m=m: page.set_svg_mode(m)) for m in ex.SVG_MODES]
            self.line = TextBox(self, page.app, "0,18", width=0, fit=NUM_FIT, bg="card", allow=_line_allowed,
                                on_apply=page.apply_svg_line)
            self.bind("<ButtonRelease-1>", lambda e: page.toggle_svg() if e.y < S(62) else None)
        if code == "PNG":
            self.chev = IconButton(self, "chev_down16", 16, bg="card", command=page.toggle_png, hover_token="card_hover")
            self.dpi = Segmented(self, ["300", "600", "1200 DPI"], 2, bg="card", equal=False, font_px=12,
                                 seg_pad=(10, 10), text_dy=-1, command=page.select_dpi)
            self.bind("<ButtonRelease-1>", lambda e: page.toggle_png() if e.y < S(62) else None)

    def layout(self, x, y, w):
        p = self.page
        self.body_h = 56 if (self.code == "PNG" and p.png_open) else 0
        if self.code == "DXF" and p.dxf_open:
            self.body_h = 72
        if self.code == "SVG" and p.svg_open:
            self.body_h = SVG_MODES_H + (SVG_LINE_H if p.svg_mode == "stroke" else 0)
        self.geom(x, y, w, self.height())
        self.toggle.set(p.formats[self.code])
        if self.code == "DXF":
            self.chev.icon_name = "chev_up" if p.dxf_open else "chev_down16"
            self.chev.geom(w - 15 - 20, 21, 20, 20)
            self.chev.redraw()
            self.toggle.geom(w - 15 - 20 - 12 - 40, 21, 40, 20)
            if p.dxf_open:
                self.line.set(ex.format_plain_number(p.dxf_line_mm, p.app.i18n.lang))
                self.line.geom(w - 17 - self.line.natural_width(), 82, self.line.natural_width(), 32)
            else:
                self.line.hide()
        elif self.code == "SVG":
            self.chev.icon_name = "chev_up" if p.svg_open else "chev_down16"
            self.chev.geom(w - 15 - 20, 21, 20, 20)
            self.chev.redraw()
            self.toggle.geom(w - 15 - 20 - 12 - 40, 21, 40, 20)
            t = p.app.t
            for i, (r, m) in enumerate(zip(self.modes, ex.SVG_MODES)):
                if p.svg_open:
                    r.label = t(f"export.svg.mode.{m}")
                    r.set(p.svg_mode == m)
                    r.geom(17, 62 + 36 + 32 * i, w - 34, 32)
                    r.redraw()
                else:
                    r.hide()
            if p.svg_open and p.svg_mode == "stroke":
                ry = 62 + SVG_MODES_H
                self.line.set(ex.format_plain_number(p.svg_line_mm, p.app.i18n.lang))
                self.line.geom(w - 17 - self.line.natural_width(), ry + 20, self.line.natural_width(), 32)
            else:
                self.line.hide()
        elif self.chev:
            self.chev.icon_name = "chev_up" if p.png_open else "chev_down16"
            self.chev.geom(w - 15 - 20, 21, 20, 20)
            self.chev.redraw()
            self.toggle.geom(w - 15 - 20 - 12 - 40, 21, 40, 20)
            if p.png_open:
                labels = [str(d) if d != p.png_dpi else p.app.t("export.dpi_value", n=d) for d in ex.DPI_CHOICES]
                self.dpi.labels = labels
                self.dpi.index = ex.DPI_CHOICES.index(p.png_dpi)
                dw = self.dpi.natural_width()
                self.dpi.geom(w - 17 - dw, 70, dw, 38)
                self.dpi.redraw()
            else:
                self.dpi.hide()
        else:
            self.toggle.geom(w - 15 - 40, 21, 40, 20)
        self.redraw()

    def draw(self):
        self.draw_base()
        p = self.page
        t = p.app.t
        on = p.formats[self.code]
        fg, bgc = TILE[self.code][1 if Theme.dark() else 0]
        self.put_cached(17, 15, ("tile", self.code, Theme.mode), lambda: gfx.rrect(32, 32, 4, bgc))
        self.text(33, 31, self.code, 11, "bold", color=fg, anchor="center") if False else \
            self.create_text(S(33), S(31), text=self.code, font=F(11, "bold"), fill=fg)
        self.text(61, 22.5, self.code, 13.5, "semibold", color="text" if on else "muted")
        avail = (self.lw - 15 - 20 - 12 - 40 if self.chev else self.lw - 15 - 40) - 12 - 61
        self.text(61, 40, elide(t(self.desc_key), avail, 12), 12, color="muted")
        if self.code == "PNG" and p.png_open:
            self.text(17, 70 + 19, t("export.png.resolution"), 13)
        if self.code == "SVG" and p.svg_open:
            self.text(17, 62 + 22, t("export.svg.mode"), 13)
            if p.svg_mode == "stroke":
                ry = 62 + SVG_MODES_H
                self.create_rectangle(S(17), S(ry), S(self.lw - 17), S(ry + 1), fill=Theme.c("divider"), width=0)
                self.text(17, ry + 20, t("export.svg.line"), 13)
                self.create_text(S(17), S(ry + 29), text=t("export.svg.line.desc"), font=F(12), fill=Theme.c("muted"),
                                 anchor="nw", width=S(270))
        if self.code == "DXF" and p.dxf_open:
            self.text(17, 82, t("export.dxf.line"), 13)
            self.create_text(S(17), S(91), text=t("export.dxf.line.desc"), font=F(12), fill=Theme.c("muted"),
                             anchor="nw", width=S(270))


class InfoBar(Box):
    def __init__(self, master, page):
        super().__init__(master, bg="bg")
        self.page = page
        self.link = Link(self, "", 12.5, "accent_text", bg="tips", weight="medium", command=page.app.open_formats_help)

    def layout(self, x, y, w):
        self.geom(x, y, w, 92)
        self.link.set_text(self.page.app.t("export.help.link"))
        self.link.geom(47, 65.1, self.link.natural_width(), 15)
        self.redraw()

    def draw(self):
        t = self.page.app.t
        self.rrect(0, 0, self.lw, self.lh, 4, "tips", "card_stroke")
        self.put_cached(15, 16, ("ii", Theme.c("accent"), Theme.c("tips")),
                        lambda: gfx.circle(18, Theme.c("accent"), bg=Theme.c("tips")))
        self.create_text(S(24), S(25), text="i", fill=Theme.c("on_accent"), font=F(12, "bold"))
        self.text(47, 23, t("export.help.title"), 13, "semibold")
        self.text(47, 37 + 9.06, t("export.help.text"), 12.5, color="muted")


class PreviewCard(Box):
    """Card padding 14: title 14/600, format tabs (only enabled formats), checker box with the file."""

    def __init__(self, master, page):
        super().__init__(master, bg="bg")
        self.page = page
        self.tabs = Segmented(self, [], 0, bg="card", equal=False, font_px=12, seg_pad=(10, 10), text_dy=-1,
                              command=page.select_tab_index)
        self.box = _PreviewBox(self, page)

    def layout(self, x, y, w, h):
        self.geom(x, y, w, h)
        p = self.page
        sel = p.selected_formats()
        if sel:
            self.tabs.labels = list(sel)
            self.tabs.index = sel.index(p.tab) if p.tab in sel else 0
            tw = self.tabs.natural_width()
            self.tabs.geom(w - 15 - tw, 15, tw, 38)
            self.tabs.redraw()
        else:
            self.tabs.hide()
        extra = 8 + 16.8 if p.nodpi_line() else 0.0     # 63: line under the preview box
        self.box.geom(15, 63, w - 30, h - 63 - 15 - extra)
        self.box.redraw()
        self.redraw()

    def draw(self):
        self.rrect(0, 0, self.lw, self.lh, 8, "card", "card_stroke")
        app = self.page.app
        job = app.job
        if app.batch is not None and job is not None:
            title = app.t("export.preview_file", file=job.stem)
        else:
            title = app.t("export.preview")
        room = self.lw - 30 - (self.tabs.lw + 12 if self.tabs.visible else 0)
        self.text(15, 34, elide(title, room, 14, "semibold"), 14, "semibold")
        if self.page.nodpi_line():
            self.text(15, self.lh - 15 - 8.4, elide(app.t("export.size.no_dpi"), self.lw - 30, 12), 12, color="muted")


class CountCard(Box):
    """16–18: «50 фото × 2 формата = 100 файлов» and «Имена файлов: <template chip>» (padding 14 16)."""

    def __init__(self, master, page):
        super().__init__(master, bg="bg")
        self.page = page

    def draw(self):
        p = self.page
        app = p.app
        self.rrect(0, 0, self.lw, self.lh, 8, "card", "card_stroke")
        b = app.batch
        if b is None:
            return
        n, k = len(b.items), len(p.selected_formats())
        self.text(17, 15 + 8, elide(B.summary_text(app.i18n, n, k, n * k), self.lw - 34, 13.5, "semibold"),
                  13.5, "semibold")
        tpl = p.settings.name_template(app.t("settings.name_template.value"))
        label = app.t("batch.names", template="\x00")
        a, _, rest = label.partition("\x00")
        y = 15 + 16 + 4 + 9.06
        x = 17.0
        self.text(x, y, a, 12.5, color="muted")
        x += text_width(a, 12.5)
        room = self.lw - 17 - x - 8
        chip = elide(tpl, room, 12.5, "mono")
        cw = text_width(chip, 12.5, "mono") + 8
        self.rrect(x, y - 8.5, cw, 17, 4, "chip")
        self.text(x + 4, y, chip, 12.5, "mono")
        if rest:
            self.text(x + cw, y, rest, 12.5, color="muted")


def preview_fit(w, h, outer_w, outer_h, side_w, pad=20.0, top=50.0, bottom=36.0):
    """Remarks 10 and 16: the framed file fills the preview and is centred horizontally.

    ``top`` keeps the size badge (11–33) and the caption above the frame clear, ``bottom`` the
    width dimension, ``side_w`` the rotated height dimension on the right — reserved on both sides
    so the left and right margins are equal.  Returns (ox, oy, k)."""
    aw = max(1.0, w - 2 * (pad + side_w))
    ah = max(1.0, h - top - bottom)
    k = min(aw / outer_w, ah / outer_h)
    ow, oh = outer_w * k, outer_h * k
    ox = (w - ow) / 2
    oy = top + (ah - oh) / 2
    return ox, oy, k


class _PreviewBox(Box):
    def __init__(self, master, page):
        super().__init__(master, bg="card")
        self.page = page
        self._checker = None

    def _height_text(self, geom):
        p = self.page
        app = p.app
        mm_h = ex.format_number(geom.file_h_mm, app.i18n.lang)
        if p.tab in ("SVG", "DXF"):
            return app.t("export.size.mm_value", n=mm_h)
        ph = ex.mm_to_px(geom.file_h_mm, p.png_eff_dpi())
        return app.t("export.dim_height", px=ph, mm=mm_h)   # one line, rotated 90°

    def _side_label_w(self, geom):
        """Room for the height dimension right of the frame: gap 8 + 6 + one rotated text line."""
        return 8 + 6 + F(11.5, "semibold").metrics("linespace") / Scale.factor

    def draw(self):
        p = self.page
        w, h = self.lw, self.lh
        W, H = S(w), S(h)
        key = (W, H, Theme.mode)
        if not self._checker or self._checker[0] != key:
            c1, c2 = CHECKER[Theme.mode]
            self._checker = (key, gfx.checker(W, H, max(1, S(10)), c1, c2))
        img = self._checker[1].copy()
        geom = p.geometry_safe()
        app = p.app
        texts = []
        if geom is not None:
            outer_w, outer_h = geom.box_mm if geom.box_mm else (geom.file_w_mm, geom.file_h_mm)
            # batch: the lower preview box makes the frame height-bound — keep the «Графа …» caption
            # clear of the size badge
            top = 58.0 if app.batch is not None else 50.0
            ox, oy, k = preview_fit(w, h, outer_w, outer_h, self._side_label_w(geom), top=top)
            ow, oh = outer_w * k, outer_h * k
            fx = ox + (outer_w - geom.file_w_mm) / 2 * k
            fy = oy + (outer_h - geom.file_h_mm) / 2 * k
            fw, fh = geom.file_w_mm * k, geom.file_h_mm * k
            rgb = p.current_rgb()
            tab = p.tab if p.tab in p.selected_formats() else None
            kd = Scale.factor
            stroke_w = p.dxf_line_mm if tab == "DXF" else (p.svg_line_mm if tab == "SVG" and p.svg_mode == "stroke" else None)
            if stroke_w is not None and p.outline_ready(geom) and p._outline_cache[2] is not None:
                ss = 2
                cl = p._outline_cache[2]
                lw_dev = max(1.0, stroke_w * k * kd * ss)
                layer = Image.new("L", (W * ss, H * ss), 0)
                dl = ImageDraw.Draw(layer)
                for pts, closed in cl.paths:
                    xy = [((fx + x * k) * kd * ss, (fy + y * k) * kd * ss) for x, y in pts]
                    if closed:
                        xy.append(xy[0])
                    dl.line(xy, fill=255, width=int(round(lw_dev)), joint="curve")
                    if not closed:
                        r = lw_dev / 2
                        for cx, cy in (xy[0], xy[-1]):
                            dl.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
                layer = layer.resize((W, H), Image.Resampling.BOX)
                img.paste(Image.new("RGBA", (W, H), tuple(rgb) + (255,)), (0, 0), layer)
            elif tab == "SVG" and p.outline_ready(geom):
                ss = 2
                polys = ex.outline_polygons(p._outline_cache[1], chord_mm=max(0.05, 0.5 / (k * kd)))
                acc = np.zeros((H * ss, W * ss), dtype=bool)
                for poly in polys:
                    tmp = Image.new("1", (W * ss, H * ss), 0)
                    ImageDraw.Draw(tmp).polygon([((fx + x * k) * kd * ss, (fy + y * k) * kd * ss) for x, y in poly], fill=1)
                    acc ^= np.asarray(tmp, dtype=bool)
                layer = Image.fromarray(acc.astype(np.uint8) * 255, "L").resize((W, H), Image.Resampling.BOX)
                img.paste(Image.new("RGBA", (W, H), tuple(rgb) + (255,)), (0, 0), layer)
            elif tab == "PNG" and p.png_ready(geom):
                src = p._png_cache[1]
                tw, th = max(1, int(round(fw * kd))), max(1, int(round(fh * kd)))
                img.alpha_composite(src.resize((tw, th), Image.Resampling.LANCZOS), (int(round(fx * kd)), int(round(fy * kd))))
            acc_c = gfx.rgba(Theme.c("accent"))
            d = ImageDraw.Draw(img)
            # dashed file / box outline in every mode, so «Поле рамки» is visible in «Как в исходнике» too
            if True:
                x0, y0, x1, y1 = ox * kd, oy * kd, (ox + ow) * kd, (oy + oh) * kd
                step, gap = 3 * kd, 2 * kd
                for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x0, y1, x1, y1), (x0, y0, x0, y1)):
                    L = max(abs(bx - ax), abs(by - ay))
                    tpos = 0.0
                    while tpos < L:
                        t2 = min(L, tpos + step)
                        d.line((ax + (bx - ax) * tpos / L, ay + (by - ay) * tpos / L,
                                ax + (bx - ax) * t2 / L, ay + (by - ay) * t2 / L), fill=acc_c, width=max(1, round(kd)))
                        tpos = t2 + gap
            if geom.box_mm:
                size = p.size_choice()
                cap = app.t("export.cell_caption") if size.is_cell_15x5 else p.wxh(*geom.box_mm)
            else:
                lg = app.i18n.lang
                cap = app.t("export.size.wxh", w=ex.format_number(geom.file_w_mm, lg), h=ex.format_number(geom.file_h_mm, lg))
            texts.append((ox, oy - 13, cap, 11, "normal", "muted", "w"))
            mm_w = ex.format_number(geom.file_w_mm, app.i18n.lang)
            if tab in ("SVG", "DXF"):
                wtxt = app.t("export.size.mm_value", n=mm_w)
            else:
                eff = p.png_eff_dpi()   # remark 36: actual px / DPI (capped in «Как в исходнике»)
                pw = ex.mm_to_px(geom.file_w_mm, eff)
                wtxt = app.t("export.dim_width", px=pw, mm=mm_w, dpi=ex.dpi_label(eff))
            ly = oy + oh + 8
            d.line((fx * kd, ly * kd, (fx + fw) * kd, ly * kd), fill=acc_c, width=max(1, round(kd)))
            texts.append((fx + fw / 2, ly + 3 + 7, wtxt, 11.5, "semibold", "accent", "n"))
            lx = ox + ow + 8
            d.line((lx * kd, fy * kd, lx * kd, (fy + fh) * kd), fill=acc_c, width=max(1, round(kd)))
            lh_txt = F(11.5, "semibold").metrics("linespace") / Scale.factor
            texts.append((lx + 6 + lh_txt / 2, fy + fh / 2, self._height_text(geom), 11.5, "semibold", "accent", "rot"))
            tag = p.tag_text(geom)
            if tag:
                tw = text_width(tag, 11.5, "semibold") + 20
                pill = gfx.rrect(tw, 22, 4, "#111317", fill_alpha=0.78)
                _paste_clip(img, pill, S(11), S(11))
                texts.append((21, 22, tag, 11.5, "semibold", "#FFFFFF", "w"))
        mask = gfx.rrect(w, h, 8, "#FFFFFF").getchannel("A")
        out = Image.new("RGBA", img.size, gfx.rgba(Theme.c("card")))
        out.paste(img, (0, 0), mask.resize(img.size) if mask.size != img.size else mask)
        out.alpha_composite(gfx.rrect(w, h, 8, None, Theme.c("card_stroke")))
        self.put(0, 0, out)
        for x, y, s, px, wt, col, anchor in texts:
            c = col if col.startswith("#") else Theme.c(col)
            if anchor == "rot":   # reads bottom to top (remark 16)
                self.create_text(S(x), S(y), text=s, font=F(px, wt), fill=c, anchor="center", angle=90)
            elif anchor == "n":
                self.create_text(S(x), S(y), text=s, font=F(px, wt), fill=c, anchor="center", justify="center")
            else:
                self.create_text(S(x), S(y), text=s, font=F(px, wt), fill=c, anchor=anchor, justify="left")


class ExportBar(Box):
    def __init__(self, master, page):
        super().__init__(master, bg="abar")
        self.page = page
        app = page.app
        # remark 31: secondary (filled) like «Назад» on screen 2, not ghost
        self.back = Button(self, "", kind="secondary", icon="arrow_left", bg="abar", command=app.back_to_process)
        self.save = Button(self, "", kind="primary", icon="save", icon_size=17, bg="abar", command=page.on_save_click)
        self.done = Button(self, "", kind="secondary", bg="abar", command=page.on_done)
        self.open = Button(self, "", kind="primary", icon="folder", bg="abar", command=page.open_saved_folder)
        self.cancel = Button(self, "", kind="secondary", bg="abar", command=page.cancel_batch_save)

    def layout(self, x, y, w):
        self.geom(x, y, w, 64)
        p = self.page
        t = p.app.t
        batch = p.app.batch is not None
        if batch and p._saving:
            # 17: «Сохранено N из M файлов» + progress bar, «Отмена»
            for wd in (self.back, self.save, self.done, self.open):
                wd.hide()
            self.cancel.set_text(t("common.cancel"))
            cw = self.cancel.natural_width()
            self.cancel.geom(w - 24 - cw, 16.5, cw, 32)
            self._prog_w = w - 24 - cw - 10 - 24 - 24
            self.redraw()
            return
        self.cancel.hide()
        if p.saved:
            self.back.hide()
            self.save.hide()
            self.done.set_text(t("common.done"))
            self.open.set_text(t("common.open_folder"))
            ow, dw = self.open.natural_width(), self.done.natural_width()
            self.open.geom(w - 24 - ow, 16.5, ow, 32)
            self.done.geom(w - 24 - ow - 10 - dw, 16.5, dw, 32)
        else:
            self.done.hide()
            self.open.hide()
            n = len(p.selected_formats())
            if batch:
                self.save.set_text(t("batch.save_to_folder"))
                self.save.icon_name, self.save.icon_px = "folder", 16
            else:
                self.save.set_text(p.app.tn("export.save_count", n))
                self.save.icon_name, self.save.icon_px = "save", 17
            self.save.set_disabled(n == 0 or p._saving)
            self.back.set_text(t("common.back"))
            sw, bw = self.save.natural_width(), self.back.natural_width()
            self.save.geom(w - 24 - sw, 16.5, sw, 32)
            self.back.geom(w - 24 - sw - 10 - bw, 16.5, bw, 32)
        self.redraw()

    def draw(self):
        self.create_rectangle(0, 0, S(self.lw), S(1), fill=Theme.c("abar_line"), width=0)
        p = self.page
        if p._saving and p.app.batch is not None and p._sess is not None:
            sess = p._sess
            room = getattr(self, "_prog_w", self.lw - 200)
            self.text(24, 19.5 + 8, elide(p.app.tn("batch.saving", sess.total, done=sess.done, total=sess.total),
                                         room, 13, "semibold"), 13, "semibold")
            self.rrect(24, 41.5, room, 4, 2, "progress_track")
            frac = sess.done / sess.total if sess.total else 0.0
            if frac > 0:
                self.rrect(24, 41.5, max(4.0, room * min(1.0, frac)), 4, 2, "accent")
            return
        if p.saved:
            n, folder = p.saved
            room = (self.done.lx - 24 - 10) if self.done.visible else self.lw - 48
            self.text(24, 32, elide(p.app.tn("export.saved_status", n, folder=folder.name), room, 13, "semibold"),
                      13, "semibold")


class ExportPage(Box):
    def __init__(self, master, app):
        super().__init__(master, bg="bg")
        self.app = app
        self.settings = app.settings
        self.result = None
        self.source: Optional[ex.ExportSource] = None
        self.formats = {"PNG": True, "SVG": False, "DXF": True}
        self.size_key = ex.SIZE_15X5
        self.custom_w, self.custom_h = 20.0, 8.0
        self.color_key = ex.DEFAULT_COLOR_KEY
        self.png_dpi = ex.DEFAULT_PNG_DPI
        self.margin_mm = ex.DEFAULT_MARGIN_MM
        self.dxf_line_mm = ex.DEFAULT_DXF_LINE_MM
        self.svg_mode = ex.DEFAULT_SVG_MODE
        self.svg_line_mm = ex.DEFAULT_SVG_LINE_MM
        self.svg_open = False
        self.tab = "PNG"
        self.color_open = False
        self.png_open = False
        self.dxf_open = False
        self.size_open = False
        self.saved = None
        self._saving = False
        self._png_cache = None
        self._outline_cache = None
        self._dxf_kb = {}
        self._after = None

        self.area = ScrollArea(self)
        inner = self.area.inner
        self.c_size = SizeCard(inner, self)
        self.c_color = ColorCard(inner, self)
        self.c_png = FormatCard(inner, self, "PNG", "export.png.desc")
        self.c_svg = FormatCard(inner, self, "SVG", "export.svg.desc")
        self.c_dxf = FormatCard(inner, self, "DXF", "export.dxf.desc")
        self.info = InfoBar(inner, self)
        self.preview = PreviewCard(self, self)
        # stage 4 (batch)
        self.strip = PhotoStrip(self, app, on_select=app.select_photo, on_add=None, on_remove=app.ask_remove_photo)
        self.count = CountCard(self, self)
        self.dim = DimLayer(app)
        self._sess: Optional[B.SaveSession] = None
        self._queue: List = []
        self._save_cfg = None
        self.bar = ExportBar(self, self)

    # ------------------------------------------------------------------ helpers
    def lang(self):
        return self.app.i18n.lang

    def wxh(self, w, h):
        return self.app.t("export.size.wxh", w=ex.format_plain_number(w, self.lang()),
                          h=ex.format_plain_number(h, self.lang()))

    def export_key(self):
        """Remark 39: everything that changes the saved files (a change after saving → «Начать заново?»)."""
        try:
            size = repr(self.size_choice())
        except Exception:
            size = repr((self.size_key, self.custom_w, self.custom_h))
        try:
            rgb = tuple(self.current_rgb())
        except Exception:
            rgb = self.color_key
        return (self.selected_formats(), size, self.margin_mm, rgb, self.png_dpi, self.dxf_line_mm,
                self.svg_mode, self.svg_line_mm)

    def selected_formats(self):
        return tuple(f for f in ex.ALL_FORMATS if self.formats.get(f))

    def custom_sizes(self):
        return list(self.settings.get("custom_sizes") or [])

    def custom_colors(self):
        return list(self.settings.get("custom_colors") or [])

    def size_choice(self):
        return ex.size_choice_for_key(self.size_key, self.custom_sizes(), (self.custom_w, self.custom_h))

    def png_eff_dpi(self) -> float:
        """PNG pixel density actually written (remark 36: «Как в исходнике» never upscales the photo)."""
        return ex.effective_png_dpi(self.source, self.size_choice(), self.png_dpi)

    def current_rgb(self):
        photo_ink = self.source.ink_rgb if self.source is not None else None
        return ex.resolve_color(self.color_key, self.custom_colors(), photo_ink)

    def nodpi_line(self) -> bool:
        """63: batch, «Как в исходнике», current photo without DPI."""
        return (self.app.batch is not None and self.size_key == ex.SIZE_ORIGINAL and self.source is not None
                and not self.source.has_dpi)

    def geometry_safe(self):
        if not self.source:
            return None
        try:
            sw, sh = self.source.size_px
            return ex.compute_geometry(sw, sh, self.source.dpi, self.size_choice(), self.margin_mm)
        except ValueError:
            return None

    def size_options(self):
        t = self.app.t
        opts = [(ex.SIZE_ORIGINAL, t("export.size.as_original")), (ex.SIZE_15X5, t("export.size.preset_15x5"))]
        for s in self.custom_sizes():
            try:
                wxh = self.wxh(float(s["w_mm"]), float(s["h_mm"]))
            except (KeyError, TypeError, ValueError):
                continue
            name = str(s.get("name") or "").strip()
            opts.append((ex.TEMPLATE_PREFIX + str(s.get("id")), wxh if not name or name == wxh else f"{name} · {wxh}"))
        opts.append((None, None))
        opts.append((ex.SIZE_CUSTOM, t("export.size.custom_item")))
        return opts

    def color_items(self):
        t = self.app.t
        items = []
        for key, hx in ex.BUILTIN_COLORS:
            if key == "as_photo":
                items.append((key, "photo", None, t("color.as_photo"), False))
            else:
                items.append((key, "color", hx, t(f"color.{key}"), False))
        for c in self.custom_colors():
            items.append((ex.CUSTOM_COLOR_PREFIX + str(c.get("id")), "color", c.get("hex", "#000000"),
                          str(c.get("name") or c.get("hex", "")), True))
        return items

    def color_label(self):
        for key, kind, hx, tip, _c in self.color_items():
            if key == self.color_key:
                return tip, hx
        return self.app.t("color.blue"), "#1B2A8A"

    # ------------------------------------------------------------------ enter / leave
    def on_show(self):
        job = self.app.job
        self.result = job.result
        self.source = job.source if job.source is not None else ex.source_from_result(job.result)
        self._png_cache = self._outline_cache = None
        self.saved = None
        s = self.settings
        last = s.get("last_export") or {}
        fmts = last.get("formats") or s.get("default_formats") or list(ex.DEFAULT_FORMATS)
        self.formats = {f: f in fmts for f in ex.ALL_FORMATS}
        self.custom_w = float(last.get("custom_w", self.custom_w))
        self.custom_h = float(last.get("custom_h", self.custom_h))
        size = last.get("size") or s.get("default_size", ex.SIZE_15X5)
        valid = {k for k, _ in self.size_options() if k}
        self.size_key = size if size in valid else ex.SIZE_15X5
        dpi = int(last.get("png_dpi") or s.get("png_resolution", ex.DEFAULT_PNG_DPI))
        self.png_dpi = dpi if dpi in ex.DPI_CHOICES else ex.DEFAULT_PNG_DPI
        ckey = last.get("color") or s.get("default_color", ex.DEFAULT_COLOR_KEY)
        valid_c = {k for k, *_ in self.color_items()}
        self.color_key = ckey if ckey in valid_c else ex.DEFAULT_COLOR_KEY
        try:
            self.margin_mm = float(s.get("crop_margin_mm", ex.DEFAULT_MARGIN_MM))
        except (TypeError, ValueError):
            self.margin_mm = ex.DEFAULT_MARGIN_MM
        self.dxf_line_mm = ex.resolve_dxf_line(last, s.get("dxf_line_mm"))   # remark 50
        # remark 29: Settings › «Форматы по умолчанию» holds the default (svg_mode); the choice made on
        # this card is remembered in last_export until the default is changed in Settings again
        self.svg_mode = ex.resolve_svg_mode(last, s.get("svg_mode"))
        self.svg_line_mm = ex.resolve_svg_line(last, s.get("svg_line_mm"))
        self._dxf_kb = {}
        sel = self.selected_formats()
        self.tab = sel[0] if sel else "PNG"
        self.c_color.rebuild()
        self.c_size.w_box.set(ex.format_plain_number(self.custom_w, self.lang()))
        self.c_size.h_box.set(ex.format_plain_number(self.custom_h, self.lang()))
        self.area.bind_wheel()
        self.changed()
        if self.app.batch is not None:
            self.after_idle(self.strip.ensure_visible)

    def on_settings_changed(self):
        """Settings changed while screen 3 was open: re-read the defaults the user just changed."""
        if self._saving:
            return
        if self.app.job and (self.app.job.result is not None or self.app.job.source is not None):
            self.on_show()

    def on_switch(self):
        """Another batch photo is shown (strip, ←/→, removal): same settings, new source."""
        job = self.app.job
        if job is None:
            return
        self.result = job.result
        self.source = job.source
        self._png_cache = self._outline_cache = None
        self._dxf_kb = {}
        self.strip.ensure_visible()
        self.layout_all()
        self.schedule_preview()

    def on_batch_changed(self):
        job = self.app.job
        if job is not None and job.source is not self.source:
            self.on_switch()
            return
        self.layout_all()

    def hide(self):
        super().hide()
        self.area.hide()

    def remember(self):
        self.settings.set("last_export", {"formats": list(self.selected_formats()), "size": self.size_key,
                                          "png_dpi": self.png_dpi, "custom_w": self.custom_w,
                                          "custom_h": self.custom_h, "color": self.color_key,
                                          "svg_mode": self.svg_mode, "svg_line_mm": self.svg_line_mm})

    # ------------------------------------------------------------------ actions
    def changed(self):
        if self.saved:
            self.saved = None
        self.strip.show_dots = self.size_key == ex.SIZE_ORIGINAL
        self.sync_combo()
        self.layout_all()
        self.schedule_preview()

    def sync_combo(self):
        opts = self.size_options()
        labels = [lab for _, lab in opts]
        idx = next((i for i, (k, _) in enumerate(opts) if k == self.size_key), 1)
        self.c_size.combo.set_items(labels, idx)
        self.c_size.combo.value_text = (lambda: self.app.t("export.size.custom_value")) \
            if self.size_key == ex.SIZE_CUSTOM else None

    def select_size_index(self, i):
        key = self.size_options()[i][0]
        if key:
            self.size_key = key
            self.changed()

    def set_custom(self, which, text):
        v = ex.parse_number(text)
        if v is None or not ex.valid_box_size(v if which == "w" else self.custom_w, v if which == "h" else self.custom_h,
                                              self.margin_mm):
            return False
        if which == "w":
            self.custom_w = v
        else:
            self.custom_h = v
        box = self.c_size.w_box if which == "w" else self.c_size.h_box
        box.set(ex.format_plain_number(v, self.lang()))
        self.changed()
        return True

    def save_template(self):
        from ui.dialogs.content import ContentDialog
        t = self.app.t
        default = self.wxh(self.custom_w, self.custom_h)

        def ok(name):
            name = (name or "").strip() or default
            sizes = self.custom_sizes()
            sid = ex.new_item_id(sizes)
            sizes.append({"id": sid, "name": name, "w_mm": self.custom_w, "h_mm": self.custom_h})
            self.settings.set("custom_sizes", sizes)
            self.size_key = ex.TEMPLATE_PREFIX + sid
            self.app.root.after(1, self.changed)
            return True
        ContentDialog(self.app, t("template.save.title"), "",
                      [(t("common.save"), "primary", ok), (t("common.cancel"), "secondary", None)],
                      width=420, field={"label": t("common.name"), "value": default})

    def selected_template(self) -> Optional[dict]:
        """The user-saved template currently selected in «Размер подписи», else None."""
        if not str(self.size_key).startswith(ex.TEMPLATE_PREFIX):
            return None
        tid = self.size_key[len(ex.TEMPLATE_PREFIX):]
        return next((sz for sz in self.custom_sizes() if str(sz.get("id")) == tid), None)

    def delete_template(self):
        """Remark 34: «Удалить шаблон» — the same confirmation as Settings › «Размеры подписи» (51 / 56),
        shared since stage 5 (ui/dialogs/sizes.confirm_delete_size, red «Удалить»).  Afterwards
        «15 × 5 мм» is selected."""
        from ui.dialogs.sizes import confirm_delete_size
        tpl = self.selected_template()
        if tpl is None:
            return

        def done():
            self.size_key = ex.SIZE_15X5
            self.changed()
        confirm_delete_size(self.app, tpl, done)

    def toggle_color(self):
        self.color_open = not self.color_open
        self.layout_all()

    def toggle_png(self):
        self.png_open = not self.png_open
        self.layout_all()

    def toggle_size(self):
        self.size_open = not self.size_open
        self.layout_all()

    def toggle_svg(self):
        self.svg_open = not self.svg_open
        self.layout_all()

    def set_svg_mode(self, mode):
        mode = ex.clamp_svg_mode(mode)
        if mode == self.svg_mode:
            return
        self.svg_mode = mode
        last = dict(self.settings.get("last_export") or {})
        last["svg_mode"] = mode
        self.settings.set("last_export", last)
        if self.saved:
            self.saved = None
        self.layout_all()
        self.preview.box.redraw()   # both traces are cached per geometry: no re-trace

    def apply_svg_line(self, text):
        v = ex.parse_number(text)
        if v is None or not (ex.DXF_LINE_RANGE[0] <= v <= ex.DXF_LINE_RANGE[1]):
            return False
        self.svg_line_mm = round(v, 2)
        # remark 32: Settings › «Толщина SVG» holds the default; a quick change here is remembered in
        # last_export (like the mode) until the default is changed in Settings again
        last = dict(self.settings.get("last_export") or {})
        last["svg_line_mm"] = self.svg_line_mm
        self.settings.set("last_export", last)
        if self.saved:
            self.saved = None
        self.layout_all()
        self.preview.box.redraw()
        return True

    def toggle_dxf(self):
        self.dxf_open = not self.dxf_open
        self.layout_all()

    def apply_dxf_line(self, text):
        v = ex.parse_number(text)
        if v is None or not (ex.DXF_LINE_RANGE[0] <= v <= ex.DXF_LINE_RANGE[1]):
            return False
        self.dxf_line_mm = round(v, 2)
        # remark 50: Settings › «Толщина DXF» holds the default; a quick change here is remembered in
        # last_export until the default is changed in Settings again (as «Толщина SVG»)
        last = dict(self.settings.get("last_export") or {})
        last["dxf_line_mm"] = self.dxf_line_mm
        self.settings.set("last_export", last)
        if self.saved:
            self.saved = None
        self.layout_all()
        self.preview.box.redraw()   # thickness only: no re-trace needed
        return True

    def select_color(self, key):
        self.color_key = key
        for s in self.c_color.swatches:
            s.redraw()
        self.changed()

    def ask_delete_color(self, key):
        """Remark 58: «Удалить цвет» and the right click ask first — the same dialog as in Settings."""
        from ui.dialogs.colors import confirm_delete_color
        return confirm_delete_color(self.app, key, lambda: self._color_deleted(key))

    def _color_deleted(self, key):
        if self.color_key == key:
            self.color_key = ex.DEFAULT_COLOR_KEY
        self.c_color.rebuild()
        self.changed()

    def delete_color(self, key):
        self.settings.delete_custom_color(key)          # stage 5: the same action as in Settings
        if self.color_key == key:
            self.color_key = ex.DEFAULT_COLOR_KEY
        self.c_color.rebuild()
        self.changed()

    def add_color(self):
        from ui.dialogs.color_dialog import CustomColorDialog

        def done(name, hx):
            colors = self.custom_colors()
            cid = ex.new_item_id(colors)
            colors.append({"id": cid, "name": name, "hex": hx})
            self.settings.set("custom_colors", colors)
            self.color_key = ex.CUSTOM_COLOR_PREFIX + cid
            self.c_color.rebuild()
            self.changed()
        CustomColorDialog(self.app, self.source.mask if self.source else None, self.current_rgb(), done)

    def toggle_format(self, code, on):
        self.formats[code] = on
        sel = self.selected_formats()
        if self.tab not in sel and sel:
            self.tab = sel[0]
        elif on and len(sel) == 1:
            self.tab = code
        self.changed()

    def select_tab_index(self, i):
        sel = self.selected_formats()
        if 0 <= i < len(sel):
            self.tab = sel[i]
            self.schedule_preview()

    def select_dpi(self, i):
        self.png_dpi = ex.DPI_CHOICES[i]
        self.changed()

    def apply_margin(self, text):
        v = ex.parse_number(text)
        if v is None or not (0 <= v <= 20) or not ex.margin_fits(self.size_choice(), round(v, 1)):
            return False
        self.margin_mm = round(v, 1)
        self.settings.set("crop_margin_mm", self.margin_mm)
        self.changed()
        return True

    def on_done(self):
        self.remember()
        self.app.done_after_save()

    def open_saved_folder(self):
        if self.saved:
            self.app.open_folder(self.saved[1])

    # ------------------------------------------------------------------ save
    def on_save_click(self):
        fmts = self.selected_formats()
        if self.app.batch is not None:
            if fmts and not self._saving:
                self.batch_save_click(fmts)
            return
        if not fmts or not self.source or self._saving:
            return
        t = self.app.t
        folder = self.settings.save_folder(t("export.default_folder"))
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            log.warning("cannot create save folder %s", folder)
        template = self.settings.name_template(t("settings.name_template.value"))
        from datetime import datetime
        stem = self.source.name or datetime.now().strftime("%Y-%m-%d_%H%M%S")
        base = ex.sanitize_filename(ex.expand_template(template, stem))
        kwargs = dict(parent=self.app.root, initialdir=str(folder), initialfile=f"{base}.{fmts[0].lower()}",
                      defaultextension=f".{fmts[0].lower()}", filetypes=[(f, f"*.{f.lower()}") for f in fmts])
        if sys.platform == "win32":
            kwargs["confirmoverwrite"] = False  # «Если файл уже есть» decides, not the dialog
        path = filedialog.asksaveasfilename(**kwargs)
        if not path:
            return  # cancelled: stay on screen 3 without «Сохранено…»
        path = Path(path)
        self.save_to(path.parent, ex.sanitize_filename(ex.strip_known_ext(path.name)), fmts)

    def save_to(self, folder: Path, base: str, fmts):
        mode = self.settings.get("if_exists", "ask")
        base2, conflicts = ex.resolve_base(folder, base, fmts, mode)
        if conflicts:
            self.ask_file_exists(folder, base, conflicts[0].name, fmts)
            return
        self.start_write(folder, base2, fmts)

    def ask_file_exists(self, folder, base, filename, fmts):
        from ui.dialogs.content import ContentDialog
        t = self.app.t
        body = t("file_exists.body", folder="\x00F", file="\x00N").replace("\x00F", folder.name)
        a, _, b = body.partition("\x00N")
        runs = [(a, "normal"), (filename, "semibold")] + ([(b, "normal")] if b else [])
        ContentDialog(self.app, t("file_exists.title"), runs, [
            (t("file_exists.keep_both"), "primary",
             lambda: self.start_write(folder, ex.resolve_base(folder, base, fmts, "add_number")[0], fmts)),
            (t("common.replace"), "secondary", lambda: self.start_write(folder, base, fmts)),
            (t("common.cancel"), "secondary", None)], width=560)

    def start_write(self, folder, base, fmts):
        job = ex.ExportJob(self.source, self.size_choice(), self.margin_mm, self.current_rgb(), self.png_dpi, fmts,
                           self.dxf_line_mm, self.svg_mode, self.svg_line_mm)
        geom = self.geometry_safe()
        ready = self.outline_ready(geom)
        cached = self._outline_cache[1] if ready else None
        cached_cl = self._outline_cache[2] if ready else None
        self._saving = True
        self.bar.layout(0, self.lh - 64, self.lw)

        def work():
            return ex.write_outputs(folder, base, ex.build_outputs(job, cached, cached_cl))

        def ok(res):
            self._saving = False
            self.saved = (len(res), Path(folder))
            if self.app.job:
                self.app.job.saved = True
            self.app.mark_saved()
            self.remember()
            self.bar.layout(0, self.lh - 64, self.lw)

        def fail(exc):
            self._saving = False
            self.app.mark_save_failed()
            log.error("save failed: %s", exc)
            self.bar.layout(0, self.lh - 64, self.lw)
            self.app.show_error_dialog(self.app.t("errors.save.title"), self.app.t("errors.save.body"),
                                       retry=lambda: self.start_write(folder, base, fmts))
        self.app.worker.submit("save", work, ok, fail)

    # ------------------------------------------------------------------ batch save (16–18, 44)
    def batch_save_click(self, fmts):
        t = self.app.t
        folder = self.settings.save_folder(t("export.default_folder"))
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            log.warning("cannot create save folder %s", folder)
        d = filedialog.askdirectory(parent=self.app.root, initialdir=str(folder), mustexist=False,
                                    title=t("batch.save_to_folder"))
        if d:
            self.start_batch_save(Path(d), fmts)

    def start_batch_save(self, folder: Path, fmts):
        b = self.app.batch
        if b is None or not b.items:
            return
        t = self.app.t
        template = self.settings.name_template(t("settings.name_template.value"))
        mode = self.settings.get("if_exists", "ask")
        self._sess = B.SaveSession(folder, fmts, mode, template, len(b.items))
        self._queue = list(b.items)
        self._save_cfg = (self.size_choice(), self.margin_mm, tuple(self.current_rgb()), self.png_dpi,
                          self.dxf_line_mm, self.svg_mode, self.svg_line_mm)
        self.saved = None
        self._saving = True
        self.app.saving = True
        Tooltip.cancel(None)
        self.bar.layout(0, self.lh - 64, self.lw)
        self.app.root.update_idletasks()
        self.dim.show(0, 64, self.lw, self.lh - 64)
        self.remember()
        self._save_next()

    def _save_next(self):
        sess = self._sess
        if sess is None or sess.cancelled:
            return
        if not self._queue:
            self._finish_batch_save()
            return
        plan = sess.plan(self._queue[0])
        if sess.needs_question(plan):
            self._ask_batch_exists(plan)
            return
        self._render_job(plan, sess.resolve(plan))

    def _ask_batch_exists(self, plan):
        """44: «Файл уже существует» with «Применить ко всем»."""
        from ui.dialogs.content import ContentDialog
        t = self.app.t
        sess = self._sess
        filename = plan.conflicts[0].name
        body = t("file_exists.body", folder="\x00F", file="\x00N").replace("\x00F", sess.folder.name)
        a, _, rest = body.partition("\x00N")
        runs = [(a, "normal"), (filename, "semibold")] + ([(rest, "normal")] if rest else [])

        def answer(choice):
            return lambda apply_all: self._render_job(plan, sess.resolve(plan, choice, apply_all))
        ContentDialog(self.app, t("file_exists.title"), runs, [
            (t("file_exists.keep_both"), "primary", answer("keep_both")),
            (t("common.replace"), "secondary", answer("replace")),
            (t("common.cancel"), "secondary", answer("skip"))], width=560, check=t("batch.apply_all"), esc_index=2)

    def _render_job(self, plan, pairs):
        sess = self._sess
        if sess is None or sess.cancelled:
            return
        if self._queue and self._queue[0] is plan.job:
            self._queue.pop(0)
        job = plan.job
        if not pairs or job.source is None:
            if job.source is None:        # nothing to export (should not happen: export needs all ready)
                sess.done += len(pairs)
            self.bar.redraw()
            self.after(1, self._save_next)
            return
        size, margin, rgb, dpi, dxf_line, svg_mode, svg_line = self._save_cfg
        ejob = ex.ExportJob(job.source, size, margin, rgb, dpi, tuple(f for f, _ in pairs), dxf_line, svg_mode, svg_line)

        def work():
            return ex.build_outputs(ejob)

        def ok(outputs):
            self._write_pairs(job, pairs, outputs)

        def fail(exc):
            log.error("batch render failed for %s: %s", job.name, exc)
            self._save_error(lambda: self._render_job(plan, pairs))
        self.app.worker.submit("batch_save", work, ok, fail)

    def _write_pairs(self, job, pairs, outputs):
        sess = self._sess
        if sess is None or sess.cancelled:
            return
        for k, (fmt, base) in enumerate(pairs):
            try:
                sess.write(fmt, base, outputs[fmt])
            except OSError as exc:
                log.error("cannot write %s: %s", base, exc)
                rest = pairs[k:]
                self.bar.redraw()
                self._save_error(lambda: self._write_pairs(job, rest, outputs))   # retry from the failed file
                return
        self.bar.redraw()
        self.after(1, self._save_next)

    def _save_error(self, retry):
        t = self.app.t
        self.app.show_error_dialog(t("errors.save.title"), t("errors.save.body"), retry=retry,
                                   on_cancel=self.cancel_batch_save)

    def cancel_batch_save(self):
        """«Отмена» (17) or «Отмена» in 31: stop; «Готово» state with the files really written."""
        sess = self._sess
        if sess is None or not self._saving:
            return
        sess.cancelled = True
        self._finish_batch_save()

    def _finish_batch_save(self):
        sess = self._sess
        self._saving = False
        self.app.saving = False
        self.dim.hide()
        self._queue = []
        b = self.app.batch
        if sess is not None and sess.saved:
            self.saved = (sess.saved, sess.folder)
            if b is not None and not sess.cancelled:
                b.saved = True
        else:
            self.saved = None
        if sess is not None and sess.saved and not sess.cancelled and not getattr(sess, "failed", 0):
            self.app.mark_saved()
        else:
            self.app.mark_save_failed()
        self.layout_all()

    # ------------------------------------------------------------------ preview (async)
    def _geom_key(self, geom):
        if geom is None:
            return None
        return (id(self.source), round(geom.content_w_mm, 6), round(geom.content_h_mm, 6),
                round(geom.file_w_mm, 6), round(geom.file_h_mm, 6))

    def _png_key(self, geom):
        return (self._geom_key(geom), tuple(self.current_rgb()), self.png_eff_dpi())

    def png_ready(self, geom):
        return bool(self._png_cache and self._png_cache[0] == self._png_key(geom))

    def outline_ready(self, geom):
        return bool(self._outline_cache and self._outline_cache[0] == self._geom_key(geom))

    def tag_text(self, geom):
        if self.tab == "PNG" and self.png_ready(geom):
            eff = self.png_eff_dpi()
            pw, ph = ex.mm_to_px(geom.file_w_mm, eff), ex.mm_to_px(geom.file_h_mm, eff)
            return self.app.t("export.file_tag", w=pw, h=ph, size=self._png_cache[2])
        if self.tab in ("SVG", "DXF") and self.outline_ready(geom):
            return self.app.t("export.vector_tag", size=self.wxh(geom.file_w_mm, geom.file_h_mm),
                              kb=self.vector_kb(self.tab))
        return None

    def schedule_preview(self):
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(40, self.update_preview)

    def update_preview(self):
        self._after = None
        geom = self.geometry_safe()
        if geom is None:
            self.preview.box.redraw()
            return
        src, rgb, dpi = self.source, tuple(self.current_rgb()), self.png_eff_dpi()
        pkey = self._png_key(geom)
        if not self.png_ready(geom):
            def render():
                img = ex.render_png(src, geom, rgb, dpi)
                return pkey, img, ex.estimate_kb(len(ex.png_bytes(img, dpi)))
            self.app.worker.submit("preview_png", render, self._png_done, lambda e: log.error("png preview: %s", e))
        if (self.formats.get("SVG") or self.formats.get("DXF")) and not self.outline_ready(geom):
            gkey = self._geom_key(geom)

            def trace():
                # SVG: filled outline; DXF: centreline — both cached per geometry
                return gkey, ex.trace_outline(src, geom), ex.trace_centerline(src, geom)
            self.app.worker.submit("preview_trace", trace, self._trace_done, lambda e: log.error("trace: %s", e))
        self.preview.layout(self.preview.lx, self.preview.ly, self.preview.lw, self.preview.lh)

    def _png_done(self, res):
        self._png_cache = res
        self.preview.box.redraw()

    def _trace_done(self, res):
        self._outline_cache = res
        self._dxf_kb = {}
        self.preview.box.redraw()

    def vector_kb(self, fmt):
        """Badge size: SVG/DXF bytes for the cached trace (DXF also depends on colour and thickness)."""
        _, outline, cl = self._outline_cache
        key = (fmt, tuple(self.current_rgb()), self.dxf_line_mm, self.svg_mode, self.svg_line_mm, id(outline))
        if key not in self._dxf_kb:
            if fmt == "SVG":
                kb = ex.vector_sizes_kb(outline, cl, key[1], svg_mode=self.svg_mode, svg_line_mm=self.svg_line_mm)["SVG"]
            else:
                kb = ex.vector_sizes_kb(None, cl, key[1], self.dxf_line_mm)["DXF"]
            self._dxf_kb[key] = kb
        return self._dxf_kb[key]

    # ------------------------------------------------------------------ layout
    def layout(self, w, h):
        self.geom(0, 64, w, h)
        self.layout_all()

    def layout_all(self):
        if self.lw <= 0:
            return
        w, h = self.lw, self.lh
        col_h = h - 64 - 16
        y = 0.0
        for c in (self.c_size, self.c_color, self.c_png, self.c_svg, self.c_dxf):
            c.layout(0, y, LEFT_W)
            y += c.height() + 8
        info_y = max(y, col_h - 92)
        self.info.layout(0, info_y, LEFT_W)
        self.area.geom(24, 0, LEFT_W + 12, col_h, info_y + 92)
        rx = 24 + LEFT_W + 16
        rw = w - rx - 24
        if self.app.batch is not None:
            ph = col_h - STRIP_H - 8 - 92 - 8
            self.preview.layout(rx, 0, rw, ph)
            self.strip.layout(rx, ph + 8, rw)
            self.count.geom(rx, col_h - 92, rw, 92)
            self.count.redraw()
        else:
            self.strip.hide()
            self.count.hide()
            self.preview.layout(rx, 0, rw, col_h)
        self.bar.layout(0, h - 64, w)
        if self.dim.active:
            self.dim.relayout(0, 64, w, h - 64)

    def refresh(self):
        super().refresh()
        self.area.refresh_bg()
