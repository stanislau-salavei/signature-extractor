"""Stage 5 (2026-11-18): sizes manager (36/37/49/51/52/56), own colours in Settings, «Сообщить о проблеме»,
updates (32, silent check, download + SHA-256), DirectX 12, Esc, language switch, 1000 px column, help texts."""
from core.version import VERSION
import csv
import hashlib
import importlib
import io
import json
import os
import re
import time
import urllib.parse
from pathlib import Path

import pytest

from core import export as ex
from core import updater as U
from tests.i18n_prompt_diff import assert_matches_prompt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "i18n" / "strings_ru_en.csv"
from tests.i18n_prompt_diff import PROMPT_CSV  # noqa: E402  (remark 91: copy in docs/prompt_v2)


def rows():
    return {r[0]: r for r in csv.reader(CSV.open(encoding="utf-8-sig", newline=""))}


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    if not os.environ.get("DISPLAY"):
        pytest.skip("no X display")
    tmp = tmp_path_factory.mktemp("appdata_s5")
    old = {k: os.environ.get(k) for k in ("APPDATA", "USERPROFILE", "LANG")}
    os.environ["APPDATA"] = os.environ["USERPROFILE"] = str(tmp)
    os.environ["LANG"] = "ru_RU.UTF-8"
    (tmp / "Signature Extractor").mkdir()
    (tmp / "Signature Extractor" / "settings.json").write_text(json.dumps({"theme": "light", "language": "ru"}))
    import core.settings
    importlib.reload(core.settings)
    from ui import app as A
    a = A.App([])
    a.root.geometry("1280x720+0+0")
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


def pump(app, ms=50, until=None, timeout=10.0):
    end = time.time() + (timeout if until else ms / 1000)
    while time.time() < end:
        app.root.update()
        if until is not None and until():
            break
        time.sleep(0.01)


def popups():
    from ui.widgets.overlay import Popup
    return Popup


def close_all():
    P = popups()
    while P.current is not None:
        P.close_current()


def settings(app):
    close_all()
    if not app.settings_open:
        app.open_settings()
    pump(app, 60)
    sp = app.settings_page
    sp.c_sizes.is_open = True
    sp.sync()
    pump(app, 30)
    return sp


def labels(menu):
    return [(it.text, bool(it.disabled)) if it is not None else None for it in menu.items]


def all_texts(widget):
    out = []
    stack = [widget]
    while stack:
        w = stack.pop()
        stack.extend(w.winfo_children())
        if w.winfo_class() == "Canvas" and w.winfo_ismapped():
            for item in w.find_all():
                if w.type(item) == "text":
                    out.append(w.itemcget(item, "text"))
    return out


# ------------------------------------------------------------------ 1. sizes
def test_size_rows_menus_built_in_and_own(app):
    app.settings.set("custom_sizes", [{"id": "1", "name": "Штамп КБ", "w_mm": 20, "h_mm": 8}])
    app.settings.set("default_size", ex.SIZE_15X5)
    sp = settings(app)
    opts = sp._size_options()
    keys = [k for k, _, _ in opts]
    assert keys[-1] == "tpl:1" and ex.SIZE_15X5 in keys
    assert len(sp.size_more) >= len(opts) and sp.btn_add_size.winfo_ismapped()
    # 52: built-in default → only «Сделать по умолчанию», inactive
    sp._size_menu(keys.index(ex.SIZE_15X5))
    assert labels(popups().current) == [("Сделать по умолчанию", True)]
    close_all()
    # 36: own size → Сделать по умолчанию / Изменить / — / Удалить
    sp._size_menu(len(opts) - 1)
    assert labels(popups().current) == [("Сделать по умолчанию", False), ("Изменить", False), None, ("Удалить", False)]
    popups().current.items[0].command()
    close_all()
    pump(app, 30)
    assert app.settings.get("default_size") == "tpl:1"
    assert sp._size_summary() == "Штамп КБ · 20 × 8 мм"
    # height grows by one 40 px row per size
    n = len(sp._size_options())
    assert sp._sizes_body_h() == 4 + 40 * n + 11 + 32 + 19
    app.settings.set("default_size", ex.SIZE_15X5)


