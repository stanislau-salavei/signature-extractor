"""Dialog 10 «Свой цвет»: SV square 200, previews on paper / on transparent, hue bar, HEX + R G B fields,
name, footer «Отмена» / «Добавить».

Remark 25 (2026-11-17): an in-window ContentDialog like «О программе» (no system title bar, bold title
inside, footer buttons; Esc cancels, Enter adds)."""
from __future__ import annotations

import logging
import colorsys
import math
from typing import Callable, Optional

import numpy as np
from PIL import Image

from core import export as ex
from ui import gfx
from ui.dialogs.content import ContentDialog
from ui.theme import S, Scale, Theme, text_width
from ui.widgets.base import Box
from ui.widgets.controls import TextBox

log = logging.getLogger(__name__)

W, H = 418, 500
DLG_W = 428                # panel: 1 + 4 + board (20 … 398) + 25
BOARD_DY = 24 + 25 + 16 - 18   # board y inside the panel: its first row (y 18) starts under the title
PAPER = {"light": "#EFECE3", "dark": "#3A3830"}
CHECK = {"light": ("#FFFFFF", "#E6E8EC"), "dark": ("#2A2A2A", "#1C1C1C")}


class _Board(Box):
    def __init__(self, master, dlg):
        super().__init__(master, bg="dialog")
        self.dlg = dlg
        self.drag = None
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag", None))

    def _press(self, e):
        x, y = e.x / Scale.factor, e.y / Scale.factor
        if 20 <= x <= 220 and 18 <= y <= 218:
            self.drag = "sv"
        elif 20 <= x <= 398 and 250 <= y <= 276:
            self.drag = "hue"
        else:
            self.drag = None
        self._move(e)

    def _move(self, e):
        x, y = e.x / Scale.factor, e.y / Scale.factor
        d = self.dlg
        if self.drag == "sv":
            d.s = min(max((x - 20) / 200, 0), 1)
            d.v = 1 - min(max((y - 18) / 200, 0), 1)
        elif self.drag == "hue":
            d.h = min(max((x - 20) / 378, 0), 0.999)
        else:
            return
        d.changed()

    def draw(self):
        d = self.dlg
        t = d.app.t
        n = S(200)
        sx = np.linspace(0, 1, n)[None, :, None]
        vy = np.linspace(1, 0, n)[:, None, None]
        base = np.array(colorsys.hsv_to_rgb(d.h, 1, 1))[None, None, :]
        arr = (vy * ((1 - sx) + sx * base) * 255).astype(np.uint8)
        sv = Image.fromarray(arr, "RGB").convert("RGBA")
        mask = gfx.rrect(200, 200, 4, "#FFFFFF").getchannel("A").resize(sv.size)
        img = Image.new("RGBA", sv.size, gfx.rgba(Theme.c("dialog")))
        img.paste(sv, (0, 0), mask)
        img.alpha_composite(gfx.rrect(200, 200, 4, None, Theme.c("card_stroke")).resize(sv.size))
        self.put(20, 18, img)
        cx, cy = 20 + d.s * 200, 18 + (1 - d.v) * 200
        self.put(cx - 7, cy - 7, gfx.circle(14, None, "#FFFFFF", 2))
        # hue bar 378×12 r4 at y 257, thumb 20
        hw = S(378)
        hs = np.linspace(0, 1, hw)
        row = (np.array([colorsys.hsv_to_rgb(h, 1, 1) for h in hs]) * 255).astype(np.uint8)
        hue = Image.fromarray(np.repeat(row[None], S(12), axis=0), "RGB").convert("RGBA")
        hm = gfx.rrect(378, 12, 4, "#FFFFFF").getchannel("A").resize(hue.size)
        hb = Image.new("RGBA", hue.size, gfx.rgba(Theme.c("dialog")))
        hb.paste(hue, (0, 0), hm)
        self.put(20, 257, hb)
        hx = 20 + min(max(d.h * 378, 10), 368)
        pure = ex.rgb_to_hex(tuple(int(c * 255) for c in colorsys.hsv_to_rgb(d.h, 1, 1)))
        self.put(hx - 10, 263 - 10, gfx.circle(20, pure, "#FFFFFF", 3))
        # labels
        for x, y, key in ((234, 25, "color.on_paper"), (234, 129, "color.on_transparent"), (20, 239.5, "color.hue"),
                          (20, 290.5, None), (d.rgb_layout()[1][0], 290.5, "R"), (d.rgb_layout()[1][1], 290.5, "G"),
                          (d.rgb_layout()[1][2], 290.5, "B"), (20, 357.5, "common.name")):
            s = "HEX" if key is None else (key if len(key) == 1 else t(key))
            self.text(x, y, s, 11.5 if key and key.startswith("color.on") else 12, color="muted")
        # previews 164×74
        rgb = d.rgb()
        for y, kind in ((40, "paper"), (144, "clear")):
            pw, ph = S(164), S(74)
            if kind == "paper":
                pv = Image.new("RGBA", (pw, ph), gfx.rgba(PAPER[Theme.mode]))
            else:
                c1, c2 = CHECK[Theme.mode]
                pv = gfx.checker(pw, ph, max(1, S(6)), c1, c2)
            if d.sig is not None:
                k = min((pw - S(24)) / d.sig.width, (ph - S(16)) / d.sig.height)
                a = d.sig.resize((max(1, int(d.sig.width * k)), max(1, int(d.sig.height * k))), Image.Resampling.LANCZOS)
                layer = Image.new("RGBA", a.size, tuple(rgb) + (0,))
                layer.putalpha(a)
                pv.alpha_composite(layer, ((pw - a.width) // 2, (ph - a.height) // 2))
            m = gfx.rrect(164, 74, 4, "#FFFFFF").getchannel("A").resize(pv.size)
            out = Image.new("RGBA", pv.size, gfx.rgba(Theme.c("dialog")))
            out.paste(pv, (0, 0), m)
            out.alpha_composite(gfx.rrect(164, 74, 4, None, Theme.c("card_stroke")).resize(pv.size))
            self.put(234, y, out)


class CustomColorDialog(ContentDialog):
    def __init__(self, app, mask, done: Callable[[str, str], None],
                 edit: Optional[dict] = None):
        """``edit`` = a saved own colour {id, name, hex} → remark 47 «Изменить цвет»: the dialog opens with its
        colour and name, the button is «Сохранить»."""
        self.done = done
        self.edit = edit
        start = (0x3A, 0x2F, 0x8F)
        if edit and edit.get("hex"):
            try:
                start = ex.hex_to_rgb(str(edit["hex"]))
            except Exception:
                log.warning("CustomColorDialog.__init__: Exception caught", exc_info=True)   # remark 81
        r, g, b = (c / 255 for c in start)
        self.h, self.s, self.v = colorsys.rgb_to_hsv(r, g, b)
        self.sig = None
        if mask is not None and mask.any():
            self.sig = Image.fromarray(mask.astype(np.uint8) * 255, "L")
        self.board = None
        self._name = str(edit.get("name") or "") if edit else ""
        if edit and self._name == str(edit.get("hex") or ""):
            self._name = ""
        self._sync = False
        t = app.t
        super().__init__(app, t("settings.edit_color" if edit else "color.custom"), "", [
            (t("common.cancel"), "secondary", None),
            (t("common.save" if edit else "common.add"), "primary", None)], width=DLG_W)
        self.cv.bind("<Return>", lambda e: self._activate(1))

    def _body_h(self):
        return BOARD_DY + 403 + 20      # last row: the name field (y 371 + 32) + bottom padding

    def render(self):
        if self.board is not None:
            self._name = self.f_name.get()
        super().render()
        app = self.app
        self.board = _Board(self.root, self)
        self.board.geom(self.px + 5, self.py + 1 + BOARD_DY, W - 20 + 2, 403 + 8)
        self.board.lift()
        self.widgets.append(self.board)
        num = lambda s: s == "" or (s.isdigit() and len(s) <= 3)
        hexok = lambda s: len(s) <= 7 and all(ch in "#0123456789abcdefABCDEF" for ch in s)
        rgb_w, rgb_x, hex_w = self.rgb_layout()
        self.f_hex = TextBox(self.board, app, "", width=hex_w, bg="dialog", apply_button=False, font_px=13,
                             allow=hexok, chip=lambda: ex.rgb_to_hex(self.rgb()),
                             on_apply=lambda s: self._commit("hex"), on_change=lambda s: self._live("hex"))
        self.f_rgb = [TextBox(self.board, app, "", width=0, fit="255", bg="dialog", apply_button=False, font_px=13, allow=num,
                              on_apply=lambda s: self._commit("rgb"), on_change=lambda s: self._live("rgb"))
                      for _ in range(3)]
        self.f_name = TextBox(self.board, app, self._name, width=378, bg="dialog", apply_button=False, font_px=13,
                              placeholder=app.t("color.name_placeholder"), on_apply=lambda s: self.submit() or True)
        self.f_hex.geom(20, 304, hex_w, 32)
        for i, f in enumerate(self.f_rgb):
            f.geom(rgb_x[i], 304, rgb_w, 32)
        self.f_name.geom(20, 371, 378, 32)
        for f in [self.f_hex, self.f_name] + self.f_rgb:
            f.entry.bind("<Escape>", lambda e: self.root.after(1, self.close), add="+")
        self.changed()
        self.cv.focus_force()     # modal: take the keyboard even if focus was on a widget that just went away

    def rgb_layout(self):
        """Remark 33: R/G/B fit «255» with «×» (real font); they end at the name field's right edge (398),
        8 px apart; HEX takes the rest after a 10 px gap.  Returns (rgb_w, [x_r, x_g, x_b], hex_w)."""
        rgb_w = float(math.ceil(11 + text_width("255", 13) + 3 + TextBox.CLEAR_AREA))
        x0 = 398 - (3 * rgb_w + 2 * 8)
        return rgb_w, [x0 + (rgb_w + 8) * i for i in range(3)], x0 - 10 - 20

    def _activate(self, i):
        if self.closed:
            return
        if i == 1:
            self.submit()
        else:
            self.close()

    def rgb(self):
        r, g, b = colorsys.hsv_to_rgb(self.h, self.s, self.v)
        return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))

    def changed(self, skip=None):
        self.board.redraw()
        r, g, b = self.rgb()
        self._sync = True
        if skip != "hex":
            self.f_hex.set(ex.rgb_to_hex((r, g, b)))
        self.f_hex.redraw()
        if skip != "rgb":
            for f, v in zip(self.f_rgb, (r, g, b)):
                f.set(str(v))
        self._sync = False

    def _parse(self, which):
        try:
            if which == "hex":
                txt = self.f_hex.get().strip()
                if len(txt.lstrip("#")) != 6:
                    return None
                return ex.hex_to_rgb(txt)
            vals = tuple(int(f.get()) for f in self.f_rgb)
            return vals if all(0 <= v <= 255 for v in vals) else None
        except ValueError:
            log.debug("CustomColorDialog._parse: ValueError caught", exc_info=True)   # remark 81
            return None

    def _live(self, which):
        if self._sync:
            return
        rgb = self._parse(which)
        if rgb:
            self.h, self.s, self.v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
            self.changed(skip=which)

    def _commit(self, which):
        rgb = self._parse(which)
        if rgb:
            self.h, self.s, self.v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
        self.changed()
        return True

    def submit(self):
        if self.closed:
            return
        hx = ex.rgb_to_hex(self.rgb())
        name = self.f_name.get().strip() or hx
        self.close()
        self.done(name, hx)
