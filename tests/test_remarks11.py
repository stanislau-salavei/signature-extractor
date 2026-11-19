"""Remarks 86–89 (2026-11-19): the photo strip's scrollbar like the other Windows 11 bars (86), the file name
template follows the language until it is edited (87), no graphics card / DirectX 12 in the issue form (88),
the reason inside the yellow «Требует внимания» card in every case (89).  Synthetic photos only."""
import csv
import inspect
import urllib.parse
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tests.test_remarks8 import app, pump, close_all, _photo, _signature      # noqa: F401  (UI fixture)

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "i18n" / "strings_ru_en.csv"
PAPER = (246, 245, 241)


def rows():
    return {r[0]: r for r in csv.reader(CSV.open(encoding="utf-8-sig", newline=""))}


def _wait(app, cond, timeout=3.0):
    pump(app, until=cond, timeout=timeout)
    return cond()


def _one(path):
    im = _photo()
    _signature(ImageDraw.Draw(im))
    im.save(path, dpi=(300, 300))


def _two(path):
    im = _photo((1800, 640))
    d = ImageDraw.Draw(im)
    _signature(d)
    _signature(d, ox=900)
    im.save(path, dpi=(300, 300))


@pytest.fixture(scope="module")
def mixed(tmp_path_factory):
    """photo 1–3 fine, photo 4 two signatures (doubt), photo 5 blank (not found)."""
    d = tmp_path_factory.mktemp("r11mixed")
    for i in (1, 2, 3):
        _one(d / f"photo_{i}.png")
    _two(d / "photo_4.png")
    Image.new("RGB", (1200, 800), PAPER).save(d / "photo_5.png", dpi=(300, 300))
    return d


@pytest.fixture(scope="module")
def many(tmp_path_factory):
    d = tmp_path_factory.mktemp("r11many")
    for i in range(18):
        _one(d / f"photo_{i + 1:02d}.png")
    return d


def _open(app, paths):
    close_all()
    app.go_home()
    app.open_paths(paths)
    pump(app, until=lambda: app.page == "process" and app.job is not None and app.job.processed
         and (app.batch is None or not app.batch.busy()), timeout=30)
    pump(app, 150)


def _select(app, name):
    b = app.batch
    i = next(k for k, j in enumerate(b.items) if j.path.name == name)
    app.select_photo(i)
    pump(app, until=lambda: app.job is b.items[i] and app.job.processed, timeout=15)
    pump(app, 100)


# ================================================================== 89: the reason inside the yellow card
def test_r89_no_separate_reason_widgets():
    from ui.pages import process_page as PPm
    src = inspect.getsource(PPm.ProcessPage)
    assert 'InfoBar(self, app, "note")' not in src and 'InfoBar(self, app, "reason")' not in src
    from ui.widgets.batch import InfoBar
    assert set(InfoBar.FILL) == {"warn", "ok", "info"}


def test_r89_infobar_lines_and_height(app):
    from ui.widgets.batch import InfoBar
    ib = InfoBar(app.process_page, app, "warn")
    ib.set("Требует внимания", "")
    assert ib.height() == 48.0 and ib.lines() == []
    ib.set("Требует внимания", "одна причина")
    assert ib.height() == pytest.approx(54.8) and ib.lines() == ["одна причина"]
    ib.set("Требует внимания", "первая\nвторая\nтретья")
    assert ib.lines() == ["первая", "вторая", "третья"]
    assert ib.height() == pytest.approx(54.8 + 2 * InfoBar.LINE)
    ib.destroy()


def test_r89_several_reasons_one_per_line():
    from core.i18n import I18n
    from ui.pages.process_page import doubt_text
    i = I18n(CSV, "ru")
    assert doubt_text(i.t, ("pale", "busy")).split("\n") == [i.t("batch.doubt.pale"), i.t("batch.doubt.busy")]