def test_add_edit_delete_size_dialogs(app):
    app.settings.set("custom_sizes", [])
    app.settings.set("default_size", ex.SIZE_15X5)
    sp = settings(app)
    sp._add_size()
    pump(app, 40)
    dlg = popups().current
    assert dlg.title == "Добавить размер" and [b[0] for b in dlg.buttons_spec] == ["Сохранить", "Отмена"]
    dlg.boxes["name"].entry.insert(0, "Визитка")
    dlg.boxes["w"].entry.insert(0, "0")        # invalid width keeps the dialog open
    dlg.boxes["h"].entry.insert(0, "10")
    dlg._activate(0)
    assert popups().current is dlg and not dlg.closed
    dlg.boxes["w"].entry.delete(0, "end")
    dlg.boxes["w"].entry.insert(0, "30,5")
    dlg._activate(0)
    pump(app, 40)
    assert app.settings.get("custom_sizes") == [{"id": "1", "name": "Визитка", "w_mm": 30.5, "h_mm": 10.0}]
    # empty name → «W × H мм»
    sp._add_size()
    pump(app, 40)
    d2 = popups().current
    d2.boxes["w"].entry.insert(0, "12")
    d2.boxes["h"].entry.insert(0, "4")
    d2._activate(0)
    pump(app, 40)
    assert app.settings.get("custom_sizes")[1]["name"] == "12 × 4 мм"
    # 49: edit
    sz = app.settings.get("custom_sizes")[0]
    sp._edit_size(sz)
    pump(app, 40)
    d3 = popups().current
    assert d3.title == "Изменить размер" and d3.boxes["w"].entry.get() == "30,5"
    d3.boxes["name"].entry.delete(0, "end")
    d3.boxes["name"].entry.insert(0, "Визитка 2")
    d3._activate(0)
    pump(app, 40)
    assert app.settings.get("custom_sizes")[0]["name"] == "Визитка 2"
    # 51: delete the default → note; 56: delete another → no note
    app.settings.set("default_size", "tpl:1")
    sp._delete_size(app.settings.get("custom_sizes")[0])
    pump(app, 40)
    d4 = popups().current
    assert d4.title.replace("\xa0", " ") == "Удалить размер «Визитка 2 · 30,5 × 10 мм»?"
    assert [k for _, k, _ in d4.buttons_spec] == ["danger", "secondary"] and d4.esc_index == 1
    assert "".join(s for ln in d4.lines for s, _ in ln).strip() == "По умолчанию станет 15 × 5 мм"
    d4._activate(0)
    pump(app, 40)
    assert [s["id"] for s in app.settings.get("custom_sizes")] == ["2"]
    assert app.settings.get("default_size") == ex.SIZE_15X5
    sp._delete_size(app.settings.get("custom_sizes")[0])
    pump(app, 40)
    d5 = popups().current
    assert d5.lines == []
    d5.escape()
    pump(app, 40)
    assert len(app.settings.get("custom_sizes")) == 1
    app.settings.set("custom_sizes", [])
    close_all()


def test_long_delete_title_wraps(app):
    from ui.dialogs import sizes as SZ
    sz = {"id": "9", "name": "Очень длинное название шаблона для печати на бланках", "w_mm": 40, "h_mm": 12}
    app.settings.set("custom_sizes", [sz])
    d = SZ.confirm_delete_size(app, sz)
    pump(app, 30)
    assert len(d.title_lines) >= 2 and d.title_extra == 26 * (len(d.title_lines) - 1)
    d.escape()
    app.settings.set("custom_sizes", [])


# ------------------------------------------------------------------ 2. own colours
def test_delete_own_colour_from_settings(app):
    app.settings.set("custom_colors", [{"id": "1", "name": "Бордо", "hex": "#7A1F2B"}])
    app.settings.set("default_color", "custom:1")
    sp = settings(app)
    items = sp._color_items()
    assert sp._delete_color(items[0][0]) is None      # built-in colour: nothing to delete
    dlg = sp._delete_color(items[-1][0])              # remark 47: asks first
    assert dlg is not None
    dlg._activate(0)
    pump(app, 30)
    close_all()
    assert app.settings.get("custom_colors") == [] and app.settings.get("default_color") == ex.DEFAULT_COLOR_KEY


# ------------------------------------------------------------------ 3. issue
def test_issue_url_has_version_windows_language(app, monkeypatch):
    from ui import platform_win as pw
    monkeypatch.setattr(pw, "windows_version", lambda: "Windows 11 23H2 (build 22631)")
    url = app.issue_url()
    assert url.startswith("https://github.com/") and "/issues/new?body=" in url and "title=" not in url
    body = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["body"][0]
    assert body == f"App version: {VERSION}\nWindows: Windows 11 23H2 (build 22631)\nLanguage: ru\n\nDescribe the problem:\n"   # 88
    assert len(url) <= 2000
    opened = []
    monkeypatch.setattr(app, "open_url", opened.append)
    app.report_issue()
    assert opened == [url]
    print("issue URL:", url)


# ------------------------------------------------------------------ 4. updates
def _rel_json(ver="1.2"):
    return {"tag_name": f"v{ver}", "body": "", "assets": [
        {"name": f"SignatureExtractor-{ver}-setup.exe", "browser_download_url": "https://x/i.exe"},
        {"name": f"SignatureExtractor-{ver}-setup.exe.sha256", "browser_download_url": "https://x/i.sha256"}]}


class _Resp(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}


