"""Remarks 27–31 (2026-11-17): EN names, SVG mode default in Settings, «Справка» page, screen 3 «Назад»."""
import csv
import importlib
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import export as ex

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "i18n" / "strings_ru_en.csv"


def rows():
    return {r[0]: r for r in csv.reader(CSV.open(encoding="utf-8-sig", newline=""))}


def fake_app(lang=2):
    r = rows()
    return SimpleNamespace(t=lambda k, **kw: r[k][lang] if k in r else k,
                           i18n=SimpleNamespace(strings={k: {} for k in r}))


# ------------------------------------------------------------------ 27, 28: EN texts
def test_en_svg_mode_as_in_original():
    r = rows()
    assert r["export.svg.mode.original"][2:4] == ["Как в оригинале", "As in original"]
    assert r["export.svg.mode.stroke"][3] == "Set thickness"
    assert r["help.formats.svg_thickness"][3].startswith("Thickness: As in original keeps the strokes")


def test_en_dxf_desc_short():
    r = rows()
    assert r["export.dxf.desc"][3] == "For AutoCAD and KOMPAS-3D, lines in mm"
    assert len(r["export.dxf.desc"][3]) <= len("Vector for the web and graphics editors")   # SVG line fits


# ------------------------------------------------------------------ 29: SVG mode in Settings
def test_settings_svg_mode_row():
    r = rows()
    assert r["settings.svg_mode"][2:4] == ["Толщина SVG", "SVG thickness"]
    keys = list(r)
    assert keys.index("settings.svg_mode") == keys.index("settings.formats.desc") + 1


def test_resolve_svg_mode():
    assert ex.resolve_svg_mode({}, "stroke") == "stroke"                    # Settings default
    assert ex.resolve_svg_mode({"svg_mode": "original"}, "stroke") == "original"   # last export wins
    assert ex.resolve_svg_mode(None, None) == "original"
    assert ex.resolve_svg_mode({"svg_mode": "bogus"}, "also-bogus") == "original"


def test_settings_default_resets_remembered_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import core.settings as mod
    mod = importlib.reload(mod)
    s = mod.SettingsManager([])
    assert "svg_mode" in mod.LAST_EXPORT_LINKS
    s.set("last_export", {"formats": ["SVG"], "svg_mode": "original"})
    s.set_export_default("svg_mode", "stroke")
    s2 = mod.SettingsManager([])
    assert s2.get("svg_mode") == "stroke"
    assert "svg_mode" not in s2.get("last_export") and s2.get("last_export")["formats"] == ["SVG"]
    assert ex.resolve_svg_mode(s2.get("last_export"), s2.get("svg_mode")) == "stroke"


def test_export_card_remembers_mode_in_last_export():
    src = "".join(p.read_text(encoding="utf-8") for p in [ROOT / "ui" / "pages" / "export_page.py", *sorted((ROOT / "ui" / "pages" / "export").glob("*.py"))])   # remark 112: screen 3 in parts
    body = src[src.index("    def set_svg_mode"):src.index("    def apply_svg_line")]
    assert 'last["svg_mode"] = mode' in body and 'settings.set("svg_mode"' not in body
    assert '"svg_mode": self.svg_mode' in src[src.index("    def remember"):]


def test_settings_svg_mode_moved_to_own_card():
    """Remark 29 radios in «Форматы по умолчанию» were replaced by the «Толщина SVG» card (remark 32)."""
    sp = pytest.importorskip("ui.pages.settings_page")
    assert not hasattr(sp, "SVG_MODE_H")
    src = (ROOT / "ui" / "pages" / "settings_page.py").read_text(encoding="utf-8")
    assert "body_h=lambda: FMT_ROWS_H)" in src and 'set_export_default("svg_mode"' in src


# ------------------------------------------------------------------ 30: «Справка» page
def test_menu_help_opens_page_and_context_help_stays_dialog():
    src = "".join((ROOT / "ui" / f).read_text(encoding="utf-8") for f in ("app.py", "keys.py", "open_flow.py", "report.py"))   # remark 112
    body = src[src.index("    def open_help("):src.index("    def _hide_help")]
    assert "HelpPage" in body and "HelpWindow" not in body
    for fn in ("open_help_prep", "open_formats_help"):
        b = src[src.index(f"    def {fn}("):]
        b = b[:b.index("\n    def ", 10)]
        assert "HelpWindow.open" in b
    esc = src[src.index("    def _esc("):]
    assert "self.close_help()" in esc[:esc.index("\n    def ", 10)]


def test_help_page_topics_and_blocks():
    hp = pytest.importorskip("ui.pages.help_page")
    assert hp.TOPICS == ("start", "prep", "process", "batch", "formats")
    for tp in hp.TOPICS:
        assert (ROOT / "assets" / "icons" / f"help_{tp}.png").exists()
    page = object.__new__(hp.HelpPage)
    page.app = fake_app(lang=2)
    for tp in hp.TOPICS:
        page.topic = tp
        b = page.blocks()
        assert b[0] == ("title", rows()[f"help.nav.{tp}"][2]) and len(b) > 3


def test_process_and_batch_sections_have_headings():
    """Remark 41: every section is a card with an icon and its heading as the card title."""
    fh = pytest.importorskip("ui.dialogs.formats_help")
    app = fake_app(lang=2)
    assert fh.card_titles(fh.generic_blocks(app, "process")) == [
        "Рамка области", "Ластик", "Выравнивание фона", "Фильтр по цвету чернил",
        "Тонкая настройка", "Фон предпросмотра"]                        # remark 78: no «AI-поиск подписи»
    assert fh.card_titles(fh.generic_blocks(app, "batch")) == [
        "Лента фото", "Настройки для всех фото", "Требуют внимания", "Добавить и убрать", "Сохранение"]
    for tp in ("start", "prep", "process", "batch"):
        assert all(len(d) < 40 for d in fh.card_titles(fh.generic_blocks(app, tp))), tp


# ------------------------------------------------------------------ 31: screen 3 «Назад»
def test_export_back_button_is_secondary_like_screen_2():
    src = "".join(p.read_text(encoding="utf-8") for p in [ROOT / "ui" / "pages" / "export_page.py", *sorted((ROOT / "ui" / "pages" / "export").glob("*.py"))])   # remark 112: screen 3 in parts
    assert re.search(r'self\.back = Button\(self, "", kind="secondary", icon="arrow_left", bg="abar"', src)
    pp = (ROOT / "ui" / "pages" / "process_page.py").read_text(encoding="utf-8")
    assert re.search(r'self\.back = Button\(self, app\.t\("common\.back"\), icon="arrow_left", bg="abar"', pp)
    assert 'kind="ghost"' not in src
