"""Remarks 59–71 (2026-11-18): auto frame prefers a signature over handwritten text (59), help texts (60, 61,
69), reasons under the yellow bar (62, 70), stamps vs. ink (63–65), «Исключить цвет» (66), table borders (67),
the «Сложный фон» threshold (68) and ⋯ › «Начать заново» (71)."""
import csv
import importlib
import json
import os
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from core import processing as P
from tests.i18n_prompt_diff import assert_matches_prompt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "i18n" / "strings_ru_en.csv"
PROMPT_CSV = Path("/workspace/prompt/v2/i18n/strings_ru_en.csv")
R48 = Path("/workspace/rewrite/r48_try")
PAPER = (239, 236, 227)
BLUE = (30, 45, 140)
DARK = (38, 32, 34)
STAMP = (110, 150, 205)       # light azure stamp (L* ≈ 60)


def rows():
    return {r[0]: r for r in csv.reader(CSV.open(encoding="utf-8-sig", newline=""))}


def _photo(size=(1000, 640)):
    return Image.new("RGB", size, PAPER)


def _signature(d, ox=0, oy=0, color=BLUE, width=8):
    pts = [(150 + ox + 55 * k, 300 + oy + (55 if k % 2 else -55)) for k in range(9)]
    d.line(pts, fill=color, width=width, joint="curve")


def _process(img, dpi=300.0, frame=None, **kw):
    ph = P.prepare_photo(img, dpi, "t.png")
    return ph, P.process(ph, P.ProcessParams(**kw), frame=frame)


def _stamp(d, cx=420, cy=300, color=STAMP):
    for r, w in ((230, 16), (170, 8)):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=w)
    for k in range(10):
        d.rectangle((cx - 140 + 28 * k, cy - 20, cx - 128 + 28 * k, cy + 20), fill=color)


def _sig_mask(img_size, **kw):
    im = Image.new("L", img_size, 0)
    _signature(ImageDraw.Draw(im), color=255, **kw)
    return np.asarray(im) > 0


# ------------------------------------------------------------------ 63, 64, 65
def test_r63_dark_signature_over_light_blue_stamp_is_the_ink():
    im = _photo()
    d = ImageDraw.Draw(im)
    _stamp(d)
    _signature(d, color=DARK, width=14)
    _ph, r = _process(im)
    assert r.ink_state == "found"
    assert max(r.ink_rgb) < 90                       # the pen, not the stamp (110, 150, 205)
    sig = _sig_mask(im.size, width=14)
    assert (r.mask & sig).sum() >= 0.85 * sig.sum()
    ring = np.zeros(sig.shape, bool)
    ring[60:110, 380:460] = True                    # top of the outer ring, far from the signature
    assert (r.mask & ring).sum() == 0
    assert "ink_stamp" in r.doubts                  # remark 65: marked, export open


def test_r64_light_blue_group_is_not_preferred_over_dark_ink():
    im = _photo()
    d = ImageDraw.Draw(im)
    _stamp(d)
    _signature(d, color=DARK, width=14)
    ph = P.prepare_photo(im, 300.0, "t.png")
    core = P._soft_alpha(P._darkness(ph, True), P.DEFAULT_SENSITIVITY) > 0.5
    raw, sep = P._detect_ink_raw(ph, core)
    assert P._lab_l(raw) > P.BLUE_MAX_L or raw[2] < 120     # the light blue median is not taken as «blue ink»
    rgb, sep, stamp_like = P.detect_ink_ex(ph, core)
    assert stamp_like and sep and max(rgb) < 90


def test_r65_light_blue_auto_ink_is_marked_and_clean_blue_is_not():
    im = _photo()
    _signature(ImageDraw.Draw(im), color=(105, 140, 200))
    _ph, r = _process(im)
    assert "ink_stamp" in r.doubts
    im = _photo()
    _signature(ImageDraw.Draw(im))
    _ph, r = _process(im)
    assert r.doubts == ()


