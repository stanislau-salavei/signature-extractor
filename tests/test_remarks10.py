"""Remarks 77–85 (2026-11-19): one-photo doubt bar under the image (77), no AI in v1.0 (78), Windows 11
scrollbar (79), shortcuts with any keyboard layout (80), log file (81), state controller (82), save folder
fixed at the first launch (83), release v1.0 (84), no final period in three texts (85)."""
import ast
import csv
import dataclasses
import inspect
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from core import processing as P

from tests.test_remarks8 import app, pump, close_all, _photo, _signature      # noqa: F401  (UI fixture)

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "i18n" / "strings_ru_en.csv"


def rows():
    return {r[0]: r for r in csv.reader(CSV.open(encoding="utf-8-sig", newline=""))}


def all_texts(widget):
    out, stack = [], [widget]
    while stack:
        w = stack.pop()
        stack.extend(w.winfo_children())
        if w.winfo_class() == "Canvas" and w.winfo_ismapped():
            out += [w.itemcget(i, "text") for i in w.find_all() if w.type(i) == "text"]
    return out


def _ai_free(s: str) -> bool:
    s = s.replace("AutoCAD", "")
    return "AI" not in s and "ИИ" not in s and "нейросет" not in s.lower() and "видеокарт" not in s.lower()


# ================================================================== 78: no AI
def test_r78_no_ai_in_any_text():
    for k, r in rows().items():
        if k == "id":                           # remark 88: the issue form no longer names the graphics card
            continue
        assert _ai_free(r[2]) and _ai_free(r[3]), k


def test_r78_not_found_advice_is_frame_and_eraser():
    r = rows()
    assert r["batch.reason_not_found"][2:4] == ["Не удалось найти подпись — выделите её рамкой или уберите лишнее ластиком",
                                                "Couldn't find a signature. Select it with the crop frame or remove extras with the eraser"]
    assert r["import.tip_background"][2] == "Сложный фон — уберите лишнее ластиком или рамкой"
    for k in ("process.ai", "process.ai_desc", "settings.ai_default", "settings.gpu", "settings.gpu.unsupported",
              "help.process.ai", "errors.no_signature.title", "errors.no_signature.body"):
        assert k not in r, k


def test_r78_no_ai_in_code_settings_and_requirements():
    assert "ai" not in {f.name for f in dataclasses.fields(P.ProcessParams)}
    assert "ai_alpha" not in inspect.signature(P.process).parameters
    assert not (ROOT / "core" / "ai.py").exists()
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "onnx" not in req and "is-net" not in req and "directml" not in req
    from core import settings as S
    assert "ai_default" not in S.DEFAULT_SETTINGS and "gpu_acceleration" not in S.DEFAULT_SETTINGS
    from core import batch as B
    assert list(inspect.signature(B.process_job).parameters) == ["job", "state", "photo"]


