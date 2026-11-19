"""Remarks 32–36 (2026-11-17): «Толщина SVG» card, TextBox ×/✓ and widths, «Удалить шаблон»,
dropdown widths, PNG DPI 300/600/1200 and no upscaling in «Как в исходнике».

UI tests run the real app under an X display (skipped without one)."""
import csv
import importlib
import io
import json
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core import export as ex
from tests.i18n_prompt_diff import assert_matches_prompt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "i18n" / "strings_ru_en.csv"
from tests.i18n_prompt_diff import PROMPT_CSV  # noqa: E402  (remark 91: copy in docs/prompt_v2)


def rows():
    return {r[0]: r for r in csv.reader(CSV.open(encoding="utf-8-sig", newline=""))}


# ================================================================== i18n
def test_i18n_rows_added():
    r = rows()
    assert r["settings.svg_mode.desc"][2:4] == ["Толщина линий в SVG-файле", "Line thickness in the SVG file"]
    assert r["export.size.delete_template"][2:4] == ["Удалить шаблон", "Delete template"]
    keys = list(r)
    assert keys.index("settings.svg_mode.desc") == keys.index("settings.svg_mode") + 1
    assert keys.index("export.size.delete_template") == keys.index("export.size.save_template") + 1


def test_i18n_png_res_help_lists_new_dpi():
    r = rows()
    ru, en = r["help.formats.png_res"][2:4]
    for txt in (ru, en):
        assert "300" in txt and "600" in txt and "1200" in txt and "150" not in txt
    assert "«Как в исходнике»" in ru and "As in original" in en


@pytest.mark.skipif(not PROMPT_CSV.exists(), reason="prompt table not on this machine")
def test_i18n_csv_identical_to_prompt():
    assert_matches_prompt(CSV, PROMPT_CSV)     # remarks 77–85: approved differences only


# ================================================================== 36: DPI
def test_dpi_choices_and_default():
    assert ex.DPI_CHOICES == (300, 600, 1200)
    assert ex.DEFAULT_PNG_DPI == 1200


def _src(w=400, h=100, dpi=300.0, has_dpi=True):
    m = np.zeros((h, w), dtype=bool)
    m[10:h - 10, 10:w - 10] = True
    return ex.ExportSource(m, dpi, has_dpi)


def test_effective_dpi_caps_only_as_source():
    s = _src(dpi=300.0)
    orig = ex.SizeChoice.original()
    box = ex.size_choice_for_key(ex.SIZE_15X5, [])
    assert ex.effective_png_dpi(s, orig, 1200) == 300
    assert ex.effective_png_dpi(s, orig, 300) == 300
    assert ex.effective_png_dpi(_src(dpi=720.0), orig, 600) == 600
    assert ex.effective_png_dpi(_src(dpi=720.0), orig, 1200) == 720
    assert ex.effective_png_dpi(s, box, 1200) == 1200          # box sizes keep the chosen DPI
    assert ex.dpi_label(287.4) == 287


def test_as_source_png_never_upscaled_and_dpi_metadata():
    s = _src(w=400, h=100, dpi=300.0)
    job = ex.ExportJob(s, ex.SizeChoice.original(), 0.0, (0, 0, 0), 1200, ("PNG",))
    data = ex.build_outputs(job)["PNG"]
    im = Image.open(io.BytesIO(data))
    assert im.size == (400, 100)                                 # = crop pixels, not 4× upscaled
    assert round(im.info["dpi"][0]) == 300
    geom = ex.compute_geometry(400, 100, 300.0, ex.SizeChoice.original(), 0.0)
    assert abs(geom.file_w_mm - 400 / 300 * 25.4) < 1e-9          # mm unchanged


def test_box_png_keeps_chosen_dpi():
    s = _src(w=400, h=100, dpi=300.0)
    job = ex.ExportJob(s, ex.size_choice_for_key(ex.SIZE_15X5, []), 0.5, (0, 0, 0), 1200, ("PNG",))
    im = Image.open(io.BytesIO(ex.build_outputs(job)["PNG"]))
    assert im.size == (ex.mm_to_px(15, 1200), ex.mm_to_px(5, 1200)) and round(im.info["dpi"][0]) == 1200


@pytest.fixture
def settings_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import core.settings as mod
    return importlib.reload(mod)