# ------------------------------------------------------------------ 66
def test_r66_exclude_colour_removes_a_same_hue_lighter_stamp_in_manual_mode():
    im = _photo()
    d = ImageDraw.Draw(im)
    _stamp(d, color=(70, 90, 175))
    _signature(d)
    ph = P.prepare_photo(im, 300.0, "t.png")
    ring = np.zeros((640, 1000), bool)
    ring[60:110, 380:460] = True
    base = P.process(ph, P.ProcessParams(ink_mode="manual", ink_rgb=BLUE))
    ex_ = P.process(ph, P.ProcessParams(ink_mode="manual", ink_rgb=BLUE, exclude_rgb=(70, 90, 175)))
    sig = _sig_mask(im.size)
    assert (ex_.mask & ring).sum() < 0.2 * max(1, (base.mask & ring).sum()) or (base.mask & ring).sum() == 0
    assert (ex_.mask & sig).sum() >= 0.7 * sig.sum()
    # auto mode ignores the excluded colour
    a1 = P.process(ph, P.ProcessParams())
    a2 = P.process(ph, P.ProcessParams(exclude_rgb=(70, 90, 175)))
    assert np.array_equal(a1.mask, a2.mask)


def test_r66_exclude_weight_is_soft_and_symmetric():
    im = _photo((40, 10))
    a = np.asarray(im).copy()
    a[:, :20] = BLUE
    a[:, 20:] = (120, 150, 210)
    ph = P.prepare_photo(Image.fromarray(a), 300.0, "t.png")
    w = P.exclude_weight(ph, BLUE, (120, 150, 210))
    assert w[:, :20].min() == 1.0 and w[:, 20:].max() == 0.0


# ------------------------------------------------------------------ 67
def _table(d, x0=40, y0=60, cols=(0, 420, 900), rows_=(0, 130, 300, 470), color=DARK, width=5):
    for c in cols:
        d.line((x0 + c, y0, x0 + c, y0 + rows_[-1]), fill=color, width=width)
    for r in rows_:
        d.line((x0, y0 + r, x0 + cols[-1], y0 + r), fill=color, width=width)


def test_r67_table_borders_are_found_and_a_lone_long_stroke_is_not():
    im = Image.new("L", (1000, 640), 0)
    d = ImageDraw.Draw(im)
    _table(d, color=255)
    m = np.asarray(im) > 0
    lines = P.long_lines(m, 300 / 25.4)
    assert lines is not None and lines.sum() >= 0.9 * m.sum()
    im = Image.new("L", (1000, 640), 0)
    ImageDraw.Draw(im).line((100, 300, 900, 310), fill=255, width=6)    # an underline alone stays
    assert P.long_lines(np.asarray(im) > 0, 300 / 25.4) is None


def test_r67_auto_frame_does_not_take_the_whole_table():
    im = _photo((1100, 640))
    d = ImageDraw.Draw(im)
    _table(d, color=DARK)
    # a signature in the right cell of the middle row and a printed word in the left cell
    pts = [(520 + 45 * k, 280 + (45 if k % 2 else -45)) for k in range(9)]
    d.line(pts, fill=DARK, width=7, joint="curve")
    for k in range(6):
        d.rectangle((90 + 40 * k, 250, 115 + 40 * k, 290), fill=DARK)
    _ph, r = _process(im, ink_filter=False)
    x, y, w, h = r.frame
    assert x > 430 and w < 560 and h < 300, r.frame


# ------------------------------------------------------------------ 59
def test_r59_signature_beats_a_bigger_cluster_of_handwritten_letters():
    im = _photo((1900, 700))
    d = ImageDraw.Draw(im)
    _signature(d)                                        # ~ 440 × 110 px, one stroke
    for row in range(3):                                 # a name + date: many small letters, more ink
        for k in range(24):
            x, y = 1000 + 34 * k, 180 + 90 * row
            d.ellipse((x, y, x + 22, y + 36), outline=BLUE, width=6)
    ph = P.prepare_photo(im, 300.0, "t.png")
    r = P.process(ph, P.ProcessParams())
    letters = np.zeros(r.mask.shape, bool)
    letters[:, 990:] = True
    full = P.process(ph, P.ProcessParams(), frame=(0, 0, 1900, 700)).mask
    assert (full & letters).sum() > (full & ~letters).sum()     # the letters hold more ink …
    x, y, w, h = r.frame
    assert x + w < 990, r.frame                                 # … but the frame is on the signature
    assert "several" in r.doubts


