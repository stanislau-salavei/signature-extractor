"""Remarks 37–44 (2026-11-18): settings reset, «Применить настройки ко всем» confirm, «Начать заново?» after a
save, DXF/SVG trace resolution, Help as icon cards with photo examples, «Спрашивать» default, name template."""
import csv
import importlib
import json
import os
import time
from pathlib import Path

import numpy as np
import pytest

from core import export as ex
from core import processing as P
from tests.i18n_prompt_diff import assert_matches_prompt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "i18n" / "strings_ru_en.csv"
PROMPT_CSV = Path("/workspace/prompt/v2/i18n/strings_ru_en.csv")


def rows():
    return {r[0]: r for r in csv.reader(CSV.open(encoding="utf-8-sig", newline=""))}


# ------------------------------------------------------------------ 40: DXF / SVG trace resolution
SAMPLE3 = ROOT / "tests" / "data" / "sample3.png"   # real signature, kept locally, not in the repo
needs_sample3 = pytest.mark.skipif(not SAMPLE3.exists(), reason="local test photo not on this machine")


def _sample3_source():
    img, dpi = P.load_image(SAMPLE3)
    ph = P.prepare_photo(img, dpi, "sample3.png")
    return ex.source_from_result(P.process(ph, P.ProcessParams()))


@needs_sample3
def test_trace_resolution_never_below_source():
    src = _sample3_source()
    sw, sh = src.size_px
    for key in (ex.SIZE_15X5, ex.SIZE_ORIGINAL):
        geom = ex.compute_geometry(sw, sh, src.dpi, ex.size_choice_for_key(key, []), 0.5)
        ppm = ex._trace_resolution(src, geom)
        assert ppm >= 20.0
        if key == ex.SIZE_15X5:
            assert ppm > 40.0          # small target: trace at the source's own px/mm, not downsampled


@needs_sample3
def test_sample3_15x5_centreline_keeps_the_whole_signature():
    src = _sample3_source()
    sw, sh = src.size_px
    geom = ex.compute_geometry(sw, sh, src.dpi, ex.size_choice_for_key(ex.SIZE_15X5, []), 0.5)
    cl = ex.trace_centerline(src, geom)
    total = sum(sum(np.hypot(*np.diff(np.array(p), axis=0).T)) for p, _ in cl.paths)
    assert 33 <= total <= 42 and len(cl.paths) <= 25       # was 7.8 mm in 40 bits before the fix


# ------------------------------------------------------------------ 43 / 37: settings
@pytest.fixture()
def settings_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import core.settings as mod
    return importlib.reload(mod)


def test_if_exists_default_is_ask(settings_mod):
    assert settings_mod.DEFAULT_SETTINGS["if_exists"] == "ask"
    assert settings_mod.SettingsManager([]).get("if_exists") == "ask"


def test_saved_if_exists_choice_is_kept(settings_mod, tmp_path):
    d = tmp_path / "Signature Extractor"
    d.mkdir()
    (d / "settings.json").write_text(json.dumps({"if_exists": "add_number", "settings_version": 3}))
    assert settings_mod.SettingsManager([]).get("if_exists") == "add_number"


def test_reset_keeps_own_sizes_and_colours(settings_mod):
    s = settings_mod.SettingsManager([])
    sizes = [{"name": "Мой", "w": 30, "h": 9}]
    s.set("custom_sizes", sizes)
    s.set("custom_colors", [[1, 2, 3]])
    s.set("last_export", {"formats": ["SVG"]})
    s.set("theme", "dark")
    s.set("language", "en")
    s.set("if_exists", "replace")
    s.set("crop_margin_mm", 3.0)
    s.reset_to_defaults()
    d = settings_mod.DEFAULT_SETTINGS
    assert s.get("custom_sizes") == sizes and s.get("custom_colors") == [[1, 2, 3]]
    assert s.get("last_export") == {} and s.get("theme") == d["theme"] and s.get("language") == d["language"]
    assert s.get("if_exists") == "ask" and s.get("crop_margin_mm") == d["crop_margin_mm"]
    s2 = settings_mod.SettingsManager([])                 # saved to disk
    assert s2.get("custom_sizes") == sizes and s2.get("if_exists") == "ask"


def test_danger_button_tokens():
    from ui.theme import TOKENS
    assert TOKENS["danger"] == ("#B22222", "#B22222")
    assert TOKENS["on_danger"][0].upper() in ("#FFFFFF", "WHITE")
    src = (ROOT / "ui" / "widgets" / "controls.py").read_text(encoding="utf-8")
    assert '"danger"' in src


# ------------------------------------------------------------------ i18n
NEW_KEYS = ["settings.reset", "settings.reset.title", "settings.reset.button", "dialog.reset.title",
            "dialog.reset.body", "batch.apply_settings_all", "dialog.apply_all.title", "dialog.apply_all.body",
            "dialog.apply_all.ok", "help.formats.name_template", "help.prep.ex_good", "help.prep.ex_good_text",
            "help.prep.ex_shadow", "help.prep.ex_glare", "help.prep.ex_tiny", "help.prep.ex_skew"]