def test_r78_old_settings_file_with_ai_keys_loads(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from core import settings as S
    d = tmp_path / S.APP_DIR_NAME
    d.mkdir()
    (d / "settings.json").write_text(json.dumps({"ai_default": True, "gpu_acceleration": False, "theme": "dark",
                                                 "settings_version": 3}), encoding="utf-8")
    m = S.SettingsManager([])
    assert m.get("theme") == "dark" and "ai_default" not in m.data
    m.set("theme", "light")
    saved = json.loads((d / "settings.json").read_text(encoding="utf-8"))
    assert "ai_default" not in saved and "gpu_acceleration" not in saved


def test_r78_help_has_no_ai_card():
    fh = pytest.importorskip("ui.dialogs.formats_help")
    r = rows()
    fake = SimpleNamespace(t=lambda k, **kw: r[k][2] if k in r else k)
    assert "AI-поиск подписи" not in fh.card_titles(fh.generic_blocks(fake, "process"))
    for topic in ("start", "prep", "process", "batch"):
        assert _ai_free(json.dumps(fh.generic_blocks(fake, topic), ensure_ascii=False, default=str)), topic


# ================================================================== 85: no final period
def test_r85_no_final_period():
    r = rows()
    for k in ("dialog.reset.body", "dialog.apply_all.body", "process.meta.frame_large"):
        for s in (r[k][2], *r[k][3].split(" | ")):
            assert not s.rstrip().endswith("."), (k, s)
    assert r["dialog.reset.body"][2] == "Все параметры вернутся к значениям по умолчанию. Свои шаблоны размеров и цвета сохранятся"
    assert r["process.meta.frame_large"][3] == "If the frame covers more than half the page, make it smaller or remove extras with the eraser"


def test_r77_help_says_under_the_image():
    a = rows()["help.batch.attention_text"]
    assert "(при одном фото — под изображением)" in a[2] and "(with one photo, below the image)" in a[3]


# ================================================================== 84: release v1.0
def test_r84_release_is_v1_0():
    from ui import app as A
    from ui.pages import settings_page as SP
    from core import updater as U
    assert A.VERSION == "1.0" and A.RELEASE_TAG == "v1.0" and SP.RELEASE_TAG == A.RELEASE_TAG
    assert not U.is_newer("v1.0", "1.0") and U.is_newer("v1.1", "1.0") and U.is_newer("v1.0.1", "1.0")
    notes = next((p for p in (ROOT / "NOTES.md", ROOT.parent / "NOTES.md") if p.exists()), None)   # repo / local
    if notes is not None:
        assert "тег `v1.0`" in notes.read_text(encoding="utf-8")


# ================================================================== 80: keyboard layouts
def test_r80_latin_letter_from_key_code():
    from ui import keys as K
    assert K.latin_letter("o", 32, "x11") == "o" and K.latin_letter("O", 0, "win32") == "o"
    # Russian layout: the key of O gives «щ», of S «ы», of Z «я», of Y «н», of V «м»
    for sym, x11, vk, letter in (("Cyrillic_shcha", 32, 79, "o"), ("Cyrillic_yeru", 39, 83, "s"),
                                 ("Cyrillic_ya", 52, 90, "z"), ("Cyrillic_en", 29, 89, "y"), ("Cyrillic_em", 55, 86, "v")):
        assert K.latin_letter(sym, x11, "x11") == letter
        assert K.latin_letter(sym, vk, "win32") == letter
    assert K.latin_letter("Escape", 9, "x11") is None and K.latin_letter("F1", 112, "win32") is None


def _ev(keysym, keycode, shift=False):
    return SimpleNamespace(keysym=keysym, keycode=keycode, state=0x4 | (0x1 if shift else 0))


def test_r80_shortcuts_with_russian_layout(app, monkeypatch):
    from ui import keys as K
    close_all()
    app.go_home()
    pump(app, 30)
    ws = app.root.tk.call("tk", "windowingsystem")
    code = {c: k for k, c in K.KEYCODES[ws].items()} if ws in K.KEYCODES else None
    if code is None:
        pytest.skip("unknown windowing system")
    calls = []
    monkeypatch.setattr(app, "open_file_dialog", lambda: calls.append("open"))
    monkeypatch.setattr(app, "go_export", lambda: calls.append("export"))
    monkeypatch.setattr(app, "undo", lambda: calls.append("undo"))
    monkeypatch.setattr(app, "redo", lambda: calls.append("redo"))
    monkeypatch.setattr(app, "paste_clipboard", lambda: calls.append("paste"))
    app.root.focus_set()
    pump(app, 20)
    for sym, letter, shift in (("Cyrillic_shcha", "o", False), ("Cyrillic_yeru", "s", False), ("Cyrillic_ya", "z", False),
                               ("Cyrillic_en", "y", False), ("Cyrillic_YA", "z", True), ("Cyrillic_em", "v", False),
                               ("o", "o", False)):
        assert app._ctrl_key(_ev(sym, code[letter], shift)) == "break"
    assert calls == ["open", "export", "undo", "redo", "redo", "paste", "open"]
    assert app._ctrl_key(_ev("Cyrillic_a", code["f"])) is None        # Ctrl+F: not a shortcut


def test_r80_text_field_editing_with_russian_layout(app):
    import tkinter as tk
    from ui import keys as K
    ws = app.root.tk.call("tk", "windowingsystem")
    if ws not in K.KEYCODES:
        pytest.skip("unknown windowing system")
    code = {c: k for k, c in K.KEYCODES[ws].items()}
    e = tk.Entry(app.root)
    e.place(x=0, y=0)
    got = []
    for ev in ("<<SelectAll>>", "<<Copy>>", "<<Paste>>", "<<Cut>>"):
        e.bind(ev, lambda _e, ev=ev: got.append(ev), add="+")
    e.focus_force()
    pump(app, 50, until=lambda: app.root.focus_get() is e, timeout=2)
    if app.root.focus_get() is not e:
        e.destroy()
        pytest.skip("no keyboard focus on this display")
    for sym, letter in (("Cyrillic_ef", "a"), ("Cyrillic_es", "c"), ("Cyrillic_em", "v"), ("Cyrillic_che", "x")):
        assert app._ctrl_key(_ev(sym, code[letter])) == "break"
    assert got == ["<<SelectAll>>", "<<Copy>>", "<<Paste>>", "<<Cut>>"]
    # a Latin layout is left to Tk's own Entry bindings (no second copy)
    assert app._ctrl_key(_ev("c", code["c"])) is None and len(got) == 4
    e.destroy()


def test_r80_bound_by_one_layout_independent_handler(app):
    b = app.root.bind_all("<Control-KeyPress>")
    assert "_ctrl_key" in b or b
    for seq in ("<Control-o>", "<Control-s>", "<Control-z>", "<Control-v>"):
        assert not app.root.bind_all(seq), seq        # no per-character bindings left


# ================================================================== 81: log file
def test_r81_log_file_rotating_and_written(tmp_path):
    from logging.handlers import RotatingFileHandler
    from core import logs as L
    root = logging.getLogger()
    saved = (list(root.handlers), root.level, sys.excepthook, threading.excepthook,
             {n: logging.getLogger(n).level for n in L.OWN})
    try:
        path = L.setup_logging(tmp_path)
        assert path == tmp_path / "signature_extractor.log"
        h = [x for x in root.handlers if isinstance(x, RotatingFileHandler)]
        assert len(h) == 1 and h[0].maxBytes == 1_000_000 and h[0].backupCount == 3
        from core import i18n
        i18n.I18n(CSV, "ru").t("process.meta", n="{", w=1)                 # a caught formatting error
        logging.getLogger("ui.test").debug("debug from the app")
        logging.getLogger("PIL.test").debug("library debug")              # libraries: warnings only
        try:
            raise ValueError("boom")
        except ValueError:
            sys.excepthook(*sys.exc_info())
        h[0].flush()
        text = path.read_text(encoding="utf-8")
        assert "debug from the app" in text and "library debug" not in text
        assert "uncaught error" in text and "ValueError: boom" in text
    finally:
        for x in list(root.handlers):
            if x not in saved[0]:
                root.removeHandler(x)
                x.close()
        root.setLevel(saved[1])
        sys.excepthook, threading.excepthook = saved[2], saved[3]
        for n, lv in saved[4].items():
            logging.getLogger(n).setLevel(lv)
        L._handler = None


def test_r81_every_caught_error_is_logged():
    """All `except` blocks of the app log (or re-raise); only an empty queue (end of polling) is not an error."""
    levels = {"debug", "info", "warning", "error", "exception", "critical"}
    bad, total = [], 0
    for f in sorted(list((ROOT / "core").glob("*.py")) + list((ROOT / "ui").rglob("*.py")) + [ROOT / "main.py"]):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ExceptHandler):
                continue
            total += 1
            if node.type is not None and ast.unparse(node.type) == "queue.Empty":
                continue
            ok = any(isinstance(s, ast.Raise) or (isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute)
                                                  and s.func.attr in levels)
                     for s in ast.walk(ast.Module(body=node.body, type_ignores=[])))
            if not ok:
                bad.append(f"{f.relative_to(ROOT)}:{node.lineno}")
    assert total > 90 and bad == [], bad