def _write(tmp_path, data):
    d = tmp_path / "Signature Extractor"
    d.mkdir(exist_ok=True)
    (d / "settings.json").write_text(json.dumps(data), encoding="utf-8")
    return d / "settings.json"


@pytest.mark.parametrize("saved,expected", [(150, 300), (600, 600), (300, 300), (1200, 1200)])
def test_png_dpi_migration_v2(settings_mod, tmp_path, saved, expected):
    f = _write(tmp_path, {"png_resolution": saved, "settings_version": 2,
                          "last_export": {"png_dpi": 150, "formats": ["PNG"]}})
    s = settings_mod.SettingsManager([])
    assert s.get("png_resolution") == expected
    assert s.get("last_export") == {"png_dpi": 300, "formats": ["PNG"]}
    assert json.loads(f.read_text(encoding="utf-8"))["settings_version"] == 3


@pytest.mark.parametrize("ver", [None, 1, 2])
def test_saved_600_is_kept_and_used_on_export(settings_mod, tmp_path, ver):
    """User decision 2026-11-17: 600 DPI set in Settings stays 600 and is the export default."""
    data = {"png_resolution": 600}
    if ver is not None:
        data["settings_version"] = ver
    _write(tmp_path, data)
    s = settings_mod.SettingsManager([])
    assert s.get("png_resolution") == 600
    last = s.get("last_export") or {}
    dpi = int(last.get("png_dpi") or s.get("png_resolution", ex.DEFAULT_PNG_DPI))   # as ExportPage.on_show
    assert (dpi if dpi in ex.DPI_CHOICES else ex.DEFAULT_PNG_DPI) == 600
    assert not hasattr(settings_mod, "OLD_PNG_DPI_DEFAULT")


def test_missing_dpi_gets_default_1200(settings_mod, tmp_path):
    _write(tmp_path, {"theme": "dark", "settings_version": 2})
    assert settings_mod.SettingsManager([]).get("png_resolution") == 1200


def test_png_dpi_migration_runs_once(settings_mod, tmp_path):
    _write(tmp_path, {"png_resolution": 600, "settings_version": 3})
    assert settings_mod.SettingsManager([]).get("png_resolution") == 600     # v3: 600 is the user's choice
    _write(tmp_path, {"png_resolution": 150, "settings_version": 3})
    assert settings_mod.SettingsManager([]).get("png_resolution") == 1200    # invalid now → default


def test_new_install_default_1200(settings_mod):
    assert settings_mod.SettingsManager([]).get("png_resolution") == 1200


def test_export_page_uses_effective_dpi_everywhere():
    src = "".join(p.read_text(encoding="utf-8") for p in [ROOT / "ui" / "pages" / "export_page.py", *sorted((ROOT / "ui" / "pages" / "export").glob("*.py"))])   # remark 112: screen 3 in parts
    assert "png_eff_dpi()" in src[src.index("    def tag_text"):src.index("    def schedule_preview")]
    assert "dpi=ex.dpi_label(eff)" in src and '["300", "600", "1200 DPI"]' in src
    assert "self.png_dpi)" not in src[src.index("    def _png_key"):src.index("    def png_ready")]


# ================================================================== 32: SVG thickness default
def test_resolve_svg_line():
    assert ex.resolve_svg_line({}, 0.35) == 0.35
    assert ex.resolve_svg_line({"svg_line_mm": 0.5}, 0.35) == 0.5
    assert ex.resolve_svg_line(None, None) == ex.DEFAULT_SVG_LINE_MM
    assert ex.resolve_svg_line({"svg_line_mm": 99}, "x") == ex.DEFAULT_SVG_LINE_MM


def test_settings_svg_line_resets_remembered(settings_mod):
    s = settings_mod.SettingsManager([])
    s.set("last_export", {"svg_line_mm": 0.5, "svg_mode": "stroke"})
    s.set_export_default("svg_line_mm", 0.35)
    assert s.get("svg_line_mm") == 0.35 and s.get("last_export") == {"svg_mode": "stroke"}


def test_svg_thickness_icon_is_fluent_glyph():
    im = Image.open(ROOT / "assets" / "icons" / "svg_thickness.png")
    assert im.size == (96, 96) and im.mode == "RGBA" and im.getchannel("A").getbbox()