# ------------------------------------------------------------------ 68
def test_r68_tiny_specks_do_not_make_a_busy_background():
    im = _photo()
    d = ImageDraw.Draw(im)
    _signature(d)
    for x in range(160, 640, 12):
        for y in range(385, 545, 12):
            d.ellipse((x, y, x + 5, y + 5), fill=BLUE)          # ≈ 0.15 mm² each
    _ph, r = _process(im, denoise=0)
    n = int(r.mask[:, :].sum())
    assert n > 0 and "busy" not in r.doubts


# ------------------------------------------------------------------ 62
def test_r62_reasons_one_per_line():
    from core.i18n import I18n
    from ui.pages.process_page import doubt_text
    i = I18n(CSV, "ru")
    assert doubt_text(i.t, ("pale", "several")) == ("Подпись бледная — проверьте, все ли штрихи на месте\n"   # 89
                                                   "На фото несколько подписей — проверьте, выбрана ли нужная")
    assert doubt_text(i.t, ("ink_stamp",)) == "Цвет чернил похож на печать — проверьте подпись"
    assert doubt_text(i.t, ()) == ""


# ------------------------------------------------------------------ i18n, help
def test_r59_71_i18n_rows_and_csv_identity():
    r = rows()
    assert len(r) == 346          # remark 78 removed 10 rows (tests/i18n_prompt_diff.py)
    assert_matches_prompt(CSV, PROMPT_CSV)     # remarks 77–85: approved differences only
    exp = {
        "batch.doubt.pale": ("Подпись бледная — проверьте, все ли штрихи на месте", "The signature is faint — check that all strokes are there"),
        "batch.doubt.busy": ("Сложный фон — в результат могли попасть лишние элементы", "Busy background — extra elements may be included"),
        "batch.doubt.cut": ("Рамка обрезает часть подписи", "The frame cuts off part of the signature"),
        "batch.doubt.few": ("Найдено слишком мало штрихов", "Too few strokes found"),
        "batch.doubt.dense": ("Штрихи занимают почти всю рамку — возможно, захвачен фон", "Strokes fill most of the frame — background may be included"),
        "batch.doubt.stamp_ink": ("Похоже на печать или красные чернила", "Looks like a stamp or red ink"),
        "batch.doubt.several": ("На фото несколько подписей — проверьте, выбрана ли нужная", "Several signatures in the photo — check the right one is selected"),
        "batch.doubt.ink_stamp": ("Цвет чернил похож на печать — проверьте подпись", "Ink color looks like a stamp — check the signature"),
        "process.filter.exclude": ("Исключить цвет", "Exclude color"),
        "process.filter.exclude_hint": ("Щёлкните по печати или фону, чтобы их убрать", "Click the stamp or background you want to remove"),
        "process.filter.exclude_note": ("Точки этого цвета убираются из подписи", "Dots of this color are removed from the signature"),
        "process.filter.exclude_clear": ("Не исключать цвет", "Stop excluding the color"),
        "menu.start_over": ("Начать заново", "Start over"),
    }
    for k, (ru, en) in exp.items():
        assert tuple(r[k][2:4]) == (ru, en), k
    assert set(P.DOUBT_CODES) == {k.split(".")[-1] for k in r if k.startswith("batch.doubt.")}