def test_r81_tk_callback_errors_go_to_the_log(app):
    from core.logs import tk_callback_error
    assert app.root.report_callback_exception is tk_callback_error
    assert "setup_logging" in (ROOT / "main.py").read_text(encoding="utf-8")


# ================================================================== 82: state controller
def test_r82_state_module_without_ui():
    src = (ROOT / "core" / "state.py").read_text(encoding="utf-8")
    assert "tkinter" not in src and "customtkinter" not in src and "import ui" not in src and "from ui" not in src
    from core.state import AppState
    s = AppState(loaded_max=2)
    assert s.page == "import" and not s.has_photos() and not s.overlay_open() and not s.can_export()
    with pytest.raises(ValueError):
        s.set_page("nowhere")
    jobs = [SimpleNamespace(id=i, version=0, result=SimpleNamespace(empty=False)) for i in range(4)]
    s.job = jobs[0]
    s.set_page("process")
    assert s.has_photos() and s.can_export() and s.has_unsaved()
    s.mark_saved("k")
    assert not s.has_unsaved("k") and s.has_unsaved("other")
    jobs[0].version = 1
    assert s.has_unsaved("k")
    s.job = jobs[3]
    out = []
    for j in jobs:
        out += s.touch(j)
    assert out == [jobs[0], jobs[1]] and s.is_recent(jobs[3])