# ================================================================== UI (real app under X)
@pytest.fixture(scope="module")
def app(tmp_path_factory):
    if not os.environ.get("DISPLAY"):
        pytest.skip("no X display")
    tmp = tmp_path_factory.mktemp("appdata")
    old = {k: os.environ.get(k) for k in ("APPDATA", "USERPROFILE", "LANG")}
    os.environ["APPDATA"] = str(tmp)
    os.environ["USERPROFILE"] = str(tmp)
    os.environ["LANG"] = "ru_RU.UTF-8"
    (tmp / "Signature Extractor").mkdir()
    (tmp / "Signature Extractor" / "settings.json").write_text(json.dumps({"theme": "light", "language": "ru"}))
    import core.settings
    importlib.reload(core.settings)
    from ui import app as A
    a = A.App([])
    a.root.geometry("1024x768+0+0")
    a.root.update()
    from ui.pages.export_page import ExportPage
    a.export_page = ExportPage(a.root, a)      # created as on screen 3 (not shown)
    a.open_settings()
    pump(a, 300)
    yield a
    from ui.widgets.overlay import Popup
    Popup.close_current()
    a.root.destroy()
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def pump(app, ms=50):
    import time
    end = time.time() + ms / 1000
    while time.time() < end:
        app.root.update()
        time.sleep(0.01)


def _textbox(app, text="", placeholder=""):
    from ui.widgets.controls import TextBox
    tb = TextBox(app.root, app, text, width=0, fit="12,34", bg="bg", placeholder=placeholder)
    tb.geom(300, 300, tb.natural_width(), 32)
    tb.lift()
    pump(app, 80)
    return tb


def _focus(app, tb):
    tb.entry.focus_force()
    pump(app, 80)
    assert tb.focus_get() is tb.entry


# ---------------------------------------------------------------- 33: TextBox
def test_clear_press_keeps_focus_and_x_visible(app):
    tb = _textbox(app, "0,18")
    try:
        _focus(app, tb)
        assert tb.clear_btn.winfo_ismapped()
        tb.clear_btn.event_generate("<ButtonPress-1>", x=12, y=12)
        pump(app, 50)
        assert tb.focus_get() is tb.entry                  # CTk «focus the clicked widget» stopped
        assert tb.clear_btn.winfo_ismapped() and tb.clear_btn.pressed
        tb.clear_btn.event_generate("<ButtonRelease-1>", x=12, y=12)
        pump(app, 50)
        assert tb.get() == "" and tb.focus_get() is tb.entry
    finally:
        tb.destroy()


def test_clear_press_leave_release_does_nothing(app):
    tb = _textbox(app, "0,18")
    try:
        _focus(app, tb)
        tb.clear_btn.event_generate("<ButtonPress-1>", x=12, y=12)
        pump(app, 30)
        tb.clear_btn.event_generate("<Leave>")
        pump(app, 30)
        tb.clear_btn.event_generate("<ButtonRelease-1>", x=60, y=12)   # released outside
        pump(app, 50)
        assert tb.get() == "0,18"                          # not cleared
        assert tb.focus_get() is tb.entry and tb.clear_btn.winfo_ismapped()   # «×» still there
        # and a normal click afterwards works
        tb.clear_btn.event_generate("<Enter>")
        tb.clear_btn.event_generate("<ButtonPress-1>", x=12, y=12)
        tb.clear_btn.event_generate("<ButtonRelease-1>", x=12, y=12)
        pump(app, 50)
        assert tb.get() == ""
    finally:
        tb.destroy()


def test_x_not_hidden_while_pressed_even_if_focus_leaves(app):
    tb = _textbox(app, "0,18")
    try:
        _focus(app, tb)
        tb.clear_btn.pressed = True
        tb._focus_out()
        assert tb.focused
        tb._update_clear()
        pump(app, 30)
        assert tb.clear_btn.winfo_ismapped()
        tb.clear_btn.pressed = False
    finally:
        tb.destroy()


def test_apply_press_keeps_focus(app):
    tb = _textbox(app, "0,18")
    got = []
    tb.on_apply = lambda t: got.append(t) or True
    try:
        _focus(app, tb)
        tb.apply_btn.event_generate("<ButtonPress-1>", x=10, y=10)
        pump(app, 30)
        assert tb.focus_get() is tb.entry
        tb.apply_btn.event_generate("<ButtonRelease-1>", x=10, y=10)
        pump(app, 30)
        assert got == ["0,18"] and tb.focus_get() is tb.entry
    finally:
        tb.destroy()