def _controller(app, tmp_path, data=b"MZ" + b"y" * 300_000, sha=None, latest="1.2", offline=False, opener=None):
    up = app.updates
    sha = sha or hashlib.sha256(data).hexdigest()

    def fetcher(url):
        if offline:
            raise OSError("offline")
        if url.endswith(".sha256"):
            return f"{sha}  SignatureExtractor-{latest}-setup.exe".encode()
        return json.dumps(_rel_json(latest)).encode()
    up.fetcher = fetcher
    up.opener = opener or (lambda u: _Resp(data))
    up.dest_dir = tmp_path
    calls = {"launch": [], "quit": 0}
    up.launcher = lambda p: calls["launch"].append(p) or True

    def q():
        calls["quit"] += 1
    up.quit = q
    return up, calls


def test_manual_check_latest_and_offline_notes(app, tmp_path):
    sp = settings(app)
    up, _ = _controller(app, tmp_path, latest=VERSION)
    sp._check_now()
    pump(app, until=lambda: not up.checking)
    pump(app, 30)
    assert sp.update_note == f"Установлена последняя версия ({VERSION})"
    assert sp.c_upd.desc_lines() == [f"Установлена последняя версия ({VERSION})"]
    up, _ = _controller(app, tmp_path, offline=True)
    sp._check_now()
    pump(app, until=lambda: not up.checking)
    assert sp.update_note == "Не удалось проверить обновления, нет подключения"
    app.close_settings()
    pump(app, 30)
    assert sp.update_note == ""                       # the line lasts until Settings close


def test_new_version_download_verify_launch_quit(app, tmp_path):
    settings(app)
    up, calls = _controller(app, tmp_path)
    app.check_for_updates(manual=True)
    pump(app, until=lambda: popups().current is not None and hasattr(popups().current, "downloading"))
    dlg = popups().current
    assert dlg.title == "Доступна новая версия" and [b[0] for b in dlg.buttons_spec] == ["Скачать", "Позже"]
    dlg._activate(0)
    assert dlg.downloading and [b[0] for b in dlg.buttons_spec] == ["Отмена"]
    assert "Скачивание" in "".join(s for ln in dlg.lines for s, _ in ln)
    pump(app, until=lambda: calls["quit"])
    assert len(calls["launch"]) == 1 and calls["launch"][0].name == "SignatureExtractor-1.2-setup.exe"
    assert calls["launch"][0].exists() and calls["quit"] == 1
    close_all()
    app.close_settings()


def test_damaged_and_failed_downloads(app, tmp_path):
    settings(app)
    up, calls = _controller(app, tmp_path, sha="0" * 64)
    up.show(U.parse_release(_rel_json()))._activate(0)
    pump(app, until=lambda: popups().current is not None and not hasattr(popups().current, "downloading"))
    assert popups().current.title == "Файл обновления повреждён, попробуйте ещё раз"
    assert calls["launch"] == [] and not list(tmp_path.iterdir())     # wrong file deleted
    close_all()

    def broken(u):
        raise OSError("reset by peer")
    up, calls = _controller(app, tmp_path, opener=broken)
    up.show(U.parse_release(_rel_json()))._activate(0)
    pump(app, until=lambda: popups().current is not None and not hasattr(popups().current, "downloading"))
    assert popups().current.title == "Не удалось скачать обновление" and calls["launch"] == []
    close_all()
    app.close_settings()


def test_cancel_download_removes_file(app, tmp_path):
    class Slow(_Resp):
        def read(self, n=-1):
            time.sleep(0.02)
            return super().read(4096)
    up, calls = _controller(app, tmp_path, opener=lambda u: Slow(b"z" * 400_000))
    dlg = up.show(U.parse_release(_rel_json()))
    dlg._activate(0)
    pump(app, until=lambda: dlg.fraction > 0)
    assert 0 < dlg.fraction < 1
    dlg.escape()                                      # Esc = «Отмена»
    assert dlg.closed
    pump(app, 400)
    assert popups().current is None and calls["launch"] == [] and not list(tmp_path.glob("*"))


def test_later_and_silent_check_only_on_screen_1(app, tmp_path, monkeypatch):
    close_all()
    up, _ = _controller(app, tmp_path)
    monkeypatch.delenv("SE_NO_UPDATE_CHECK", raising=False)
    app.settings.set("check_updates", True)
    app.settings.set("last_update_check", "2026-01-01T00:00:00")
    app.open_settings()                               # not on screen 1 → waits
    pump(app, 30)
    up.startup()
    pump(app, until=lambda: up.pending is not None)
    pump(app, 200)
    assert popups().current is None and up.pending is not None
    assert not U.due(app.settings.get("last_update_check"))   # contacted → once a day
    app.close_settings()
    pump(app, until=lambda: popups().current is not None, timeout=3)
    dlg = popups().current
    assert dlg.title == "Доступна новая версия"
    dlg.escape()                                      # Esc = «Позже»
    pump(app, 30)
    assert popups().current is None and not U.due(app.settings.get("last_update_check"))
    up.startup()                                      # same day: no request at all
    assert not up.checking
    # switched off: nothing
    app.settings.set("last_update_check", None)
    app.settings.set("check_updates", False)
    up.startup()
    assert not up.checking
    # offline: silent, retried next start
    app.settings.set("check_updates", True)
    up, _ = _controller(app, tmp_path, offline=True)
    up.startup()
    pump(app, until=lambda: not up.checking)
    pump(app, 30)
    assert popups().current is None and app.settings.get("last_update_check") is None
    app.settings.set("check_updates", False)


