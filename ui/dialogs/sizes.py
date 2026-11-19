"""Signature sizes in Settings (stage 5, mockups 36, 37, 49, 51, 52, 56).

* ``SizeDialog`` — 37 «Добавить размер» / 49 «Изменить размер»: «Название» across, «Ширина, мм» and
  «Высота, мм» side by side, «Сохранить» + «Отмена» (Esc = Отмена).  Wrong numbers keep the dialog open.
* ``confirm_delete_size`` — 51 / 56 «Удалить размер «…»?» (red «Удалить», + «По умолчанию станет 15 × 5 мм»
  when the size was the default); used by Settings and by «Удалить шаблон» on screen 3.
* ``size_label`` / ``add_size`` / ``edit_size`` / ``delete_size`` / ``set_default_size`` — settings data."""
from __future__ import annotations

import logging
import re
from typing import Callable, Optional

from core import export as ex
from ui.dialogs.content import ContentDialog
from ui.theme import text_width
from ui.widgets.base import Box
from ui.widgets.controls import TextBox

log = logging.getLogger(__name__)

NBSP = "\u00a0"
LABEL_H, LABEL_GAP, FIELD_H, ROW_GAP = 16, 8, 32, 16
COL_GAP = 8


def _num_allowed(text: str) -> bool:
    return re.fullmatch(r"\d{0,4}([.,]\d{0,2})?", text) is not None


def lang(app) -> str:
    return getattr(app.i18n, "lang", "ru")


def wxh(app, w, h) -> str:
    return app.t("export.size.wxh", w=ex.format_plain_number(float(w), lang(app)),
                 h=ex.format_plain_number(float(h), lang(app)))


def size_label(app, sz: dict) -> str:
    """«Штамп КБ · 20 × 8 мм» (or only «20 × 8 мм» when the name is empty or the same)."""
    dims = wxh(app, sz["w_mm"], sz["h_mm"])
    name = str(sz.get("name") or "").strip()
    return dims if not name or name == dims else f"{name} · {dims}"


def custom_sizes(app):
    out = []
    for sz in app.settings.get("custom_sizes") or []:
        try:
            float(sz["w_mm"]), float(sz["h_mm"])
        except (KeyError, TypeError, ValueError):
            log.debug("custom_sizes: (KeyError, TypeError, ValueError) caught", exc_info=True)   # remark 81
            continue
        out.append(dict(sz))
    return out


# ------------------------------------------------------------------ data
def set_default_size(app, key: str) -> None:
    app.settings.set_export_default("default_size", key)


def add_size(app, name: str, w: float, h: float) -> str:
    sizes = custom_sizes(app)
    sid = ex.new_item_id(sizes)
    sizes.append({"id": sid, "name": name, "w_mm": w, "h_mm": h})
    app.settings.set("custom_sizes", sizes)
    return ex.TEMPLATE_PREFIX + sid


def edit_size(app, sid: str, name: str, w: float, h: float) -> None:
    sizes = custom_sizes(app)
    for sz in sizes:
        if str(sz.get("id")) == str(sid):
            sz.update(name=name, w_mm=w, h_mm=h)
    app.settings.set("custom_sizes", sizes)


def delete_size(app, sid: str) -> None:
    key = ex.TEMPLATE_PREFIX + str(sid)
    s = app.settings
    left, new_default = ex.remove_custom_size(custom_sizes(app), str(sid), s.get("default_size", ex.SIZE_15X5))
    s.set("custom_sizes", left)
    if new_default != s.get("default_size"):
        s.set("default_size", new_default)
    last = dict(s.get("last_export") or {})
    if last.get("size") == key:
        last.pop("size", None)
        s.set("last_export", last)


def delete_title(app, label: str, width: float = 420) -> str:
    """Keep the quoted name on one line when it fits (51: «Удалить размер» / «Штамп КБ · 20 × 8 мм»?)."""
    name = label
    if text_width(f"«{label}»?", 20, "semibold") <= width - 50:
        name = label.replace(" ", NBSP)
    return app.t("settings.delete_size.title", name=name)


def confirm_delete_size(app, sz: dict, on_done: Optional[Callable[[], None]] = None) -> ContentDialog:
    t = app.t
    key = ex.TEMPLATE_PREFIX + str(sz.get("id"))
    is_default = app.settings.get("default_size", ex.SIZE_15X5) == key
    body = t("settings.delete_size.default_note", size=t("export.size.preset_15x5")) if is_default else ""

    def ok():
        delete_size(app, str(sz.get("id")))
        if on_done:
            on_done()
    return ContentDialog(app, delete_title(app, size_label(app, sz)), body,
                         [(t("common.delete"), "danger", ok), (t("common.cancel"), "secondary", None)],
                         width=420, esc_index=1)