def test_r60_61_69_70_71_help_texts():
    r = rows()
    c = r["help.formats.color"][2]
    assert "Кнопка «+» добавляет свой цвет. Чтобы удалить свой цвет, выберите его и нажмите «Удалить цвет» под образцами или щёлкните по образцу правой кнопкой." in c
    assert c.endswith("«Цвет подписи по умолчанию».")
    assert "The + button adds a custom color. To delete a custom color, select it and click Delete color below the swatches, or right-click its swatch." in r["help.formats.color"][3]
    a = r["help.batch.attention_text"]
    assert "жёлтая панель (при одном фото — под изображением), а в ней — причина для выбранного фото" in a[2]   # 77, 89
    assert a[2].endswith("Если подпись не найдена, экспорт будет недоступен, пока вы не поправите или не уберёте это фото. Если есть сомнения, экспорт доступен, но фото стоит проверить.")
    assert a[3].endswith("If no signature is found, export is unavailable until you fix or remove that photo. If there are doubts, export is available, but check the photo.")
    assert r["help.batch.attention_reasons"][2].startswith("Возможные причины: подпись бледная")
    assert "«Цвет чернил похож на печать — проверьте подпись»" in r["help.process.ink_auto"][2]
    assert r["help.process.ink_exclude"][2].startswith("«Исключить цвет» (только в режиме «Вручную»)")
    assert r["help.process.frame1"][2].endswith("проверьте, что выбрана нужная.")
    assert r["help.prep.paper_text"][2].endswith("а лишнее уберите через «Исключить цвет».")
    assert r["help.process.frame4"][2].startswith("Линии таблиц и линовку рамка не учитывает.")
    assert r["process.meta.frame_large"][2] == "Если рамка охватывает больше половины листа, уменьшите её или уберите лишнее ластиком"   # 78, 85
    assert r["help.batch.add_remove_text"][2].endswith("Чтобы вернуться на начальный экран, выберите в меню ⋯ «Начать заново». Программа всегда спросит подтверждение, а без загруженных фото пункт неактивен.")
    assert r["help.batch.add_remove_text"][3].endswith("To go back to the start screen, choose Start over from the ⋯ menu. The app always asks you to confirm; with no photos loaded, the item is unavailable.")


def test_r69_help_builder_uses_the_new_keys():
    from core.i18n import I18n
    from ui.dialogs import formats_help as FH
    i = I18n(CSV, "ru")
    txt = json.dumps(FH._process(i.t), ensure_ascii=False, default=str)
    assert "точки этого цвета уберутся из подписи" in txt
    txt = json.dumps(FH._batch(i.t), ensure_ascii=False, default=str)
    assert "цвет чернил похож на печать." in txt


# ------------------------------------------------------------------ zip4 (user photos, local only)
@pytest.mark.skipif(not (R48 / "zip4").exists(), reason="user test photos not on this machine")
def test_r63_zip4_blue_stamp_photos_keep_the_signature():
    for name in ("IMG_20261118_194541.jpg", "IMG_20261118_194604.jpg"):
        img, dpi = P.load_image(R48 / "zip4" / name)
        ph = P.prepare_photo(img, dpi, name)
        r = P.process(ph, P.ProcessParams())
        assert max(r.ink_rgb) < 80, (name, r.ink_rgb)      # the pen, not the stamp (≈ 111, 143, 170)
        assert "ink_stamp" in r.doubts and "busy" not in r.doubts


# ================================================================== UI
@pytest.fixture(scope="module")
def app(tmp_path_factory):
    if not os.environ.get("DISPLAY"):
        pytest.skip("no X display")
    tmp = tmp_path_factory.mktemp("appdata_r8")
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


def pump(app, ms=50, until=None, timeout=15.0):
    end = time.time() + (timeout if until else ms / 1000)
    while time.time() < end:
        app.root.update()
        if until is not None and until():
            break
        time.sleep(0.01)


def close_all():
    from ui.widgets.overlay import Popup
    while Popup.current is not None:
        Popup.close_current()


def _menu_items(app):
    from ui.widgets.overlay import Popup
    app.open_more_menu()
    pump(app, 30)
    items = Popup.current.items
    close_all()
    return items


@pytest.fixture(scope="module")
def doubt_photo(tmp_path_factory):
    p = tmp_path_factory.mktemp("r8") / "two.png"
    im = _photo((1800, 640))
    d = ImageDraw.Draw(im)
    _signature(d)
    _signature(d, ox=900)
    im.save(p, dpi=(300, 300))
    return p


