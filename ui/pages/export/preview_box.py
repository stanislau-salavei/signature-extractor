"""Screen 3 preview: the checkerboard box with the file, its size lines and badge (remark 112)."""
from __future__ import annotations

import logging

import numpy as np
from PIL import Image, ImageDraw

from core import export as ex
from ui import gfx
from ui.theme import F, S, Scale, Theme, elide, text_width
from ui.widgets.base import Box
from ui.widgets.controls import Segmented
from ui.widgets.overlay import _paste_clip

log = logging.getLogger(__name__)


CHECKER = {"light": ("#FFFFFF", "#E6E8EC"), "dark": ("#2A2A2A", "#1C1C1C")}


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
            # remark 100 (audit B2): the drawing of the chosen format in separate methods
            if not self._draw_vector(img, geom, tab, fx, fy, k, rgb) and tab == "PNG" and p.png_ready(geom):
                self._draw_png(img, fx, fy, fw, fh)
            acc_c = gfx.rgba(Theme.c("accent"))
            d = ImageDraw.Draw(img)
            # dashed file / box outline in every mode, so «Поле рамки» is visible in «Как в исходнике» too
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
            self._draw_badge(img, geom, texts)
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

    def _draw_vector(self, img, geom, tab, fx, fy, k, rgb) -> bool:
        """DXF / SVG «линия»: the centreline at the line width; SVG «заливка»: the filled outline.
        False when the tab shows no vector (PNG, or the trace is not ready)."""
        p = self.page
        W, H = img.size
        kd = Scale.factor
        stroke_w = p.dxf_line_mm if tab == "DXF" else (p.svg_line_mm if tab == "SVG" and p.svg_mode == "stroke" else None)
        if stroke_w is not None and p.outline_ready(geom) and p.model.centerline is not None:
            ss = 2
            cl = p.model.centerline
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
            return True
        if tab == "SVG" and p.outline_ready(geom):
            ss = 2
            polys = ex.outline_polygons(p.model.outline, chord_mm=max(0.05, 0.5 / (k * kd)))
            acc = np.zeros((H * ss, W * ss), dtype=bool)
            for poly in polys:
                tmp = Image.new("1", (W * ss, H * ss), 0)
                ImageDraw.Draw(tmp).polygon([((fx + x * k) * kd * ss, (fy + y * k) * kd * ss) for x, y in poly], fill=1)
                acc ^= np.asarray(tmp, dtype=bool)
            layer = Image.fromarray(acc.astype(np.uint8) * 255, "L").resize((W, H), Image.Resampling.BOX)
            img.paste(Image.new("RGBA", (W, H), tuple(rgb) + (255,)), (0, 0), layer)
            return True
        return False

    def _draw_png(self, img, fx, fy, fw, fh) -> None:
        """PNG tab: the rendered preview PNG scaled into the file rectangle."""
        kd = Scale.factor
        src = self.page.model.png_image
        tw, th = max(1, int(round(fw * kd))), max(1, int(round(fh * kd)))
        img.alpha_composite(src.resize((tw, th), Image.Resampling.LANCZOS), (int(round(fx * kd)), int(round(fy * kd))))

    def _draw_badge(self, img, geom, texts) -> None:
        """Dark pill in the top left corner with the file size (tag_text)."""
        tag = self.page.tag_text(geom)
        if tag:
            tw = text_width(tag, 11.5, "semibold") + 20
            pill = gfx.rrect(tw, 22, 4, "#111317", fill_alpha=0.78)
            _paste_clip(img, pill, S(11), S(11))
            texts.append((21, 22, tag, 11.5, "semibold", "#FFFFFF", "w"))