# ------------------------------------------------------------------ 37 / 49
class _Labels(Box):
    def __init__(self, master, dlg):
        super().__init__(master, bg="dialog")
        self.dlg = dlg

    def draw(self):
        t = self.dlg.app.t
        cw = (self.lw - COL_GAP) / 2
        self.text(0, LABEL_H / 2, t("common.name"), 13)
        y2 = LABEL_H + LABEL_GAP + FIELD_H + ROW_GAP
        self.text(0, y2 + LABEL_H / 2, t("settings.width_mm"), 13)
        self.text(cw + COL_GAP, y2 + LABEL_H / 2, t("settings.height_mm"), 13)


class SizeDialog(ContentDialog):
    """``sz`` = None → 37 «Добавить размер»; a saved size → 49 «Изменить размер» with its values."""

    FIELDS_H = 16 + (LABEL_H + LABEL_GAP + FIELD_H) * 2 + ROW_GAP

    def __init__(self, app, sz: Optional[dict] = None, on_done: Optional[Callable[[str], None]] = None):
        self.sz = sz
        self.on_done = on_done
        self.boxes = {}
        t = app.t
        if sz:
            self.init = (str(sz.get("name") or ""), ex.format_plain_number(float(sz["w_mm"]), lang(app)),
                         ex.format_plain_number(float(sz["h_mm"]), lang(app)))
        else:
            self.init = ("", "", "")
        super().__init__(app, t("settings.edit_size" if sz else "settings.add_size"), "",
                         [(t("common.save"), "primary", self._saved), (t("common.cancel"), "secondary", None)],
                         width=420, esc_index=1)

    def _body_h(self):
        return super()._body_h() + self.FIELDS_H

    def render(self):
        old = {k: b.entry.get() for k, b in self.boxes.items()}
        super().render()
        x, y, w = self.px, self.py, self.pw
        top = y + 1 + 24 + 25 + self.title_extra + 16
        lab = _Labels(self.root, self)
        lab.geom(x + 25, top, w - 50, self.FIELDS_H - 16)
        lab.lift()
        self.widgets.append(lab)
        cw = (w - 50 - COL_GAP) / 2
        spec = (("name", x + 25, top + LABEL_H + LABEL_GAP, w - 50, None),
                ("w", x + 25, top + 2 * (LABEL_H + LABEL_GAP) + FIELD_H + ROW_GAP, cw, _num_allowed),
                ("h", x + 25 + cw + COL_GAP, top + 2 * (LABEL_H + LABEL_GAP) + FIELD_H + ROW_GAP, cw, _num_allowed))
        self.boxes = {}
        for i, (k, bx, by, bw, allow) in enumerate(spec):
            tb = TextBox(self.root, self.app, old.get(k, self.init[i]), width=bw, bg="dialog", apply_button=False,
                         allow=allow, on_apply=lambda _t: self._activate(0) or True)
            if k != "name":
                tb.entry.configure(justify="center")      # 37 / 49: the numbers are centred
            tb.geom(bx, by, bw, FIELD_H)
            tb.lift()
            self.widgets.append(tb)
            self.boxes[k] = tb
        first = self.boxes["name"]
        self.root.after(10, lambda: (first.entry.focus_set(), first.entry.select_range(0, "end")))

    def values(self):
        name = self.boxes["name"].entry.get().strip()
        w = ex.parse_number(self.boxes["w"].entry.get())
        h = ex.parse_number(self.boxes["h"].entry.get())
        return name, w, h

    def valid(self):
        """Same limits as «Свой размер» on screen 3: room inside «Поле рамки», at most 2000 mm."""
        name, w, h = self.values()
        margin = float(self.app.settings.get("crop_margin_mm", ex.DEFAULT_MARGIN_MM) or 0)
        bad_w = w is None or not ex.valid_box_size(w, 2000, margin)
        bad_h = h is None or not ex.valid_box_size(2000, h, margin)
        return (not bad_w and not bad_h), ("w" if bad_w else ("h" if bad_h else None))

    def _activate(self, i):
        if i == 0 and not self.closed:
            ok, bad = self.valid()
            if not ok:
                b = self.boxes[bad]
                b.entry.focus_set()
                b.entry.select_range(0, "end")
                self.root.bell()
                return
        super()._activate(i)

    def _saved(self):
        name, w, h = self._result
        if self.sz:
            edit_size(self.app, str(self.sz.get("id")), name, w, h)
            key = ex.TEMPLATE_PREFIX + str(self.sz.get("id"))
        else:
            key = add_size(self.app, name, w, h)
        if self.on_done:
            self.on_done(key)

    def close(self):
        if not self.closed and self.boxes:
            name, w, h = self.values()
            if w is not None and h is not None:
                self._result = (name or wxh(self.app, w, h), round(w, 2), round(h, 2))
        super().close()