def test_i18n_new_rows_and_texts():
    r = rows()
    for k in NEW_KEYS:
        assert k in r and r[k][2] and r[k][3], k
    assert r["settings.reset"][2:4] == ["Сброс", "Reset"]
    assert r["settings.reset.title"][2] == "Восстановить параметры по умолчанию"
    assert r["settings.reset.button"][2] == "Сбросить"
    assert r["dialog.reset.title"][2] == "Сбросить настройки?"
    assert r["batch.apply_settings_all"][2:4] == ["Применить настройки ко всем", "Apply settings to all"]
    assert r["dialog.apply_all.title"][2] == "Применить настройки ко всем?"
    assert r["dialog.apply_all.ok"][2] == "Применить"
    assert r["settings.name_template.desc"][2] == ("Метки: {имя}, {дата}. Например, подпись_{имя}_{дата} → "
                                                   "подпись_IMG_3051_2026-11-18.png")
    assert r["settings.name_template.desc"][3] == ("Tokens: {name}, {date}. For example, signature_{name}_{date} → "
                                                   "signature_IMG_3051_2026-11-18.png")
    assert len(r) >= 327          # stage 5 adds rows (test_stage5 checks the exact count)


def test_apply_all_body_plurals():
    from core.i18n import I18n
    ru, en = I18n(CSV, "ru"), I18n(CSV, "en")
    assert ru.tn("dialog.apply_all.body", 5) == ("Настройки панели этого фото будут применены к остальным 5 фото "
                                                 "пакета. Рамка обрезки и ластик не изменятся")   # remark 85: no period
    assert "the other photo " in en.tn("dialog.apply_all.body", 1) and "other 5 photos " in en.tn("dialog.apply_all.body", 5)


@pytest.mark.skipif(not PROMPT_CSV.exists(), reason="prompt CSV not on this machine")
def test_csv_matches_prompt_copy():
    assert_matches_prompt(CSV, PROMPT_CSV)     # remarks 77–85: approved differences only


# ------------------------------------------------------------------ 41 / 42 / 44: help cards
def fake_app(lang=2):
    from types import SimpleNamespace
    r = rows()
    return SimpleNamespace(t=lambda k, **kw: r[k][lang] if k in r else k,
                           i18n=SimpleNamespace(strings={k: {} for k in r}))


def test_help_topics_are_icon_cards_with_existing_icons():
    fh = pytest.importorskip("ui.dialogs.formats_help")
    app = fake_app()
    for tp in ("start", "prep", "process", "batch", "formats"):
        blocks = fh.topic_blocks(app, tp)
        cards = [d for k, d in blocks if k == "card"]
        assert cards, tp
        assert {k for k, _ in blocks} <= {"intro", "intro_logo", "card", "examples"}, tp
        for icon, _title, _items in cards:
            if icon in ("PNG", "SVG", "DXF"):          # format tiles carry the format name, not an icon
                continue
            assert (ROOT / "assets" / "icons" / f"{icon}.png").exists(), icon


def test_prep_examples_come_first_and_assets_exist():
    fh = pytest.importorskip("ui.dialogs.formats_help")
    r = rows()
    blocks = fh.topic_blocks(fake_app(), "prep")
    kinds = [k for k, _ in blocks]
    assert kinds.index("examples") < kinds.index("card")
    for n in ("good", "shadow", "glare", "tiny", "skew"):
        assert (ROOT / "assets" / "help" / f"ex_{n}.png").exists()
    assert "help.prep.more" not in r or not any("Ещё несколько советов" in str(d) for _, d in blocks)


def test_formats_help_has_name_template_card():
    fh = pytest.importorskip("ui.dialogs.formats_help")
    r = rows()
    t = lambda k, **kw: r[k][2] if k in r else k
    text = json.dumps(fh.formats_blocks(t), ensure_ascii=False)
    assert r["help.formats.name_template"][2].split(" ")[0] in text


# ------------------------------------------------------------------ UI (real app under X)
@pytest.fixture(scope="module")
def app(tmp_path_factory):
    if not os.environ.get("DISPLAY"):
        pytest.skip("no X display")
    tmp = tmp_path_factory.mktemp("appdata6")
    old = {k: os.environ.get(k) for k in ("APPDATA", "USERPROFILE", "LANG")}
    os.environ["APPDATA"] = os.environ["USERPROFILE"] = str(tmp)
    os.environ["LANG"] = "ru_RU.UTF-8"
    (tmp / "Signature Extractor").mkdir()
    (tmp / "Signature Extractor" / "settings.json").write_text(json.dumps({"theme": "light", "language": "ru"}))
    import core.settings
    importlib.reload(core.settings)
    from ui import app as A
    a = A.App([])
    a.root.geometry("1024x616+0+0")
    a.root.update()
    yield a
    from ui.widgets.overlay import Popup
    Popup.close_current()
    a.root.destroy()
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def pump(app, ms=50, until=None, timeout=20.0):
    end = time.time() + (timeout if until else ms / 1000)
    while time.time() < end:
        app.root.update()
        if until is not None and until():
            break
        time.sleep(0.01)