def test_r82_app_attributes_live_in_the_state(app):
    from core.state import AppState
    assert isinstance(app.state, AppState)
    close_all()
    app.go_home()
    pump(app, 20)
    assert app.page == app.state.page == "import" and app.job is app.state.job is None
    app.settings_open = True
    assert app.state.settings_open and app.overlay_open()
    app.settings_open = False
    app._work_token = "x"
    assert app.state.saved_token == "x"
    app._work_token = None
    src = (ROOT / "ui" / "app.py").read_text(encoding="utf-8")
    assert "self.page = " not in src and "self.job: Optional" not in src


# ================================================================== 83: save folder
def test_r83_save_folder_fixed_at_first_launch(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from core import settings as S
    m = S.SettingsManager([])
    assert m.first_run and m.get("save_folder") is None
    f = m.fix_save_folder("Подписи")
    assert f == S.documents_dir() / "Подписи" and m.get("save_folder") == str(f)
    assert m.fix_save_folder("Signatures") == f                  # the language changed: the folder stays
    assert S.SettingsManager([]).save_folder("Signatures") == f  # and after a restart
    m.reset_to_defaults()
    assert m.fix_save_folder("Signatures") == S.documents_dir() / "Signatures"   # «Сбросить»: chosen again
    m.set("save_folder", str(tmp_path / "my"))
    assert m.fix_save_folder("Подписи") == tmp_path / "my"       # the user's own folder is kept


def test_r83_language_switch_keeps_the_folder(app):
    close_all()
    app.go_home()
    folder = app.settings.get("save_folder")
    assert folder and folder.endswith("Подписи")
    app.set_language_pref("en")
    pump(app, 30)
    assert app.settings.get("save_folder") == folder
    assert app.settings.save_folder(app.t("export.default_folder")) == Path(folder)
    app.set_language_pref("ru")
    pump(app, 30)
    assert app.settings.get("save_folder") == folder


# ================================================================== 78 / 77 (UI)
def test_r78_settings_page_without_ai_switches(app):
    close_all()
    app.open_settings()
    pump(app, 60)
    sp = app.settings_page
    assert not hasattr(sp, "c_ai") and not hasattr(sp, "c_gpu")
    assert [k for k, _ in sp.groups][:2] == ["settings.appearance", "shell.step.export"]
    texts = all_texts(app.settings_page)
    assert "Внешний вид" in texts and "Экспорт" in texts
    assert all(_ai_free(s) for s in texts), [s for s in texts if not _ai_free(s)]
    assert "Обработка" not in texts                               # the section had only the two switches
    app.close_settings()


@pytest.fixture(scope="module")
def doubt_photo10(tmp_path_factory):
    p = tmp_path_factory.mktemp("r10") / "two.png"
    im = _photo((1800, 640))
    d = ImageDraw.Draw(im)
    _signature(d)
    _signature(d, ox=900)
    im.save(p, dpi=(300, 300))
    return p


def test_r77_single_photo_doubt_bar_under_the_image(app, doubt_photo10):
    close_all()
    app.go_home()
    app.open_paths([doubt_photo10])
    pump(app, until=lambda: app.page == "process" and app.job is not None and app.job.processed)
    pump(app, 150)
    pp = app.process_page
    assert app.batch is None and app.job.status == "doubt"
    assert not hasattr(pp, "c_ai")
    assert pp.warn_bar.visible and not pp.strip.visible
    assert pp.preview.ly + pp.preview.lh < pp.warn_bar.ly                     # under the image
    assert abs((pp.warn_bar.ly + pp.warn_bar.lh) - (pp.lh - 64 - 16)) < 1     # at the bottom, like the batch bar
    assert "На фото несколько подписей" in pp.warn_bar.msg                     # remark 89: the reason inside
    assert pp.meta_y < pp.warn_bar.ly
    texts = all_texts(pp)
    assert all(_ai_free(s) for s in texts)


# ================================================================== 79: scrollbar
def _wait(app, cond, timeout=3.0):
    pump(app, until=cond, timeout=timeout)
    return cond()


def test_r79_scrollbar_widens_smoothly_and_narrows_after_a_second(app):
    from ui.widgets import scroll as SC
    close_all()
    app.open_settings()
    pump(app, 60)
    sp = app.settings_page
    sp.area.scroll_to(0)
    bar = sp.area.bar
    assert sp.area.content_h > sp.area.view_h
    assert bar.t == 0 and not bar.arrows_shown()
    x, y, w, h = bar.thumb_rect()
    assert w == SC.REST_W and abs(bar.lw - (x + w) - SC.REST_GAP) < 1e-6        # 2 px line, 4 px from the edge
    bar._on_enter(None)
    pump(app, 40)
    assert 0 < bar.t < 1                                                        # smooth, not a jump
    assert _wait(app, lambda: bar.t == 1)
    x, y, w, h = bar.thumb_rect()
    assert w == SC.WIDE_W and bar.arrows_shown()
    t0 = time.time()
    bar._on_leave(None)
    pump(app, 600)
    assert bar.t == 1                                                           # still wide after 0.6 s
    assert _wait(app, lambda: bar.t == 0, 3)
    assert 0.9 < time.time() - t0 < 2.5


def test_r79_scrollbar_arrows_track_and_thumb(app):
    from ui.widgets import scroll as SC
    sp = app.settings_page
    if not app.settings_open:
        app.open_settings()
        pump(app, 60)
    a, bar = sp.area, sp.area.bar
    a.scroll_to(200)
    bar._on_enter(None)
    _wait(app, lambda: bar.t == 1)

    class E:
        def __init__(self, y, x=6):
            from ui.theme import Scale
            self.x, self.y = x * Scale.factor, y * Scale.factor
    s0 = a.scroll
    bar._on_press(E(SC.ARROW_TOP + 2))                  # up arrow: one step
    assert abs(a.scroll - (s0 - SC.STEP_PX)) < 1e-6
    bar._on_release(E(SC.ARROW_TOP + 2))
    s0 = a.scroll
    bar._on_press(E(bar.lh - SC.ARROW_TOP - 2))         # down arrow
    assert abs(a.scroll - (s0 + SC.STEP_PX)) < 1e-6
    pump(app, SC.REPEAT_FIRST_MS + 3 * SC.REPEAT_MS + 60)
    assert a.scroll > s0 + SC.STEP_PX                   # held: repeats
    bar._on_release(E(bar.lh - SC.ARROW_TOP - 2))
    s1 = a.scroll
    pump(app, 200)
    assert a.scroll == s1                               # released: stops
    a.scroll_to(0)
    x, ty, w, th = bar.thumb_rect()
    bar._on_press(E(ty + th + 30))                      # track below the thumb: a page
    assert a.scroll > 100
    bar._on_release(E(ty + th + 30))
    a.scroll_to(0)
    x, ty, w, th = bar.thumb_rect()
    bar._on_press(E(ty + 5))
    bar._drag(E(ty + 5 + 40))
    assert a.scroll > 40                                # the page moves more than the thumb
    bar._on_release(E(ty + 45))
    app.close_settings()


def test_r79_long_list_bar_widens_and_does_not_pick_an_item(app):
    from ui.widgets.overlay import ListPopup
    from ui.widgets import scroll as SC
    close_all()
    app.go_home()
    pump(app, 30)
    picked = []
    lp = ListPopup(app, [f"Пункт {i}" for i in range(30)], 0, (300, 200, 200, 32), picked.append)
    pump(app, 30)
    assert lp.content_h > lp.ph and lp.sb.t == 0
    zx = lp.pw - 1 - SC.ZONE_W / 2
    lp.motion(zx, 100)
    assert _wait(app, lambda: lp.sb.t == 1) and lp.hover_i == -1
    s0 = lp.scroll
    lp.press(zx, lp.ph - SC.ARROW_TOP - 2)               # down arrow
    lp.release(zx, lp.ph - SC.ARROW_TOP - 2)
    assert lp.scroll > s0 and not lp.closed and picked == []
    lp.motion(40, 100)                                   # back over the items
    assert lp.hover_i >= 0
    pump(app, 400)
    assert lp.sb.t == 1
    assert _wait(app, lambda: lp.sb.t == 0, 3)
    lp.close()