def test_click_on_padding_focuses_entry(app):
    tb = _textbox(app, "5")
    try:
        app.root.focus_force()
        pump(app, 50)
        tb.event_generate("<Button-1>", x=4, y=4)
        pump(app, 80)
        assert tb.focus_get() is tb.entry
    finally:
        tb.destroy()


def test_click_on_empty_placeholder_field_focuses_entry(app):
    tb = _textbox(app, "", placeholder="Например, Фиолетовый")
    try:
        app.root.focus_force()
        pump(app, 50)
        assert not tb.entry.winfo_ismapped()               # placeholder shown, entry parked
        tb.event_generate("<Button-1>", x=60, y=16)
        pump(app, 120)
        assert tb.focus_get() is tb.entry and tb.focused and tb.entry.winfo_ismapped()
    finally:
        tb.destroy()


def test_set_redraws_placeholder(app):
    tb = _textbox(app, "", placeholder="Например")
    try:
        app.root.focus_force()
        pump(app, 50)
        assert not tb.entry.winfo_ismapped()
        tb.set("abc")
        pump(app, 50)
        assert tb.entry.winfo_ismapped()
        tb.set("")
        pump(app, 50)
        assert not tb.entry.winfo_ismapped()
    finally:
        tb.destroy()


def test_number_fields_fit_value_with_x(app):
    from ui.theme import F, text_width
    from ui.widgets.controls import TextBox
    sp, ep = app.settings_page, app.export_page
    boxes = {"settings.margin": sp.margin_box, "settings.svg_line": sp.svg_line_box, "export.w": ep.c_size.w_box,
             "export.h": ep.c_size.h_box, "export.margin": ep.c_size.margin, "dxf.line": ep.c_dxf.line,
             "svg.line": ep.c_svg.line}
    for name, b in boxes.items():
        assert b.fit == "12,34", name
        assert b.box_w >= 11 + text_width("12,34", 14) + TextBox.CLEAR_AREA, name
        assert 76 <= b.box_w <= 86, (name, b.box_w)      # ~80 px
    # real entry room with «×» visible
    tb = _textbox(app, "12,34")
    try:
        _focus(app, tb)
        assert tb.clear_btn.winfo_ismapped()
        assert tb.entry.winfo_width() >= F(14).measure("12,34") + 1
        assert tb.entry.xview() == (0.0, 1.0)
    finally:
        tb.destroy()
    assert TextBox.CLEAR_AREA == 30


def test_rgb_fields_fit_255():
    pytest.importorskip("tkinter")
    src = (ROOT / "ui" / "dialogs" / "color_dialog.py").read_text(encoding="utf-8")
    assert 'fit="255"' in src and "def rgb_layout" in src


def test_rgb_layout(app):
    from ui.dialogs.color_dialog import CustomColorDialog
    from ui.theme import text_width
    w, xs, hex_w = CustomColorDialog.rgb_layout(None)
    assert w >= 11 + text_width("255", 13) + 30 and 64 <= w <= 72
    assert xs[2] + w == 398 and xs[1] - xs[0] == w + 8 and 20 + hex_w + 10 == xs[0]


def test_sizecard_x2_initialised_and_custom_row_fits(app):
    from ui.pages import export_page as EP
    ep = app.export_page
    assert hasattr(ep.c_size, "_x2")
    assert EP.CUSTOM_GAP == 16
    for lang in ("ru", "en"):
        app.set_language_pref(lang)
        ep.size_key = ex.SIZE_CUSTOM
        ep.c_size.layout(0, 0, EP.LEFT_W)
        right = ep.c_size.h_box.lx + ep.c_size.h_box.natural_width()
        assert right <= EP.LEFT_W - 17, (lang, right)
    app.set_language_pref("ru")
    ep.size_key = ex.SIZE_15X5