def _close_popups():
    from ui.widgets.overlay import Popup
    while Popup.current is not None:
        Popup.close_current()


@pytest.fixture
def folder(tmp_path):
    from PIL import Image, ImageDraw
    d = tmp_path / "photos"
    d.mkdir()
    for i in range(3):
        im = Image.new("RGB", (900, 560), (239, 236, 227))
        dr = ImageDraw.Draw(im)
        dr.line([(150 + 60 * k + 7 * i, 300 + (60 if k % 2 else -60)) for k in range(10)], fill=(30, 45, 140), width=9)
        im.save(d / f"IMG_{i}.jpg", quality=92, dpi=(300, 300))
    return d


def _open_batch(app, folder):
    _close_popups()
    app.go_home()
    app.open_paths([folder])
    pump(app, until=lambda: app.batch is not None and app.page == "process" and not app.batch.busy())
    pump(app, 100)


def test_settings_reset_card_after_about(app):
    app.open_settings()
    pump(app, 100)
    sp = app.settings_page
    keys = [k for k, _ in sp.groups]
    assert keys[-2:] == ["settings.about", "settings.reset"]
    assert sp.btn_reset.kind == "danger"
    from ui.widgets.overlay import Popup
    sp._confirm_reset()
    dlg = Popup.current
    assert dlg is not None and dlg.title == "Сбросить настройки?" and dlg.esc_index == 1
    assert [k for _, k, _ in dlg.buttons_spec] == ["danger", "secondary"]
    app.settings.set("if_exists", "replace")
    dlg.escape()                                    # Esc = «Отмена»
    pump(app, 50)
    assert app.settings.get("if_exists") == "replace"
    sp._confirm_reset()
    Popup.current._activate(0)
    pump(app, 50)
    assert app.settings.get("if_exists") == "ask"
    app.close_settings()
    pump(app, 50)


def test_apply_all_asks_and_esc_cancels(app, folder):
    from ui.widgets.overlay import Popup
    _open_batch(app, folder)
    b = app.batch
    app.edit(flatten=False)
    app.apply_to_all()
    dlg = Popup.current
    assert dlg.title == "Применить настройки ко всем?" and "остальным 2 фото" in "".join(s for ln in dlg.lines for s, _ in ln)
    dlg.escape()
    pump(app, 50)
    assert sum(not j.state.params.flatten for j in b.items) == 1
    _close_popups()


def test_restart_prompt_follows_saved_snapshot(app, folder):
    _open_batch(app, folder)
    pump(app, until=lambda: app.batch.ready_for_export())
    assert app.has_unsaved()                                # never saved
    app.go_export()
    pump(app, 100)
    app.mark_saved()                                        # a save happens on screen 3
    assert not app.has_unsaved()
    app.show_page("process")                                # «Назад»
    pump(app, 100)
    assert not app.has_unsaved()                            # Назад/Далее is not a change
    app.go_export()
    pump(app, 100)
    assert not app.has_unsaved()
    pg = app.export_page
    app.mark_saved()
    pg.export_key = lambda: ("changed",)                    # S6/B4: an export setting changed
    assert app.has_unsaved()
    del pg.export_key
    app.show_page("process")
    pump(app, 100)
    app.edit(flatten=False)
    assert app.has_unsaved()                                # edit after the save
    app.undo()
    assert app.has_unsaved()                                # B7: Ctrl+Z is a change too
    app.mark_saved()
    app.remove_photo(app.batch.items[-1])
    pump(app, 50)
    assert app.has_unsaved()                                # B8: «Убрать»
    app.mark_saved()
    app.mark_save_failed()
    assert app.has_unsaved()                                # failed / cancelled save
    _close_popups()


def test_wrap_keeps_glued_punctuation_with_its_word():
    if not os.environ.get("DISPLAY"):
        pytest.skip("no X display")
    import tkinter as tk
    from ui.dialogs.content import wrap_runs
    from ui.theme import text_width
    r = tk.Tk()
    try:
        runs = [("aaa bbb ccc ", "normal"), ("«_»", "semibold"), (".", "normal")]
        w = text_width("aaa bbb ccc ", 14) + text_width("«_»", 14, "semibold") + 1   # «_» fits, "." doesn't
        lines = wrap_runs(runs, w, 14)
        assert lines[-1] == [("«_»", "semibold"), (".", "normal")]
        assert wrap_runs([("hello world foo bar", "normal")], 60, 14)[0] == [("hello ", "normal")]
    finally:
        r.destroy()


def test_r45_help_names_the_new_button_and_checkbox_is_kept():
    r = rows()
    assert "«Применить настройки ко всем»" in r["help.batch.all_text"][2]
    assert r["help.batch.all_text"][3].startswith("You can set") and "Apply settings to all asks first" in r["help.batch.all_text"][3]
    assert r["batch.apply_all"][2:4] == ["Применить ко всем", "Apply to all"]      # file-exists checkbox (44)
    for k, row in r.items():
        if k.startswith("help."):
            assert "«Применить ко всем»" not in row[2] and "Apply to all " not in row[3], k