def test_r89_single_photo_doubt_reason_inside(app, tmp_path):
    p = tmp_path / "two.png"
    _two(p)
    _open(app, [p])
    pp = app.process_page
    assert app.batch is None and app.job.status == "doubt"
    wb = pp.warn_bar
    assert wb.visible and wb.title == "Требует внимания"
    assert wb.lines() == [app.t("batch.doubt.several")]
    assert not hasattr(pp, "note") and not hasattr(pp, "reason")
    assert pp.preview.ly + pp.preview.lh < wb.ly
    assert abs(wb.ly + wb.lh - (pp.lh - 64 - 16)) < 1                     # at the bottom of the column
    assert pp.meta_y < wb.ly


def test_r89_single_photo_not_found_reason_inside(app, tmp_path):
    p = tmp_path / "blank.png"
    Image.new("RGB", (1200, 800), PAPER).save(p, dpi=(300, 300))
    _open(app, [p])
    pp = app.process_page
    assert app.job.status == "attention"
    assert pp.warn_bar.title == "Требует внимания" and pp.warn_bar.msg == app.t("batch.reason_not_found")
    assert pp.bar.next.disabled


def test_r89_batch_doubt_and_not_found_reason_inside(app, mixed):
    _open(app, [mixed])
    pp = app.process_page
    b = app.batch
    assert b is not None and len(b.items) == 5
    _select(app, "photo_4.png")
    assert app.job.status == "doubt"
    wb = pp.warn_bar
    assert wb.visible and wb.action.visible and wb.title == app.tn("batch.attention_bar", 2)
    assert wb.lines() == [app.t("batch.doubt.several")]
    assert pp.preview.ly + pp.preview.lh < wb.ly < pp.strip.ly             # card between the image and the strip
    _select(app, "photo_5.png")
    assert app.job.status == "attention"
    assert wb.lines() == [app.t("batch.reason_not_found")]                  # no reason bar above the preview (40)
    assert pp.preview.ly == 52.0
    _select(app, "photo_1.png")                                             # a fine photo: remark 90 — title only
    assert wb.lines() == [] and wb.height() == 48.0


def test_r89_help_text_says_inside():
    r = rows()["help.batch.attention_text"]
    assert "а в ней — причина для выбранного фото" in r[2] and "под ней" not in r[2]
    assert "showing the reason for the selected photo" in r[3] and "below it" not in r[3]


# ================================================================== 88: no graphics card in the issue form
def test_r88_issue_body_without_gpu(app, monkeypatch):
    from ui import platform_win as pw
    assert not hasattr(pw, "gpu_names") and not hasattr(pw, "dx12_supported")
    monkeypatch.setattr(pw, "windows_version", lambda: "Windows 11 23H2 (build 22631)")
    body = urllib.parse.parse_qs(urllib.parse.urlparse(app.issue_url()).query)["body"][0]
    assert "Graphics" not in body and "DirectX" not in body
    assert body == "App version: 1.0\nWindows: Windows 11 23H2 (build 22631)\nLanguage: ru\n\nDescribe the problem:\n"
    r = rows()["issue.body"]
    assert "{gpu}" not in r[2] + r[3] and "{dx12}" not in r[2] + r[3]


