"""Screen 3 (11–13, 33–35, 48, 54, 58–61; batch 16–18, 44, 63): size, colour, PNG / SVG / DXF, preview,
single save; in a batch also the photo strip, the file count card and «Сохранить в папку…»."""
from __future__ import annotations

import logging
from typing import List, Optional

from core import batch as B
from core import export as ex
from core.export_preview import ExportPreviewModel, geom_key
from ui.theme import ACTION_BAR_H, HEADER_H
from ui.widgets.base import Box
from ui.widgets.scroll import ScrollArea
from ui.widgets.batch import STRIP_H, DimLayer, PhotoStrip

from ui.pages.export.cards import (  # noqa: F401 — names used by tests and other screens
    COLOR_DELETE_ROW_H, CUSTOM_GAP, LEFT_W, MARGIN_ROW_H, NUM_FIT, SIZE_COMBO_W, SVG_LINE_H, SVG_MODES_H, SWATCH_STEP,
    TEMPLATE_ROW_H, TILE, Card, ColorCard, CountCard, FormatCard, InfoBar, SizeCard, Swatch)
from ui.pages.export.preview_box import CHECKER, PreviewCard, _PreviewBox, preview_fit  # noqa: F401
from ui.pages.export.save_flow import ExportBar, SaveFlowMixin  # noqa: F401

log = logging.getLogger(__name__)


class ExportPage(SaveFlowMixin, Box):
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
        self.model = ExportPreviewModel()      # remark 117: preview PNG, traces and file sizes
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
            log.warning("ExportPage.export_key: Exception caught", exc_info=True)   # remark 81, 115
            size = repr((self.size_key, self.custom_w, self.custom_h))
        try:
            rgb = tuple(self.current_rgb())
        except Exception:
            log.warning("ExportPage.export_key: Exception caught", exc_info=True)   # remark 81, 115
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
            log.debug("ExportPage.geometry_safe: ValueError caught", exc_info=True)   # remark 81
            return None

    def size_options(self):
        t = self.app.t
        opts = [(ex.SIZE_ORIGINAL, t("export.size.as_original")), (ex.SIZE_15X5, t("export.size.preset_15x5"))]
        for s in self.custom_sizes():
            try:
                wxh = self.wxh(float(s["w_mm"]), float(s["h_mm"]))
            except (KeyError, TypeError, ValueError):
                log.debug("ExportPage.size_options: (KeyError, TypeError, ValueError) caught", exc_info=True)   # remark 81
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
        self.model.reset()
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
            log.debug("ExportPage.on_show: (TypeError, ValueError) caught", exc_info=True)   # remark 81
            self.margin_mm = ex.DEFAULT_MARGIN_MM
        self.dxf_line_mm = ex.resolve_dxf_line(last, s.get("dxf_line_mm"))   # remark 50
        # remark 29: Settings › «Форматы по умолчанию» holds the default (svg_mode); the choice made on
        # this card is remembered in last_export until the default is changed in Settings again
        self.svg_mode = ex.resolve_svg_mode(last, s.get("svg_mode"))
        self.svg_line_mm = ex.resolve_svg_line(last, s.get("svg_line_mm"))
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
        self.model.reset()
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
        self.preview.box.redraw()   # traces are cached per geometry; remark 103a: trace the other one if missing
        if not self.outline_ready(self.geometry_safe()):
            self.schedule_preview()

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
        CustomColorDialog(self.app, self.source.mask if self.source else None, done)

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

    # ------------------------------------------------------------------ preview (async)
    def _geom_key(self, geom):
        return geom_key(self.source, geom)

    def _png_key(self, geom):
        return self.model.png_key(self.source, geom, tuple(self.current_rgb()), self.png_eff_dpi())

    def png_ready(self, geom):
        return self.model.png_ready(self._png_key(geom))

    def outline_ready(self, geom):
        """The traces the chosen formats need are ready for this geometry (remark 103a)."""
        return self.model.trace_ready(self._geom_key(geom), self.selected_formats(), self.svg_mode)

    def tag_text(self, geom):
        if self.tab == "PNG" and self.png_ready(geom):
            eff = self.png_eff_dpi()
            pw, ph = ex.mm_to_px(geom.file_w_mm, eff), ex.mm_to_px(geom.file_h_mm, eff)
            return self.app.t("export.file_tag", w=pw, h=ph, size=self.model.png_kb)
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
        m = self.model
        if not self.png_ready(geom):
            self.app.worker.submit("preview_png", m.png_job(src, geom, rgb, dpi), self._png_done,
                                   lambda e: log.error("png preview: %s", e))
        fmts = self.selected_formats()
        if ("SVG" in fmts or "DXF" in fmts) and not self.outline_ready(geom):
            # remark 103a: only the traces the formats need; C8: their badge sizes in the same job
            kb = [(f, rgb, self.dxf_line_mm, self.svg_mode, self.svg_line_mm) for f in ("SVG", "DXF") if f in fmts]
            self.app.worker.submit("preview_trace", m.trace_job(src, geom, fmts, self.svg_mode, kb), self._trace_done,
                                   lambda e: log.error("trace: %s", e))
        self.preview.layout(self.preview.lx, self.preview.ly, self.preview.lw, self.preview.lh)

    def _png_done(self, res):
        self.model.set_png(res)
        self.preview.box.redraw()

    def _trace_done(self, res):
        self.model.set_trace(res)
        self.preview.box.redraw()

    def vector_kb(self, fmt):
        """Badge size: SVG/DXF bytes for the cached trace (DXF also depends on colour and thickness)."""
        return self.model.vector_kb(fmt, tuple(self.current_rgb()), self.dxf_line_mm, self.svg_mode, self.svg_line_mm)

    # ------------------------------------------------------------------ layout
    def layout(self, w, h):
        self.geom(0, HEADER_H, w, h)
        self.layout_all()

    def layout_all(self):
        if self.lw <= 0:
            return
        w, h = self.lw, self.lh
        col_h = h - ACTION_BAR_H - 16
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
        self.bar.layout(0, h - ACTION_BAR_H, w)
        if self.dim.active:
            self.dim.relayout(0, HEADER_H, w, h - ACTION_BAR_H)

    def refresh(self):
        super().refresh()
        self.area.refresh_bg()
