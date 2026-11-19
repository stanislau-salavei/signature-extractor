"""Screen 3 option cards: size, colour, formats, info line, batch count (remark 112)."""
from __future__ import annotations

import logging
import re
from typing import List

from core import batch as B
from core import export as ex
from ui import gfx
from ui.theme import F, S, Scale, Theme, blend, elide, text_width
from ui.widgets.base import Box, Control
from ui.widgets.controls import ComboBox, IconButton, Link, Radio, Segmented, TextBox, Toggle
from ui.widgets.overlay import MenuItem, MenuPopup, widget_rect

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


def _num_allowed(text: str) -> bool:
    return re.fullmatch(r"\d{0,3}([.,]\d?)?", text) is not None


def _line_allowed(text: str) -> bool:
    """DXF line thickness: up to 5 mm with two decimals (0,18)."""
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
        x, y, w, h = widget_rect(self.page.app.root, self)
        MenuPopup(self.page.app, [MenuItem(self.page.app.t("common.delete"),
                                           lambda: self.page.ask_delete_color(self.key), "trash")],
                  x + e.x / Scale.factor + 2, y + e.y / Scale.factor + 8)

    def draw(self):
        sel = self.key == self.page.color_key
        bgc = Theme.c("card")
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
            for i, (r, m) in enumerate(zip(self.modes, ex.SVG_MODES, strict=True)):
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
