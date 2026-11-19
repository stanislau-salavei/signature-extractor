"""ContentDialog (04, 20, 29, 30, 31, 34, 43): smoke over the window, panel radius 8,
body padding 24 24 20 (title 20/600 lh 25, gap 16, text 14 lh 20.3), footer 81 with equal buttons."""
from __future__ import annotations

import logging
import tkinter as tk
from typing import Callable, List, Optional, Sequence, Tuple

from PIL import Image, ImageTk

from ui import gfx
from ui.theme import F, S, Scale, Theme, elide, text_width
from ui.widgets.base import Box, Tooltip
from ui.widgets.controls import Button, CheckRow, TextBox
from ui.widgets.overlay import DIALOG_SHADOW, Popup, _paste_clip, grab_window

log = logging.getLogger(__name__)


def wrap_runs(runs: Sequence[Tuple[str, str]], width: float, px: float = 14) -> List[List[Tuple[str, str]]]:
    """Greedy word wrap of (text, weight) runs into lines of runs.  A word split between runs (e.g. bold
    «_» + ".") moves to the next line as a whole, so punctuation never starts a line on its own."""
    words: List[List[Tuple[str, str]]] = []
    open_word = False
    for text, weight in runs:
        parts = text.split(" ")
        for i, wd in enumerate(parts):
            token = wd if i == len(parts) - 1 else wd + " "
            if not token:
                continue
            if not open_word:
                words.append([])
            words[-1].append((token, weight))
            open_word = not token.endswith(" ")
    lines: List[List[Tuple[str, str]]] = [[]]
    cur_w = 0.0
    for word in words:
        ww = sum(text_width(tk, px, wt) for tk, wt in word)
        if cur_w + ww > width and cur_w > 0 and "".join(tk for tk, _ in word).strip():
            lines.append([])
            cur_w = 0.0
            word = [(word[0][0].lstrip(), word[0][1])] + word[1:]
            ww = sum(text_width(tk, px, wt) for tk, wt in word)
        for token, weight in word:
            if not token:
                continue
            if lines[-1] and lines[-1][-1][1] == weight:
                lines[-1][-1] = (lines[-1][-1][0] + token, weight)
            else:
                lines[-1].append((token, weight))
        cur_w += ww
    return lines


TITLE_LH = 26


class _Body(Box):
    def __init__(self, master, dlg):
        super().__init__(master, bg="dialog")
        self.dlg = dlg

    def draw(self):
        d = self.dlg
        for i, ln in enumerate(d.title_lines):
            self.text(0, 12.5 + TITLE_LH * i, ln, 20, "semibold")
        y = 25 + d.title_extra + 16
        for line in d.lines:
            x = 0.0
            for text, weight in line:
                self.text(x, y + 10.15, text, 14, weight)
                x += text_width(text, 14, weight)
            y += 20.3
        if d.field_label:
            self.text(0, y + 8, d.field_label, 13)
        if d.rows:
            # 47: file list — bg #F3F3F3-like chip, stroke, radius 4, rows 36 (pad 0 12), dividers
            y += 14
            lw = self.dlg.width - 50
            lh = 2 + len(d.rows) * 36 + (len(d.rows) - 1)
            self.rrect(0, y, lw, lh, 4, "chip", "card_stroke")
            ry = y + 1
            for i, (name, size) in enumerate(d.rows):
                if i:
                    self.create_rectangle(S(1), S(ry), S(lw - 1), S(ry) + max(1, S(1)), width=0,
                                          fill=Theme.c("divider_bg"))
                    ry += 1
                sw = text_width(size, 13.5)
                self.text(13, ry + 18, elide(name, lw - 26 - sw - 12, 13.5), 13.5)
                self.text(lw - 13, ry + 18, size, 13.5, color="muted", anchor="e")
                ry += 36