def test_r71_menu_order_and_disabled_on_screen1(app):
    close_all()
    app.go_home()
    pump(app, 30)
    items = _menu_items(app)
    texts = [it.text if it else None for it in items]
    assert texts[:4] == ["Открыть файл", "Добавить папку", "Начать заново", None]
    assert items[2].icon == "reset" and items[2].disabled
    assert app.start_over() is None                         # nothing to start over


def test_r70_single_photo_doubt_bar_and_reason(app, doubt_photo):
    close_all()
    app.go_home()
    app.open_paths([doubt_photo])
    pump(app, until=lambda: app.page == "process" and app.job is not None and app.job.processed)
    pump(app, 150)
    pp = app.process_page
    assert app.batch is None and app.job.status == "doubt" and "several" in app.job.doubts
    assert pp.warn_bar.visible and not pp.strip.visible
    assert pp.warn_bar.title == "Требует внимания" and not pp.warn_bar.action.visible
    assert "На фото несколько подписей" in pp.warn_bar.msg            # remark 89: the reason inside the card
    assert pp.preview.ly < pp.warn_bar.ly                             # remark 77: under the image
    assert not pp.bar.next.disabled                                 # export stays open


def test_r71_start_over_from_the_menu_always_asks(app, doubt_photo):
    close_all()
    if app.page != "process":
        app.open_paths([doubt_photo])
        pump(app, until=lambda: app.page == "process")
    items = _menu_items(app)
    assert not items[2].disabled
    app._work_token = app.work_token() if hasattr(app, "work_token") else None   # «saved» — still asks
    dlg = app.start_over()
    assert dlg is not None and dlg.title == "Начать заново?"
    dlg._activate(1)                                                # «Отмена»
    pump(app, 30)
    assert app.page == "process"
    dlg = app.start_over()
    dlg._activate(0)
    pump(app, 60)
    assert app.page == "import" and app.job is None and app.batch is None


def test_r66_exclude_block_only_in_manual_mode(app, doubt_photo):
    close_all()
    app.go_home()
    app.open_paths([doubt_photo])
    pump(app, until=lambda: app.page == "process" and app.job is not None and app.job.processed)
    pump(app, 100)
    pp = app.process_page
    card = pp.c_ink
    assert not card.ex_pick.visible and not card.ex_lines             # «Авто»: card unchanged
    h_auto = card.height()
    pp.set_param(ink_mode="manual", ink_rgb=BLUE)
    pump(app, until=lambda: app.job.processed and not app.job.busy)
    pump(app, 60)
    assert card.ex_pick.visible and not card.ex_swatch.visible and card.height() > h_auto
    assert card.ex_lines == ["Щёлкните по печати или фону, чтобы их убрать"]
    pp.toggle_exclude_pipette()
    assert pp.preview.pipette and pp.pipette_target == "exclude"
    assert card.ex_pick.text_color == "accent" and card.pick.text_color is None
    pp.toggle_pipette()                                              # only one eyedropper at a time
    assert pp.preview.pipette and pp.pipette_target == "ink" and card.ex_pick.text_color is None
    pp.toggle_exclude_pipette()
    pp.on_pipette((110, 150, 205))
    pump(app, until=lambda: app.job.processed and not app.job.busy)
    pump(app, 60)
    p = app.job.state.params
    assert p.exclude_rgb == (110, 150, 205) and p.ink_rgb == BLUE and p.ink_mode == "manual"
    assert card.ex_swatch.visible and card.ex_clear.visible and card.ex_swatch.color == "#6E96CD"
    assert card.ex_lines == ["Точки этого цвета убираются из подписи"]
    pp.clear_exclude()
    pump(app, until=lambda: app.job.processed and not app.job.busy)
    pump(app, 60)
    assert app.job.state.params.exclude_rgb is None and not card.ex_swatch.visible
    pp.set_param(ink_mode="auto")
    pump(app, 60)
    assert not card.ex_pick.visible