# ---------------------------------------------------------------- 32: settings card
def test_settings_svg_card(app):
    from ui.pages import settings_page as SP
    sp = app.settings_page
    groups = dict(sp.groups)
    exp = groups["shell.step.export"]
    assert exp.index(sp.c_svg) == exp.index(sp.c_dpi) + 1        # remark 51: by format, after «Разрешение PNG»
    assert sp.c_formats.body_h_fn() == SP.FMT_ROWS_H and not hasattr(sp, "svg_radios")
    sp._set_svg_mode("original")
    pump(app, 50)
    assert sp.c_svg.height() == SP.CARD_H and not sp.svg_line_box.winfo_ismapped()
    assert sp.svg_combo.items == ["Как в оригинале", "Заданная толщина"] and sp.svg_combo.index == 0
    app.settings.set("last_export", {"svg_line_mm": 0.5})
    sp._set_svg_mode("stroke")
    sp.area.scroll_to(sp.c_svg.ly - 100)
    pump(app, 80)
    assert app.settings.get("svg_mode") == "stroke"
    assert sp.c_svg.height() == SP.CARD_H + SP.SVG_LINE_ROW_H and sp.svg_line_box.winfo_ismapped()
    assert sp.svg_line_box.apply_btn is not None
    assert sp._apply_svg_line("0,35") is True
    assert app.settings.get("svg_line_mm") == 0.35 and "svg_line_mm" not in app.settings.get("last_export")
    assert sp._apply_svg_line("9,5") is False
    assert ex.resolve_svg_line(app.settings.get("last_export"), app.settings.get("svg_line_mm")) == 0.35
    sp._set_svg_mode("original")


def test_settings_dpi_combo_items(app):
    sp = app.settings_page
    sp.sync()
    assert sp.dpi_combo.items == ["300 DPI", "600 DPI", "1200 DPI"]
    assert sp.dpi_combo.items[sp.dpi_combo.index] == f"{app.settings.get('png_resolution')} DPI"


# ---------------------------------------------------------------- 34: «Удалить шаблон»
def test_delete_template_link_and_flow(app):
    from ui.pages import export_page as EP
    from ui.widgets.overlay import Popup
    ep = app.export_page
    app.settings.set("custom_sizes", [{"id": "1", "name": "Штамп КБ", "w_mm": 20, "h_mm": 8},
                                      {"id": "2", "name": "Визитка", "w_mm": 30, "h_mm": 10}])
    app.settings.set("default_size", "tpl:2")
    app.settings.set("last_export", {"size": "tpl:2"})
    ep.size_key = "tpl:2"
    ep.c_size.layout(0, 0, EP.LEFT_W)
    assert ep.c_size.mode == "template" and ep.selected_template()["name"] == "Визитка"
    assert ep.c_size.delete_link.label == "Удалить шаблон"
    assert ep.c_size.delete_link.color == ep.c_size.save_link.color      # same blue link
    ep.delete_template()
    pump(app, 50)
    dlg = Popup.current
    # stage 5 (mockup 51): the title names the size with its dimensions, the name kept on one line (NBSP)
    assert dlg is not None and dlg.title.replace("\xa0", " ") == "Удалить размер «Визитка · 30 × 10 мм»?"
    assert [b[0] for b in dlg.buttons_spec] == ["Удалить", "Отмена"]
    assert "".join(t for line in dlg.lines for t, _ in line).strip() == "По умолчанию станет 15 × 5 мм"
    dlg._activate(0)
    pump(app, 120)
    assert [s["id"] for s in app.settings.get("custom_sizes")] == ["1"]
    assert app.settings.get("default_size") == ex.SIZE_15X5 and ep.size_key == ex.SIZE_15X5
    assert "size" not in app.settings.get("last_export")
    ep.c_size.layout(0, 0, EP.LEFT_W)
    assert ep.c_size.mode == "none"
    # a non-default template: no extra line; «Отмена» keeps it
    ep.size_key = "tpl:1"
    ep.delete_template()
    pump(app, 50)
    dlg = Popup.current
    assert dlg.lines == [] and dlg.title.replace("\xa0", " ") == "Удалить размер «Штамп КБ · 20 × 8 мм»?"
    dlg._activate(1)
    pump(app, 80)
    assert len(app.settings.get("custom_sizes")) == 1 and ep.size_key == "tpl:1"
    ep.size_key = ex.SIZE_15X5
    for k in ("15x5", ex.SIZE_ORIGINAL, ex.SIZE_CUSTOM):
        ep.size_key = k
        assert ep.selected_template() is None
    ep.size_key = ex.SIZE_15X5