# ================================================================== 87: template follows the language
def test_r87_template_follows_language_until_edited(app):
    close_all()
    app.go_home()
    app.settings.set("name_template", None)
    app.open_settings()
    pump(app, 60)
    sp = app.settings_page
    assert app.settings.name_template(app.t("settings.name_template.value")) == "подпись_{имя}"
    app.set_language_pref("en")
    pump(app, 60)
    sp = app.settings_page
    assert app.settings.name_template(app.t("settings.name_template.value")) == "signature_{name}"
    assert sp.name_box.get() == "signature_{name}"
    assert sp._apply_name("signature_{name}") and app.settings.get("name_template") is None   # default = not edited
    assert sp._apply_name("скан_{имя}")                                     # edited by hand
    app.set_language_pref("ru")
    pump(app, 60)
    sp = app.settings_page
    assert app.settings.get("name_template") == "скан_{имя}"
    assert app.settings.name_template(app.t("settings.name_template.value")) == "скан_{имя}"
    assert sp.name_box.get() == "скан_{имя}"
    app.set_language_pref("en")
    pump(app, 60)
    assert app.settings.name_template(app.t("settings.name_template.value")) == "скан_{имя}"   # stays as edited
    assert app.settings_page._apply_name("signature_{name}")               # typing the default again
    app.set_language_pref("ru")
    pump(app, 60)
    assert app.settings.name_template(app.t("settings.name_template.value")) == "подпись_{имя}"  # follows again
    app.settings.set("name_template", None)
    app.close_settings() if hasattr(app, "close_settings") else None
    pump(app, 30)


# ================================================================== 86: the strip scrollbar
def test_r86_strip_bar_widens_and_narrows(app, many):
    from ui.widgets import scroll as SC
    _open(app, [many])
    s = app.process_page.strip
    bar = s.bar
    assert s.content_w() > s.view_w()
    assert bar.lh == SC.ZONE_W and bar.t == 0 and not bar.arrows_shown()
    x, y, w, h = bar.thumb_rect()
    assert h == SC.REST_W                                                   # 2 px line at rest
    rest_y = s.bar.ly + y
    from ui.widgets.batch import FILM_TOP, TILE
    assert 3.5 <= rest_y - (FILM_TOP + TILE) <= 6                           # ≈ 4 px under the tiles
    bar._on_enter(None)
    seen = []
    _wait(app, lambda: (seen.append(bar.t), bar.t == 1)[1])
    assert bar.t == 1 and any(0 < v < 1 for v in seen)                      # smooth
    assert bar.thumb_rect()[3] == SC.WIDE_W and bar.arrows_shown()
    tx, ty, tw, th = bar.thumb_rect()
    assert abs((ty + th / 2) - SC.ZONE_W / 2) < 1e-6                         # 6 px thumb centred in the track
    bar._on_leave(None)
    pump(app, 600)
    assert bar.t == 1                                                       # still wide after 0.6 s
    assert _wait(app, lambda: bar.t == 0, timeout=2.5)


def test_r86_strip_bar_arrows_track_and_drag(app, many):
    from ui.widgets import scroll as SC
    from ui.widgets.batch import PITCH
    if app.batch is None or len(app.batch.items) != 18:
        _open(app, [many])
    s = app.process_page.strip
    bar = s.bar
    s.scroll_to(0)
    bar._on_enter(None)
    _wait(app, lambda: bar.t == 1)

    class E:
        def __init__(self, x, y=6):
            self.x, self.y = x, y

    bar._on_press(E(bar.lw - 6))                                            # right arrow: one tile
    assert s.scroll == pytest.approx(PITCH)
    pump(app, 700)
    assert s.scroll > PITCH                                                 # repeats while held
    bar._on_release(E(bar.lw - 6))
    v = s.scroll
    pump(app, 200)
    assert s.scroll == v
    bar._on_press(E(8))                                                     # left arrow
    bar._on_release(E(8))
    assert s.scroll == pytest.approx(v - PITCH)
    s.scroll_to(0)
    tx, ty, tw, th = bar.thumb_rect()
    bar._on_press(E(tx + tw + 40))                                          # track: one page
    bar._on_release(E(tx + tw + 40))
    assert s.scroll > PITCH
    s.scroll_to(0)
    tx, ty, tw, th = bar.thumb_rect()
    bar._on_press(E(tx + 5))
    bar._move(E(tx + 5 + 60))
    assert s.scroll > 0
    bar._on_release(E(tx + 65))
    assert hasattr(s, "film") and s.film.visible                            # the round «‹» / «›» buttons stay
    src = inspect.getsource(type(s.film))
    assert '"next"' in src and '"prev"' in src
    bar._on_leave(None)
