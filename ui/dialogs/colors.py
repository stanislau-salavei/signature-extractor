"""Own signature colours (remarks 47 and 58, 2026-11-18): data helpers and the shared delete confirmation.

* ``color_items`` — [(key, name, hex | None, is_custom)] in the order of screen 3: «Как на фото», the
  built-in colours, then the user's own colours.
* ``add_color`` / ``edit_color`` / ``set_default_color`` — settings data.
* ``confirm_delete_color`` — «Удалить цвет «{name}»?», red «Удалить» + «Отмена» (Esc = «Отмена»); when the
  colour was the default, the line «По умолчанию станет Синий».  Used by Settings › «Цвет подписи по
  умолчанию» and by «Удалить цвет» / right click on screen 3."""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from core import export as ex
from ui.dialogs.content import ContentDialog
from ui.theme import text_width

NBSP = "\u00a0"


def custom_colors(app) -> List[dict]:
    return [dict(c) for c in (app.settings.get("custom_colors") or []) if isinstance(c, dict)]


def color_items(app) -> List[Tuple[str, str, Optional[str], bool]]:
    t = app.t
    items = [(k, t(f"color.{k}"), hx, False) for k, hx in ex.BUILTIN_COLORS]
    for c in custom_colors(app):
        items.append((ex.CUSTOM_COLOR_PREFIX + str(c.get("id")), str(c.get("name") or c.get("hex")),
                      c.get("hex", "#000000"), True))
    return items


def color_name(app, key: str) -> str:
    for k, name, _hx, _c in color_items(app):
        if k == key:
            return name
    return app.t("color.blue")


def find_custom(app, key: str) -> Optional[dict]:
    if not key.startswith(ex.CUSTOM_COLOR_PREFIX):
        return None
    cid = key[len(ex.CUSTOM_COLOR_PREFIX):]
    return next((c for c in custom_colors(app) if str(c.get("id")) == cid), None)


def set_default_color(app, key: str) -> None:
    app.settings.set_export_default("default_color", key)


def add_color(app, name: str, hx: str) -> str:
    colors = custom_colors(app)
    cid = ex.new_item_id(colors)
    colors.append({"id": cid, "name": name, "hex": hx})
    app.settings.set("custom_colors", colors)
    return ex.CUSTOM_COLOR_PREFIX + cid


def edit_color(app, key: str, name: str, hx: str) -> None:
    cid = key[len(ex.CUSTOM_COLOR_PREFIX):]
    colors = custom_colors(app)
    for c in colors:
        if str(c.get("id")) == cid:
            c.update(name=name, hex=hx)
    app.settings.set("custom_colors", colors)


def delete_title(app, name: str, width: float = 420) -> str:
    if text_width(f"«{name}»?", 20, "semibold") <= width - 50:
        name = name.replace(" ", NBSP)
    return app.t("settings.delete_color.title", name=name)


def confirm_delete_color(app, key: str, on_done: Optional[Callable[[], None]] = None) -> Optional[ContentDialog]:
    if find_custom(app, key) is None:          # built-in colours are not deleted
        return None
    t = app.t
    is_default = app.settings.get("default_color", ex.DEFAULT_COLOR_KEY) == key
    body = t("settings.delete_color.default_note", name=t("color.blue")) if is_default else ""

    def ok():
        app.settings.delete_custom_color(key)
        if on_done:
            on_done()
    return ContentDialog(app, delete_title(app, color_name(app, key)), body,
                         [(t("common.delete"), "danger", ok), (t("common.cancel"), "secondary", None)],
                         width=420, esc_index=1)