# ---------------------------------------------------------------- 35: dropdown widths
def _check_popup(app, combo, name):
    from ui.theme import text_width
    from ui.widgets.overlay import ListPopup, Popup
    combo.show_list()
    pump(app, 60)
    p = Popup.current
    try:
        assert isinstance(p, ListPopup), name
        W = app.width()
        labels = [l for l in combo.items if l]
        sw = {i: c for i in range(len(combo.items)) if combo.swatch_fn and (c := combo.swatch_fn(i))}
        need = ListPopup.needed_width(combo.items, sw, p.content_h > p.ph)
        assert p.pw >= combo.lw + 8 - 0.01, name
        assert p.pw <= W - 8 + 0.01, name
        assert p.pw >= min(need, W - 8) - 0.01, (name, p.pw, need)
        assert p.px >= 4 - 0.01 and p.px + p.pw <= W - 4 + 0.01, name
        for i, lab in enumerate(combo.items):
            if lab and p.pw >= need:
                assert text_width(lab, 14) <= p.text_room(i) + 0.01, (name, lab)
    finally:
        Popup.close_current()
        pump(app, 30)


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_all_dropdowns_fit(app, lang):
    from ui.theme import text_width
    app.set_language_pref(lang)
    app.settings.set("custom_colors", [{"id": "1", "name": "Очень длинное название своего цвета для проверки ширины",
                                        "hex": "#123456"}])
    app.settings.set("custom_sizes", [{"id": "7", "name": "Очень длинное название шаблона для штампа", "w_mm": 30,
                                       "h_mm": 10}])
    sp = app.settings_page
    sp.sync()
    pump(app, 50)
    for name in ("lang_combo", "svg_combo", "exists_combo", "dpi_combo"):   # remark 47: colour card is an expander
        combo = getattr(sp, name)
        nat = combo.natural_width()
        longest = max(combo.item_width(t, bool(combo.swatch_fn and combo.swatch_fn(i)))
                      for i, t in enumerate(combo.items) if t)
        if combo.max_width:
            assert nat == min(max(longest, combo.fixed_width or 0), combo.max_width), name
        else:
            assert nat >= longest, name        # width doesn't jump with the selection
        for idx in range(len(combo.items)):    # same width whatever is selected
            combo.index = idx
            assert combo.natural_width() == nat, name
        sp.area.scroll_to(max(0, combo.master.ly - 200))
        sp.layout_content()
        pump(app, 50)
        _check_popup(app, combo, f"{lang}:{name}")
    # screen 3 size combo
    ep = app.export_page
    ep.sync_combo()
    ep.c_size.layout(0, 0, 424)
    from ui.pages import export_page as EP
    assert ep.c_size.combo.natural_width() == EP.SIZE_COMBO_W
    app.settings.set("custom_colors", [])
    app.set_language_pref("ru")


def test_list_popup_capped_and_elided(app):
    from ui.widgets.overlay import ListPopup, Popup
    labels = ["Короткий", "Очень " * 60 + "длинный"]
    p = ListPopup(app, labels, 0, (100, 100, 120, 32), lambda i: None)
    try:
        W = app.width()
        assert p.pw <= W - 8 + 0.01
        assert p.text_room(1) < ListPopup.needed_width(labels) - 34
    finally:
        Popup.close_current()


def test_menu_popup_capped_and_elided(app):
    from ui.theme import elide, text_width
    from ui.widgets.overlay import MenuItem, MenuPopup, Popup
    long = "Удалить " * 50
    p = MenuPopup(app, [MenuItem(long, None, "trash"), MenuItem("Удалить", None, "trash")], 900, 100)
    try:
        assert p.pw <= app.width() - 16 + 0.01 and p.px >= 8 - 0.01
        room = p.pw - (5 + 9 + 16 + 12) - 19 - 4 - 1
        assert text_width(elide(long, room, 14), 14) <= room
    finally:
        Popup.close_current()


def test_elide_helper(app):
    from ui.theme import elide, text_width
    assert elide("abc", 1000, 14) == "abc"
    e = elide("Очень длинное название", 80, 14)
    assert e.endswith("…") and text_width(e, 14) <= 80