# ------------------------------------------------------------------ 5. DirectX 12
# remark 78: «Ускорение на видеокарте» is gone with the AI (tests/test_remarks10.py checks it is not there)


# ------------------------------------------------------------------ 6. Esc
def test_esc_in_field_then_page(app):
    sp = settings(app)
    box = sp.name_box
    box.entry.focus_force()
    pump(app, 30)
    box.entry.insert("end", "_x")
    r = box._esc()
    assert r == "break" and app.settings_open and "_x" not in box.entry.get()
    assert app.root.focus_get() is not box.entry
    app._esc()
    assert not app.settings_open
    # a dialog over Settings: Esc closes only the dialog
    app.open_settings()
    pump(app, 30)
    sp._confirm_reset()
    app._esc()
    assert popups().current is None and app.settings_open
    app._esc()
    assert not app.settings_open
    app.open_help("start")
    pump(app, 30)
    app._esc()
    assert not app.help_open
    assert app._esc() is None                         # screen 1: Esc does not close the window
    assert app.root.winfo_exists()


# ------------------------------------------------------------------ 7. language
CYR = re.compile("[А-Яа-яЁё]")


def test_language_switch_retranslates_everything(app):
    app.settings.set("custom_sizes", [])
    app.settings.set("custom_colors", [])
    sp = settings(app)
    for c in (sp.c_theme, sp.c_formats, sp.c_sizes, sp.c_about):
        c.is_open = True
    sp.layout_content()
    sp.area.scroll_to(0)
    app.set_language_pref("en")
    pump(app, 60)
    texts = all_texts(app.root)
    print("EN texts:", len(texts))
    assert len(texts) > 40 and "Settings" in texts and "Add size" in " ".join(texts)
    folder = str(app.settings.save_folder(""))       # remark 83: the folder of the first launch stays
    left = [s for s in texts if CYR.search(s) and s != folder]
    assert left == [], left
    assert app.root.title() == "Signature Extractor"
    app.close_settings()
    app.open_help("formats")
    pump(app, 60)
    left = [s for s in all_texts(app.root) if CYR.search(s)]
    assert left == [], left
    app.close_help()
    app.set_language_pref("ru")
    pump(app, 30)


# ------------------------------------------------------------------ 8. 1000 px column
def test_column_width_on_wide_and_min_window(app):
    sp = settings(app)
    assert sp.column(2560) == (780.0, 1000) and sp.column(1024) == (56.0, 912)
    assert sp.column(1280) == (140.0, 1000)
    app.close_settings()
    app.open_help("start")
    pump(app, 30)
    hp = app.help_page
    assert hp.column(2560) == (780.0, 1000) and hp.column(1024) == (56.0, 912)
    app.close_help()


# ------------------------------------------------------------------ 9. help texts, i18n
def test_every_help_key_is_shown(app, monkeypatch):
    from core import i18n as I
    used = set()
    orig = I.I18n.t

    def rec(self, key, **kw):
        used.add(key)
        return orig(self, key, **kw)
    monkeypatch.setattr(I.I18n, "t", rec)
    from ui.pages.help_page import TOPICS
    for tp in TOPICS:
        app.open_help(tp)
        pump(app, 40)
    app.close_help()
    from ui.dialogs.formats_help import HelpWindow
    for tp in TOPICS:
        HelpWindow.open(app, tp)
        pump(app, 30)
        close_all()
    keys = {k for k in rows() if k.startswith("help.")}
    assert keys - used == set()


def test_stage5_i18n_rows_and_csv_identity():
    r = rows()
    assert len(r) >= 330            # remarks 46–58 add rows (exact count in test_remarks7)
    assert r["update.downloading"][2:4] == ["Скачивание… {percent} %", "Downloading… {percent}%"]
    assert r["update.download_failed"][2:4] == ["Не удалось скачать обновление", "Couldn't download the update"]
    assert r["issue.body"][2] == r["issue.body"][3] and "\\n" in r["issue.body"][2]
    assert_matches_prompt(CSV, PROMPT_CSV)     # remarks 77–85: approved differences only
