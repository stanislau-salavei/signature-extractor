"""Dialog 32 «Доступна новая версия» (stage 5) and its download state.

«Скачать» keeps the dialog open: the text becomes «Скачивание… N %» with a progress bar and the only
button is «Отмена» (user decision 2026-11-18; no mockup) — normal width, right-aligned (remark 46).  Esc = «Позже» / «Отмена»."""
from __future__ import annotations

from typing import Callable, Optional

from ui.dialogs.content import ContentDialog, wrap_runs
from ui.widgets.base import Box

BAR_H, BAR_GAP = 4, 14


class _Bar(Box):
    def __init__(self, master, dlg):
        super().__init__(master, bg="dialog")
        self.dlg = dlg

    def draw(self):
        w = self.lw
        self.rrect(0, 0, w, BAR_H, BAR_H / 2, "toggle_off_stroke")
        f = max(0.0, min(1.0, self.dlg.fraction))
        if f > 0:
            self.rrect(0, 0, max(BAR_H, w * f), BAR_H, BAR_H / 2, "accent")


class UpdateDialog(ContentDialog):
    def __init__(self, app, version: str, on_download: Callable[[], None], on_later: Callable[[], None],
                 on_cancel: Callable[[], None]):
        self.version = version
        self.on_download, self.on_later, self.on_cancel = on_download, on_later, on_cancel
        self.downloading = False
        self.fraction = 0.0
        self._bar: Optional[_Bar] = None
        t = app.t
        super().__init__(app, t("update.title"), t("update.body", version=version),
                         [(t("common.download"), "primary", None), (t("common.later"), "secondary", None)],
                         width=420, esc_index=1)

    # --------------------------------------------------------------- states
    def _activate(self, i):
        if self.closed:
            return
        if not self.downloading:
            if i == 0:
                self.start_download()
            else:
                self.close()
                self.on_later()
            return
        self.close()                      # «Отмена» while downloading
        self.on_cancel()

    def start_download(self):
        t = self.app.t
        self.downloading = True
        self.fraction = 0.0
        self.buttons_spec = [(t("common.cancel"), "secondary", None)]
        # remark 46: «Отмена» keeps the normal width of a two-button footer and sits on the right
        self.button_w = (self.width - 2 - 48 - 8) / 2
        self.esc_index = 0
        self._set_text(0)
        self.render()
        self.on_download()

    def _set_text(self, percent: int):
        self.lines = wrap_runs([(self.app.t("update.downloading", percent=percent), "normal")], self.width - 2 - 48)

    def set_progress(self, done: int, total: int):
        if self.closed or not self.downloading:
            return
        self.fraction = (done / total) if total else 0.0
        self._set_text(int(round(self.fraction * 100)))
        if self.widgets:
            self.widgets[0].redraw()     # the text body
        if self._bar is not None:
            self._bar.redraw()

    # --------------------------------------------------------------- layout
    def _body_h(self):
        return super()._body_h() + ((BAR_GAP + BAR_H) if getattr(self, "downloading", False) else 0)

    def render(self):
        super().render()
        self._bar = None
        if self.downloading:
            x, y, w = self.px, self.py, self.pw
            by = y + 1 + 24 + 25 + self.title_extra + 16 + len(self.lines) * 20.3 + BAR_GAP
            bar = _Bar(self.root, self)
            bar.geom(x + 25, by, w - 50, BAR_H)
            bar.lift()
            self.widgets.append(bar)
            self._bar = bar
