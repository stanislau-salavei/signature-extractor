"""Settings page (27, 64–67): Win11 Settings-style cards.

Column padding 0 56 32; cards 63 high, 7 apart; groups 56 apart (header 14/600 + 8 included);
row padding 0 16, icon 20 at x 17, text at x 51 (title 14/18, description 12/16); right controls end
16 px from the card edge with a 12 px gap.  Expanders: theme (radios), formats (checkboxes),
sizes (stage 5: the size manager of 36 / 52 — rows with «…» menus, «По умолчанию» badge, «Добавить размер»)
and «Сведения» (links).  Stage 5: the column is at most 1000 px wide and centred (2k_27)."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from tkinter import filedialog
from typing import Callable, List, Optional

from core import export as ex
from core.version import LICENSE_URL, RELEASE_TAG, REPO_URL  # remark 84 / 118 (A13): one place
from ui import gfx
from ui.dialogs import sizes as SZ
from ui.dialogs.color_dialog import CustomColorDialog
from ui.dialogs.colors import (add_color, color_items, color_name, confirm_delete_color, edit_color, find_custom,
    set_default_color)
from ui.dialogs.content import ContentDialog, wrap_runs
from ui.dialogs.sizes import SizeDialog, confirm_delete_size
from ui.theme import S, Theme, elide, text_width
from ui.widgets.base import Box
from ui.widgets.controls import Button, CheckRow, ComboBox, IconButton, Link, Radio, TextBox, Toggle
from ui.widgets.overlay import MenuItem, MenuPopup, widget_rect
from ui.widgets.scroll import ScrollArea

log = logging.getLogger(__name__)

CARD_H = 63
FMT_ROWS_H = 147        # «Форматы по умолчанию»: three checkbox rows, 49 each
SVG_LINE_ROW_H = 64     # remark 32: «Толщина SVG» card, second row «Толщина линии» (variant B)
DPI_COMBO_MIN = 120
GAP = 7
GROUP_GAP = 28          # + header 20 + 8 = 56 between groups
PAGE_MAX_W = 1000      # stage 5 (2k_25 / 2k_27): .col {max-width: 1000px; margin: 0 auto}
SIZE_ROW_H = 40         # 36: rows of «Размеры подписи» 40 apart, first centre 24 below the divider
SIZE_BTN_H = 32
COLOR_ROW_H = 32        # remark 47 (mockup_colors): colour rows 32 apart
THEME_ORDER = ("light", "dark", "system")   # as in Win11 Calculator: «Светлая», «Тёмная», «Использовать параметры системы»


class SCard(Box):
    """One settings card. ``expand`` = None (plain row) or a callable returning the body height."""

    def __init__(self, master, page, icon: Optional[str], title: Callable[[], str],
                 desc: Optional[Callable[[], str]] = None, summary: Optional[Callable[[], str]] = None,
                 expandable: bool = False, open_: bool = False, body_h: Callable[[], float] = lambda: 0,
                 logo: bool = False, extra_h: Callable[[], float] = lambda: 0):
        super().__init__(master, bg="bg")
        self.page = page
        self.icon_name, self.title_fn, self.desc_fn, self.summary_fn = icon, title, desc, summary
        self.expandable, self.is_open, self.body_h_fn, self.logo = expandable, open_, body_h, logo
        self.extra_h_fn = extra_h   # always-visible rows under the header (not an expander)
        self.hover = False
        self.extra_draw: Optional[Callable[["SCard"], None]] = None  # page-owned items, redrawn with the card
        if expandable:
            self.bind("<Enter>", lambda e: self._hov(e))
            self.bind("<Motion>", self._hov)
            self.bind("<Leave>", lambda e: self._set_hover(False))
            self.bind("<ButtonRelease-1>", self._click)

    desc_room: Optional[float] = None   # remark 44: set by the page → the description wraps to fit

    note_fn: Optional[Callable[[], str]] = None   # stage 5: grey line under the description (none since remark 78)

    def desc_lines(self) -> List[str]:
        desc = self.desc_fn() if self.desc_fn else ""
        note = self.note_fn() if self.note_fn else ""
        extra = [note] if note else []
        if not desc or self.desc_room is None or text_width(desc, 12) <= self.desc_room:
            return ([desc] if desc else []) + extra
        return ["".join(t for t, _ in ln).rstrip() for ln in wrap_runs([(desc, "normal")], self.desc_room, 12)] + extra

    def head_h(self) -> float:
        return CARD_H + 16 * max(0, len(self.desc_lines()) - 1)

    def height(self) -> float:
        return self.head_h() + (self.body_h_fn() if (self.expandable and self.is_open) else 0) + self.extra_h_fn()

    def _hov(self, e):
        self._set_hover(e.y < S(CARD_H - 1))

    def _set_hover(self, h):
        if h != self.hover:
            self.hover = h
            self.redraw()

    def _click(self, e):
        if e.y < S(CARD_H - 1):
            self.is_open = not self.is_open
            self.page.layout_content()

    def draw(self):
        w, h = self.lw, self.lh
        self.rrect(0, 0, w, h, 8, "card", "card_stroke")
        if self.hover:
            hh = CARD_H - 1 if self.is_open else h - 2
            corners = (True, True, not self.is_open, not self.is_open)
            self.rrect(1, 1, w - 2, hh, 7, "card_hover", bg="card", corners=corners)
        if self.expandable and self.is_open:
            self.create_rectangle(S(1), S(CARD_H - 1), S(w - 1), S(CARD_H), fill=Theme.c("divider"), width=0)
        cy = self.head_h() / 2 if self.desc_room is not None else CARD_H / 2
        if self.logo:
            self.put_cached(17, cy - 16, ("logo", 32), lambda: gfx.icon("app_tile", 32, None))
            tx = 63
        else:
            if self.icon_name:
                self.icon(self.icon_name, 17, cy - 10, 20, "text_card")
            tx = 51
        lines = self.desc_lines()
        if len(lines) > 1:
            top = cy - (18 + 16 * len(lines)) / 2
            self.text(tx, top + 9, self.title_fn(), 14, color="text_card")
            for i, ln in enumerate(lines):
                self.text(tx, top + 18 + 16 * i + 8, ln, 12, color="muted")
        elif lines:
            self.text(tx, 14.5 + 9, self.title_fn(), 14, color="text_card")
            self.text(tx, 32.5 + 8, lines[0], 12, color="muted")
        else:
            self.text(tx, cy, self.title_fn(), 14, color="text_card")
        x = w - 17
        if self.expandable:
            self.icon("chev_up" if self.is_open else "chev_down16", x - 16, cy - 8, 16, "text_card")
            x -= 16 + 12
        if self.summary_fn:
            self.text(x, cy, self.summary_fn(), 14, color="muted", anchor="e")
        if self.extra_draw:
            self.extra_draw(self)


class SettingsPage(Box):
    def __init__(self, master, app):
        super().__init__(master, bg="bg")
        self.app = app
        s = app.settings
        t = app.t
        self.back = IconButton(self, "back", 16, bg="bg", command=app.close_settings,
                               tooltip=lambda: app.t("common.back"))
        self.area = ScrollArea(self)
        inner = self.area.inner
        self.cards: List[tuple] = []   # (group_key | None, card)
        self.headers = {}
        self.update_note = ""
        self._lic_y = 0.0

        # ------------------------------------------------ Appearance («Внешний вид»)
        self.c_theme = SCard(inner, self, "theme", lambda: t("settings.theme"), lambda: t("settings.theme.desc"),
                             expandable=True, body_h=lambda: 115)   # no summary: chevron only, as in Calculator
        self.theme_radios = [Radio(self.c_theme, "", bg="card", command=lambda v=v: self._set_theme(v))
                             for v in THEME_ORDER]
        self.c_lang = SCard(inner, self, "globe", lambda: t("settings.language"), lambda: t("settings.language.desc"))
        self.lang_combo = ComboBox(self.c_lang, app, bg="card", command=self._set_lang)
        # remark 78: no section «Обработка» (AI search, GPU acceleration) — no AI in v1.0
        # ------------------------------------------------ Export («Экспорт»)
        self.c_formats = SCard(inner, self, "formats", lambda: t("settings.formats"), lambda: t("settings.formats.desc"),
                               expandable=True, body_h=lambda: FMT_ROWS_H)   # chevron only (remark 18)
        self.fmt_rows = {}
        for code, key in (("PNG", "export.png.desc"), ("SVG", "export.svg.desc"), ("DXF", "export.dxf.desc")):
            self.fmt_rows[code] = (CheckRow(self.c_formats, code, t(key), bg="card",
                                            command=lambda v, c=code: self._toggle_format(c, v)), key)
        # remark 32 (variant B): «Толщина SVG» is its own card under «Форматы по умолчанию» — a ComboBox
        # «Как в оригинале» / «Заданная толщина»; with «Заданная толщина» a second row «Толщина линии».
        # Both are the defaults of the SVG card on screen 3 (svg_mode, svg_line_mm).
        self.c_svg = SCard(inner, self, "svg_thickness", lambda: t("settings.svg_mode"),
                           lambda: t("settings.svg_mode.desc"), extra_h=self._svg_row_h)
        self.svg_combo = ComboBox(self.c_svg, app, bg="card", command=lambda i: self._set_svg_mode(ex.SVG_MODES[i]))
        self.svg_line_box = TextBox(self.c_svg, app, self._svg_line_text(), width=0, fit="12,34", bg="card",
                                    on_apply=self._apply_svg_line, allow=_line_allowed)
        # remark 50 (mockup /workspace/rewrite/mockup_r50): «Толщина DXF» — field «Толщина линии» in mm,
        # the default of the DXF card on screen 3; the number is left-aligned as in «Поле рамки при обрезке»
        self.c_dxf = SCard(inner, self, "svg_thickness", lambda: t("settings.dxf_line"), lambda: t("settings.dxf_line.desc"))
        self.dxf_line_box = TextBox(self.c_dxf, app, self._dxf_line_text(), width=0, fit="12,34", bg="card",
                                    on_apply=self._apply_dxf_line, allow=_line_allowed)
        self.c_sizes = SCard(inner, self, "size", lambda: t("settings.sizes"), None, summary=self._size_summary,
                             expandable=True, body_h=self._sizes_body_h)
        self.size_more: List[IconButton] = []     # «…» per row (36, 52)
        self.btn_add_size = Button(self.c_sizes, t("settings.add_size"), icon="add", bg="card",
                                   command=self._add_size)
        self.c_margin = SCard(inner, self, "margin", lambda: t("settings.margin"), lambda: t("settings.margin.desc"))
        self.margin_box = TextBox(self.c_margin, app, self._margin_text(), width=0, fit="12,34", bg="card",
                                  on_apply=self._apply_margin, allow=_margin_allowed)
        # remark 47 (mockup /workspace/rewrite/mockup_colors): an expander like «Размеры подписи» — collapsed:
        # swatch + name of the default colour; open: a row per colour with «…», the «По умолчанию» badge and
        # «Добавить цвет» at the bottom
        self.c_color = SCard(inner, self, "drop", lambda: t("settings.color_default"),
                             lambda: t("settings.color_default.desc"), summary=self._color_summary,
                             expandable=True, body_h=self._colors_body_h)
        self.color_more: List[IconButton] = []
        self.btn_add_color = Button(self.c_color, t("settings.add_color"), icon="add", bg="card",
                                    command=self._add_color)
        self.c_dpi = SCard(inner, self, "image_dpi", lambda: t("settings.png_resolution"),
                           lambda: t("settings.png_resolution.desc"))
        self.dpi_combo = ComboBox(self.c_dpi, app, bg="card", width=DPI_COMBO_MIN, command=self._set_dpi)
        # ------------------------------------------------ Saving («Сохранение»)
        self.c_folder = SCard(inner, self, "folder_set", lambda: t("settings.folder"), lambda: str(self._folder()))
        self.btn_change = Button(self.c_folder, t("common.change_ellipsis"), bg="card", command=self._change_folder)
        self.btn_open = Button(self.c_folder, t("common.open_folder"), bg="card",
                               command=lambda: app.open_folder(self._folder()))
        self.c_name = SCard(inner, self, "filename", lambda: t("settings.name_template"),
                            lambda: t("settings.name_template.desc"))
        self.name_box = TextBox(self.c_name, app, self._name_template(), width=180, bg="card",
                                on_apply=self._apply_name)
        self.c_exists = SCard(inner, self, "conflict", lambda: t("settings.if_exists"), lambda: t("settings.if_exists.desc"))
        self.exists_combo = ComboBox(self.c_exists, app, bg="card", command=self._set_exists)
        # ------------------------------------------------ About («Сведения»)
        self.c_about = SCard(inner, self, None, lambda: t("app.name"), lambda: t("app.description"),
                             summary=lambda: t("settings.version", version=app.VERSION_STR), expandable=True, open_=True, body_h=lambda: 267, logo=True)
        self.about_links = [
            (Link(self.c_about, "", 13.5, "link", bg="card", command=lambda: app.open_url(f"{REPO_URL}/releases/tag/{RELEASE_TAG}")),
             "settings.release_notes"),
            (Link(self.c_about, "", 13.5, "link", bg="card", command=lambda: app.open_url(f"{REPO_URL}/releases")),
             "settings.all_releases"),
            (Link(self.c_about, "", 13.5, "link", bg="card", command=app.report_issue),
             "settings.report_issue"),
            (Link(self.c_about, "", 13.5, "link", bg="card", command=lambda: app.open_url(REPO_URL)),
             "settings.source_code"),
        ]
        self.license_link = Link(self.c_about, "GNU GPLv3", 13.5, "link", bg="card",
                                 command=lambda: app.open_url(LICENSE_URL))
        self.about_body = _AboutText(self.c_about, app)
        self.c_upd = SCard(inner, self, "update", lambda: t("settings.check_updates"),
                           lambda: self.update_note)
        self.btn_check = Button(self.c_upd, t("settings.check_now"), bg="card", command=self._check_now)
        self.upd_toggle = Toggle(self.c_upd, bool(s.get("check_updates")), bg="card", label_fn=self._onoff,
                                 command=lambda v: s.set("check_updates", v))
        # ------------------------------------------------ Reset («Сброс», remark 37)
        self.c_reset = SCard(inner, self, "reset", lambda: t("settings.reset.title"))
        self.btn_reset = Button(self.c_reset, t("settings.reset.button"), kind="danger", bg="card",
                                command=self._confirm_reset)

        self.groups = [
            ("settings.appearance", [self.c_theme, self.c_lang]),
            # remark 51: common cards first, then by format as on screen 3
            ("shell.step.export", [self.c_formats, self.c_sizes, self.c_margin, self.c_color, self.c_dpi, self.c_svg,
                                   self.c_dxf]),
            ("settings.save", [self.c_folder, self.c_name, self.c_exists]),
            ("settings.about", [self.c_about, self.c_upd]),
            ("settings.reset", [self.c_reset]),
        ]
        for key, _ in self.groups:
            self.headers[key] = _Header(inner, app, key)

    # ------------------------------------------------------------------ texts
    def _onoff(self, v):
        return self.app.t("common.on" if v else "common.off")

    def _size_options(self):
        """[(key, label, saved size or None)]: «Как в исходнике», «15 × 5 мм», then the user's sizes (36)."""
        t = self.app.t
        opts = [(ex.SIZE_ORIGINAL, t("export.size.as_original"), None), (ex.SIZE_15X5, t("export.size.preset_15x5"), None)]
        for sz in SZ.custom_sizes(self.app):
            opts.append((ex.TEMPLATE_PREFIX + str(sz.get("id")), SZ.size_label(self.app, sz), sz))
        return opts

    def _size_summary(self):
        cur = self.app.settings.get("default_size", ex.SIZE_15X5)
        for k, label, _ in self._size_options():
            if k == cur:
                return label
        return self.app.t("export.size.preset_15x5")

    def _sizes_body_h(self):
        # 4 top + rows 40 + 11 + «Добавить размер» 32 + 19 (36: four rows → 226)
        return 4 + SIZE_ROW_H * len(self._size_options()) + 11 + SIZE_BTN_H + 19

    def _svg_mode(self) -> str:
        return ex.clamp_svg_mode(self.app.settings.get("svg_mode", ex.DEFAULT_SVG_MODE))

    def _svg_row_h(self) -> float:
        return SVG_LINE_ROW_H if self._svg_mode() == "stroke" else 0

    def _svg_line_text(self):
        v = ex.resolve_svg_line(None, self.app.settings.get("svg_line_mm"))
        return ex.format_plain_number(v, self.app.i18n.lang)

    def _dxf_line_text(self):
        v = ex.resolve_dxf_line(None, self.app.settings.get("dxf_line_mm"))
        return ex.format_plain_number(v, self.app.i18n.lang)

    def _margin_text(self):
        v = float(self.app.settings.get("crop_margin_mm", ex.DEFAULT_MARGIN_MM))
        return ex.format_plain_number(v, self.app.i18n.lang)

    def _folder(self) -> Path:
        return self.app.settings.save_folder(self.app.t("export.default_folder"))

    def _name_template(self) -> str:
        return self.app.settings.name_template(self.app.t("settings.name_template.value"))

    def _color_items(self):
        """[(key, name, hex | None, is_custom)] — «Как на фото», built-in colours, own colours (47)."""
        return color_items(self.app)

    def _default_color(self) -> str:
        key = self.app.settings.get("default_color", ex.DEFAULT_COLOR_KEY)
        return key if any(k == key for k, *_ in self._color_items()) else ex.DEFAULT_COLOR_KEY

    def _color_summary(self):
        return color_name(self.app, self._default_color())

    def _colors_body_h(self):
        return 2 + COLOR_ROW_H * len(self._color_items()) + 8 + SIZE_BTN_H + 15

    # ------------------------------------------------------------------ actions
    def _set_theme(self, v):
        self.app.set_theme_pref(v)
        self.sync()

    def _set_lang(self, i):
        self.app.set_language_pref(("system", "ru", "en")[i])
        self.sync()

    def _toggle_format(self, code, on):
        cur = [c for c in ex.ALL_FORMATS if c in (self.app.settings.get("default_formats") or [])]
        if on and code not in cur:
            cur.append(code)
        if not on:
            if len(cur) <= 1:  # at least one format stays on
                self.fmt_rows[code][0].set(True)
                return
            cur.remove(code)
        self.app.settings.set_export_default("default_formats", [c for c in ex.ALL_FORMATS if c in cur])
        self.c_formats.redraw()

    def _set_svg_mode(self, mode):
        self.app.settings.set_export_default("svg_mode", ex.clamp_svg_mode(mode))
        self.svg_combo.set_index(ex.SVG_MODES.index(self._svg_mode()))
        self.layout_content()      # the «Толщина линии» row appears / disappears

    def _apply_svg_line(self, text):
        v = ex.parse_number(text)
        if v is None or not (ex.DXF_LINE_RANGE[0] <= v <= ex.DXF_LINE_RANGE[1]):
            return False
        self.app.settings.set_export_default("svg_line_mm", round(v, 2))
        self.svg_line_box.set(self._svg_line_text())
        return True

    def _apply_dxf_line(self, text):
        v = ex.parse_number(text)
        if v is None or not (ex.DXF_LINE_RANGE[0] <= v <= ex.DXF_LINE_RANGE[1]):
            return False
        self.app.settings.set_export_default("dxf_line_mm", round(v, 2))
        self.dxf_line_box.set(self._dxf_line_text())
        return True

    def _set_size(self, key):
        SZ.set_default_size(self.app, key)
        self.sync()

    def _size_menu(self, i):
        """«…» of a size row: built-in sizes only «Сделать по умолчанию» (52), own sizes also «Изменить»
        and «Удалить» (36).  «Сделать по умолчанию» is inactive for the current default."""
        opts = self._size_options()
        if not (0 <= i < len(opts)):
            return
        key, _label, sz = opts[i]
        t = self.app.t
        is_default = key == self.app.settings.get("default_size", ex.SIZE_15X5)
        items = [MenuItem(t("common.set_default"), lambda: self._set_size(key), disabled=is_default)]
        if sz is not None:
            items += [MenuItem(t("common.edit"), lambda: self._edit_size(sz)), None,
                      MenuItem(t("common.delete"), lambda: self._delete_size(sz))]
        x, y, w, h = widget_rect(self.app.root, self.size_more[i])
        MenuPopup(self.app, items, x - 4, y + h - 2, align_right=True, min_width=160)

    def _add_size(self):
        SizeDialog(self.app, None, lambda key: self.sync())

    def _edit_size(self, sz):
        SizeDialog(self.app, sz, lambda key: self.sync())

    def _delete_size(self, sz):
        confirm_delete_size(self.app, sz, self.sync)

    def _color_menu(self, i):
        """Remark 47: «…» of a colour row — built-in colours only «Сделать по умолчанию» (inactive for the
        default); own colours also «Изменить» (dialog 10 with the colour and name), a divider, «Удалить»."""
        items = self._color_items()
        if not (0 <= i < len(items)):
            return
        key, _name, _hx, custom = items[i]
        t = self.app.t
        menu = [MenuItem(t("common.set_default"), lambda: self._set_color_key(key), disabled=key == self._default_color())]
        if custom:
            menu += [MenuItem(t("common.edit"), lambda: self._edit_color(key)), None,
                     MenuItem(t("common.delete"), lambda: self._delete_color(key))]
        x, y, w, h = widget_rect(self.app.root, self.color_more[i])
        MenuPopup(self.app, menu, x - 4, y + h - 2, align_right=True, min_width=160)

    def _set_color_key(self, key):
        set_default_color(self.app, key)
        self.sync()

    def _add_color(self):
        CustomColorDialog(self.app, None, lambda name, hx: (add_color(self.app, name, hx), self.sync()))

    def _edit_color(self, key):
        c = find_custom(self.app, key)
        if c is None:
            return
        CustomColorDialog(self.app, None, lambda name, hx: (edit_color(self.app, key, name, hx), self.sync()),
                          edit=c)

    def _delete_color(self, key):
        return confirm_delete_color(self.app, key, self.sync)

    def _apply_margin(self, text):
        v = ex.parse_number(text)
        if v is None or not (0 <= v <= 20):
            return False
        self.app.settings.set("crop_margin_mm", round(v, 1))
        self.margin_box.set(self._margin_text())
        return True

    def _set_dpi(self, i):
        self.app.settings.set_export_default("png_resolution", ex.DPI_CHOICES[i])

    def _change_folder(self):
        path = filedialog.askdirectory(parent=self.app.root, initialdir=str(self._folder()),
                                       title=self.app.t("settings.folder"))
        if path:
            self.app.settings.set("save_folder", str(Path(path)))
            self.c_folder.redraw()
            self.layout_content()

    def _apply_name(self, text):
        text = text.strip()
        if not text or re.search(r'[<>:"/\\|?*]', text):
            return False
        default = self.app.t("settings.name_template.value")
        self.app.settings.set("name_template", None if text == default else text)
        return True

    def _set_exists(self, i):
        self.app.settings.set("if_exists", ("add_number", "replace", "ask")[i])

    def _confirm_reset(self):
        """Remark 37: «Сбросить настройки?» like «О программе» — red «Сбросить» + «Отмена», Esc = «Отмена»."""
        t = self.app.t
        ContentDialog(self.app, t("dialog.reset.title"), t("dialog.reset.body"),
                      [(t("settings.reset.button"), "danger", self.app.reset_settings),
                       (t("common.cancel"), "secondary", None)], width=420, esc_index=1)

    def _check_now(self):
        """«Проверить сейчас» (stage 5): a new version → dialog 32; otherwise a grey line under «Проверять
        обновления при запуске» that stays until «Параметры» are closed."""
        self.app.check_for_updates(manual=True)

    def set_update_note(self, text: str):
        self.update_note = text or ""
        self.layout_content()

    # ------------------------------------------------------------------ state
    def on_show(self):
        self.sync()
        self.area.scroll_to(0)
        self.area.bind_wheel()

    def hide(self):
        super().hide()
        self.area.hide()

    def sync(self):
        s, t = self.app.settings, self.app.t
        theme = s.get("theme", "system")
        for r, v in zip(self.theme_radios, THEME_ORDER, strict=True):
            key = f"settings.theme.{v}"
            r.label = t(key)
            r.set(theme == v)
            r.redraw()
        self.lang_combo.set_items([t("settings.language.system"), t("settings.language.ru"), t("settings.language.en")],
                                  ("system", "ru", "en").index(s.get("language", "system")))
        fm = s.get("default_formats") or []
        for code, (row, key) in self.fmt_rows.items():
            row.desc = t(key)
            row.set(code in fm)
            row.redraw()
        self.svg_combo.set_items([t(f"export.svg.mode.{m}") for m in ex.SVG_MODES],
                                 ex.SVG_MODES.index(self._svg_mode()))
        self.svg_line_box.set(self._svg_line_text())
        self.dxf_line_box.set(self._dxf_line_text())
        opts = self._size_options()
        while len(self.size_more) < len(opts):
            i = len(self.size_more)
            self.size_more.append(IconButton(self.c_sizes, "more", 16, bg="card", command=lambda i=i: self._size_menu(i)))
        self.btn_add_size.set_text(t("settings.add_size"))
        self.margin_box.set(self._margin_text())
        while len(self.color_more) < len(self._color_items()):
            i = len(self.color_more)
            self.color_more.append(IconButton(self.c_color, "more", 16, bg="card", command=lambda i=i: self._color_menu(i)))
        self.btn_add_color.set_text(t("settings.add_color"))
        dpi = s.get("png_resolution", ex.DEFAULT_PNG_DPI)
        if dpi not in ex.DPI_CHOICES:
            dpi = ex.DEFAULT_PNG_DPI
        self.dpi_combo.set_items([t("export.dpi_value", n=d) for d in ex.DPI_CHOICES], ex.DPI_CHOICES.index(dpi))
        self.name_box.set(self._name_template())
        self.exists_combo.set_items([t("settings.if_exists.add_number"), t("common.replace"),
                                     t("settings.if_exists.ask")],
                                    ("add_number", "replace", "ask").index(s.get("if_exists", "ask")))
        self.btn_change.set_text(t("common.change_ellipsis"))
        self.btn_open.set_text(t("common.open_folder"))
        self.btn_check.set_text(t("settings.check_now"))
        self.btn_reset.set_text(t("settings.reset.button"))
        self.upd_toggle.set(bool(s.get("check_updates")))
        for link, key in self.about_links:
            link.set_text(t(key))
        self.layout_content()

    # ------------------------------------------------------------------ layout
    def column(self, w=None):
        """(left, width) of the cards: 56 px sides, at most 1000 px wide and centred (2k_27)."""
        w = self.lw if w is None else w
        cw = min(w - 112, PAGE_MAX_W)
        return round((w - cw) / 2, 1), cw

    def layout(self, w, h):
        self.geom(0, 0, w, h)
        x0, _ = self.column(w)
        self.back.geom(x0 - 53, 22, 36, 36)
        self.redraw()
        self.layout_content()

    def draw(self):
        self.text(self.column()[0], 40, self.app.t("menu.settings"), 20, "semibold")

    def layout_content(self):
        if self.lw <= 0:
            return
        w = self.lw
        x0, cw = self.column(w)
        y = 0.0
        for gi, (key, cards) in enumerate(self.groups):
            if gi:
                y += GROUP_GAP
            self.headers[key].geom(x0, y, cw, 20)
            y += 28
            for ci, c in enumerate(cards):
                if ci:
                    y += GAP
                if c is self.c_name:   # remark 44: the long caption wraps on a narrow window
                    c.desc_room = cw - 51 - 17 - self.name_box.natural_width() - 12 - 12
                ch = c.height()
                c.geom(x0, y, cw, ch)
                c.redraw()
                self._layout_card(c, cw)
                y += ch
        content_h = y + 32
        self.area.geom(0, 80, w, self.lh - 80, content_h)

    def _right(self, card, widgets, cw):
        """Place header-row controls right to left (gap 12, right edge at cw − 17)."""
        x = cw - 17
        head = card.head_h() if hasattr(card, "head_h") else CARD_H
        for wd, ww, hh in widgets:
            x -= ww
            wd.geom(x, (head - hh) / 2, ww, hh)
            x -= 12

    def _layout_card(self, c, cw):
        if c is self.c_theme:
            for i, r in enumerate(self.theme_radios):
                if c.is_open:
                    r.geom(51, CARD_H + 6 + 34 * i, cw - 51 - 17, 34)
                else:
                    r.hide()
        elif c is self.c_lang:
            self._right(c, [(self.lang_combo, self.lang_combo.natural_width(), 32)], cw)
        elif c is self.c_formats:
            for i, (code, (row, _)) in enumerate(self.fmt_rows.items()):
                if c.is_open:
                    row.geom(51, CARD_H + 49 * i + 7 - 1 + 1, cw - 51 - 17, 35)
                else:
                    row.hide()
            c.extra_draw = self._draw_format_dividers
            c.redraw()
        elif c is self.c_svg:
            self._right(c, [(self.svg_combo, self.svg_combo.natural_width(), 32)], cw)
            if self._svg_mode() == "stroke":
                bw = self.svg_line_box.natural_width()
                self.svg_line_box.geom(cw - 17 - bw, CARD_H + (SVG_LINE_ROW_H - 32) / 2, bw, 32)
            else:
                self.svg_line_box.hide()
            c.extra_draw = self._draw_svg_line_row
            c.redraw()
        elif c is self.c_sizes:
            n = len(self._size_options())
            for i, b in enumerate(self.size_more):
                if c.is_open and i < n:
                    b.geom(cw - 38, CARD_H + 4 + SIZE_ROW_H * i + (SIZE_ROW_H - 28) / 2, 28, 28)
                else:
                    b.hide()
            if c.is_open:
                bw = self.btn_add_size.natural_width()
                self.btn_add_size.geom(51, CARD_H + 4 + SIZE_ROW_H * n + 11, bw, SIZE_BTN_H)
            else:
                self.btn_add_size.hide()
            c.extra_draw = self._draw_size_rows
            c.redraw()
        elif c is self.c_dxf:
            self._right(c, [(self.dxf_line_box, self.dxf_line_box.natural_width(), 32)], cw)
        elif c is self.c_margin:
            self._right(c, [(self.margin_box, self.margin_box.natural_width(), 32)], cw)
        elif c is self.c_color:
            n = len(self._color_items())
            for i, b in enumerate(self.color_more):
                if c.is_open and i < n:
                    b.geom(cw - 38, CARD_H + 2 + COLOR_ROW_H * i + (COLOR_ROW_H - 28) / 2, 28, 28)
                else:
                    b.hide()
            if c.is_open:
                bw = self.btn_add_color.natural_width()
                self.btn_add_color.geom(51, CARD_H + 2 + COLOR_ROW_H * n + 8, bw, SIZE_BTN_H)
            else:
                self.btn_add_color.hide()
            c.extra_draw = self._draw_color_rows
            c.redraw()
        elif c is self.c_dpi:
            self._right(c, [(self.dpi_combo, self.dpi_combo.natural_width(), 32)], cw)
        elif c is self.c_folder:
            self._right(c, [(self.btn_open, self.btn_open.natural_width(), 32),
                            (self.btn_change, self.btn_change.natural_width(), 32)], cw)
        elif c is self.c_name:
            self._right(c, [(self.name_box, self.name_box.natural_width(), 32)], cw)
        elif c is self.c_exists:
            self._right(c, [(self.exists_combo, self.exists_combo.natural_width(), 32)], cw)
        elif c is self.c_about:
            if c.is_open:
                top = CARD_H - 1 + 1 + 8
                self.about_body.geom(63, top, cw - 63 - 17, 36)
                y = top + 36 + 2
                for link, _ in self.about_links:
                    link.geom(63, y, link.natural_width(), 40)
                    y += 42
                lab_w = text_width(self.app.t("settings.license"), 12.5)
                self.about_body.redraw()
                self.license_link.geom(63 + lab_w + 5.4, y, self.license_link.natural_width(), 40)
                self._lic_y = y
                c.extra_draw = self._draw_license_label
                c.redraw()
            else:
                self.about_body.hide()
                for link, _ in self.about_links:
                    link.hide()
                self.license_link.hide()
        elif c is self.c_reset:
            self._right(c, [(self.btn_reset, self.btn_reset.natural_width(), 32)], cw)
        elif c is self.c_upd:
            self._right(c, [(self.upd_toggle, self.upd_toggle.natural_width(), 20),
                            (self.btn_check, self.btn_check.natural_width(), 32)], cw)

    # Items drawn on the card canvas itself go through SCard.extra_draw: the card clears its
    # canvas on every hover redraw, so anything drawn from outside (the «Лицензия» label,
    # the format dividers) used to vanish when the mouse moved over the card.
    def _draw_size_rows(self, c):
        """36: size names at x 51, the grey «По умолчанию» badge left of «…» on the default size."""
        if not c.is_open:
            return
        cur = self.app.settings.get("default_size", ex.SIZE_15X5)
        room = c.lw - 51 - 46 - 12
        badge = self.app.t("common.default_badge")
        for i, (k, label, _sz) in enumerate(self._size_options()):
            cy = CARD_H + 4 + SIZE_ROW_H * i + SIZE_ROW_H / 2
            r = room - (text_width(badge, 12) + 12 if k == cur else 0)
            c.text(51, cy, elide(label, r, 14), 14, color="text_card")
            if k == cur:
                c.text(c.lw - 46, cy, badge, 12, color="muted", anchor="e")

    def _draw_color_rows(self, c):
        """47: the swatch left of the collapsed value; open — rows «swatch · name», badge left of «…»."""
        items = self._color_items()
        cur = self._default_color()
        hx_cur = next((hx for k, _n, hx, _c in items if k == cur), None)
        x = c.lw - 17 - 16 - 12 - text_width(self._color_summary(), 14) - 8 - 14
        self._draw_swatch(c, x, CARD_H / 2 - 7, hx_cur)
        if not c.is_open:
            return
        room = c.lw - 74 - 46 - 12
        badge = self.app.t("common.default_badge")
        for i, (k, name, hx, _custom) in enumerate(items):
            cy = CARD_H + 2 + COLOR_ROW_H * i + COLOR_ROW_H / 2
            self._draw_swatch(c, 51, cy - 7, hx)
            r = room - (text_width(badge, 12) + 12 if k == cur else 0)
            c.text(74, cy, elide(name, r, 14), 14, color="text_card")
            if k == cur:
                c.text(c.lw - 46, cy, badge, 12, color="muted", anchor="e")

    @staticmethod
    def _draw_swatch(c, x, y, hx):
        if hx:
            c.rrect(x, y, 14, 14, 3, hx, "swatch_stroke")
        else:   # «Как на фото»
            c.icon("pipette", x, y, 14, "text_card")

    def _draw_license_label(self, c):
        if c.is_open:
            c.text(63, self._lic_y + 20, self.app.t("settings.license"), 12.5, color="muted")

    def _draw_format_dividers(self, c):
        if c.is_open:
            for i in range(1, 3):
                yy = CARD_H - 1 + 49 * i
                c.create_rectangle(S(1), S(yy), S(c.lw - 1), S(yy + 1), fill=Theme.c("divider"), width=0)

    def _draw_svg_line_row(self, c):
        """Remark 32, variant B: «Толщина линии» row under the «Толщина SVG» header (only «Заданная толщина»)."""
        if self._svg_mode() != "stroke":
            return
        t = self.app.t
        y0 = CARD_H - 1
        c.create_rectangle(S(1), S(y0), S(c.lw - 1), S(y0 + 1), fill=Theme.c("divider"), width=0)
        room = c.lw - 51 - 17 - self.svg_line_box.natural_width() - 12
        c.text(51, y0 + 1 + SVG_LINE_ROW_H / 2 - 8, t("export.svg.line"), 14, color="text_card")
        c.text(51, y0 + 1 + SVG_LINE_ROW_H / 2 + 9, elide(t("export.svg.line.desc"), room, 12), 12, color="muted")

    def refresh(self):
        super().refresh()
        self.area.refresh_bg()
        if self.visible:
            self.sync()


class _Header(Box):
    def __init__(self, master, app, key):
        super().__init__(master, bg="bg")
        self.app, self.key = app, key

    def draw(self):
        self.text(0, 10, self.app.t(self.key), 14, "semibold")


class _AboutText(Box):
    """© line (36 high, 12.5 px muted)."""

    def __init__(self, master, app):
        super().__init__(master, bg="card")
        self.app = app

    def draw(self):
        self.text(0, 18, "© 2026 Stanislau Salavei", 12.5, color="muted")


def _line_allowed(text: str) -> bool:
    """Line thickness: up to 5 mm with two decimals (0,18) — same as the SVG / DXF cards on screen 3."""
    return re.fullmatch(r"\d?([.,]\d{0,2})?", text) is not None


def _margin_allowed(text: str) -> bool:
    return re.fullmatch(r"\d{0,2}([.,]\d?)?", text) is not None