class ContentDialog(Popup):
    def __init__(self, app, title: str, body, buttons: Sequence[Tuple[str, str, Optional[Callable]]],
                 width: float = 420, field: Optional[dict] = None, on_close=None,
                 check: Optional[str] = None, rows: Optional[Sequence[Tuple[str, str]]] = None,
                 esc_index: Optional[int] = None):
        """``body`` = str or [(text, weight), ...]. ``field`` = {label, value, on_ok(text)->bool}.
        ``check`` = label of a checkbox row under the text (44); button callbacks then get its value.
        ``rows`` = [(name, right text)] list box under the text (47)."""
        Tooltip.cancel(None)
        super().__init__(app, on_close)
        self.title = title
        # stage 5 (51): a long title («Удалить размер «…»?») wraps; lines 26 apart
        self.title_lines = ["".join(t for t, _ in ln).rstrip() for ln in
                            wrap_runs([(title, "semibold")], width - 50, 20)] if title else [""]
        self.title_extra = TITLE_LH * (len(self.title_lines) - 1)
        runs = [(body, "normal")] if isinstance(body, str) else list(body)
        self.lines = wrap_runs(runs, width - 2 - 48) if body else []
        self.field_label = field.get("label") if field else None
        self.buttons_spec = list(buttons)
        self.width = width
        self.field = field
        self.check_label = check
        self.esc_index = esc_index    # Esc = this button (e.g. «Отмена» that must reach its callback)
        self.checked = False
        self.rows = list(rows or [])[:8]   # long lists are cut to 8 rows (window height)
        self.button_w = getattr(self, "button_w", None)   # fixed width → buttons right-aligned
        self.widgets: List[tk.Widget] = []
        self.cv.bind("<Return>", lambda e: self._activate(0))
        self.render()
        self.root.bind("<Configure>", self._on_resize, add="+")

    def _body_h(self):
        h = 24 + 25 + self.title_extra + (16 + len(self.lines) * 20.3 if self.lines else 0)
        if self.field:
            h += 16 + 16 + 8 + 32  # gap + label line + gap + entry
        if self.check_label:
            h += 16 + 20
        if self.rows:
            h += 14 + 2 + len(self.rows) * 36 + (len(self.rows) - 1)
        return h + 20

    def render(self):
        W, H = self.app.width(), self.app.height()
        w = self.width
        body_h = self._body_h()
        h = 1 + body_h + 81 + 1
        # centred in the whole window incl. the 32 px title bar, as in the mockups
        x, y = round((W - w) / 2, 1), round(max(8, (H - h) / 2 - 16), 1)
        self.px, self.py, self.pw, self.ph = x, y, w, h
        img = self.backdrop.copy()
        smoke = Image.new("RGBA", img.size, (0, 0, 0, int(255 * (0.5 if Theme.dark() else 0.3))))
        img.alpha_composite(smoke)
        pad = 60
        sh = gfx.shadow_box(w, h, 8, DIALOG_SHADOW, pad)
        _paste_clip(img, sh, S(x - pad), S(y - pad))
        panel = gfx.rrect(w, h, 8, Theme.c("dialog"), Theme.c("dialog_stroke"))
        _paste_clip(img, panel, S(x), S(y))
        foot = gfx.rrect(w - 2, 81, 7, Theme.c("dialog_foot"), corners=(False, False, True, True))
        _paste_clip(img, foot, S(x + 1), S(y + 1 + body_h))
        line = Image.new("RGBA", (S(x + w - 1) - S(x + 1), max(1, S(1))), gfx.rgba(Theme.c("divider_bg")))
        _paste_clip(img, line, S(x + 1), S(y + 1 + body_h))
        self._imgs = [ImageTk.PhotoImage(img)]
        self.cv.delete("all")
        self.cv.create_image(0, 0, image=self._imgs[0], anchor="nw")
        for wd in self.widgets:
            wd.destroy()
        self.widgets.clear()
        body = _Body(self.root, self)
        body.geom(x + 25, y + 25, w - 50, body_h - 44)
        body.lift()
        self.widgets.append(body)
        if self.field:
            tb = TextBox(self.root, self.app, self.field.get("value", ""), width=w - 50, bg="dialog",
                         apply_button=False, on_apply=lambda t: self._activate(0) or True)
            fy = y + 1 + 24 + 25 + self.title_extra + (16 + len(self.lines) * 20.3 if self.lines else 0) + 16 + 16 + 8
            tb.geom(x + 25, fy, w - 50, 32)
            tb.lift()
            self.widgets.append(tb)
            self.textbox = tb
            self.root.after(10, lambda: (tb.entry.focus_set(), tb.entry.select_range(0, "end")))
        if self.check_label:
            cy = y + 1 + 24 + 25 + self.title_extra + (16 + len(self.lines) * 20.3 if self.lines else 0) + 16
            cb = CheckRow(self.root, self.check_label, checked=self.checked, bg="dialog",
                          command=lambda v: setattr(self, "checked", v))
            cb.geom(x + 25, cy - 1, min(w - 50, 28 + text_width(self.check_label, 14) + 4), 22)
            cb.lift()
            self.widgets.append(cb)
        n = len(self.buttons_spec)
        inner = w - 2 - 48
        bw = (inner - 8 * (n - 1)) / n if not self.button_w else self.button_w
        bx0 = x + 1 + 24 if not self.button_w else x + w - 1 - 24 - n * bw - 8 * (n - 1)
        by = y + 1 + body_h + 25
        for i, (label, kind, _cb) in enumerate(self.buttons_spec):
            b = Button(self.root, label, kind=kind, bg="dialog_foot", command=lambda i=i: self._activate(i), pad=10)
            b.geom(bx0 + i * (bw + 8), by, bw, 32)
            b.lift()
            self.widgets.append(b)
        if not self.field:
            self.cv.focus_set()

    def _on_resize(self, e):
        if self.closed or e.widget is not self.root:
            return
        # re-snapshot without the dialog after the window settles
        self.root.after(80, self._resnap)

    def _resnap(self):
        if self.closed:
            return
        for wd in self.widgets:
            wd.place_forget()
        self.cv.place_forget()
        self.root.update()
        self.backdrop = grab_window(self.root)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.cv.tk.call("raise", self.cv._w)
        self.render()

    def escape(self):
        if self.esc_index is not None:
            self._activate(self.esc_index)
        else:
            self.close()

    def _press(self, e):
        pass  # modal: clicks outside do nothing

    def _activate(self, i):
        if self.closed:
            return
        label, kind, cb = self.buttons_spec[i]
        if self.field and i == 0 and cb is not None:
            ok = cb(self.textbox.get())
            if ok is False:
                return
            self.close()
            return
        self.close()
        if cb:
            if self.check_label:
                v = self.checked
                self.root.after(1, lambda: cb(v))
            else:
                self.root.after(1, cb)

    def close(self):
        for wd in self.widgets:
            try:
                wd.destroy()
            except tk.TclError:
                log.debug("ContentDialog.close: tk.TclError caught", exc_info=True)   # remark 81
        self.widgets.clear()
        super().close()
