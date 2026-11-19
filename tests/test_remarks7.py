import hashlib
"""Remarks 46–58 (2026-11-18, «Вноси правки»): update «Отмена» width (46), Settings colour card (47),
«Требует внимания» for doubts (48), help texts (49), «Толщина DXF» (50), Export card order (51), blue ink
over a stamp (52), a separate flourish (53), DPI 72 (54), print / stamp next to blue ink (55, 56),
crossed strokes in the auto frame (57), swatches wrap + «Удалить цвет» on screen 3 (58)."""
import csv
import glob
import importlib
import io
import json
import os
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from core import batch as B
from core import export as ex
from core import processing as P

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "i18n" / "strings_ru_en.csv"
PROMPT_CSV = Path("/workspace/prompt/v2/i18n/strings_ru_en.csv")
R48 = Path("/workspace/rewrite/r48_try")


def rows():
    return {r[0]: r for r in csv.reader(CSV.open(encoding="utf-8-sig", newline=""))}


# ================================================================== synthetic photos
PAPER = (239, 236, 227)
BLUE = (30, 45, 140)
RED = (200, 40, 40)


def _signature(d, ox=0, oy=0, color=BLUE, width=8):
    pts = [(150 + ox + 55 * k, 300 + oy + (55 if k % 2 else -55)) for k in range(9)]
    d.line(pts, fill=color, width=width, joint="curve")


def _photo(size=(1000, 640)):
    return Image.new("RGB", size, PAPER)


def _process(img, dpi=300.0, frame=None, **kw):
    ph = P.prepare_photo(img, dpi, "t.png")
    return ph, P.process(ph, P.ProcessParams(**kw), frame=frame)


# ------------------------------------------------------------------ 54
def test_r54_dpi_72_and_absurd_values_count_as_missing():
    for v, exp in ((72, None), (72.0, None), (50, None), (96, 96.0), (300, 300.0), (299.9994, 299.9994),
                   (10000, None), ((72, 72), None), ((600, 600), 600.0)):
        im = Image.new("RGB", (10, 10))
        im.info["dpi"] = v
        assert P.read_dpi(im) == exp, v
    buf = io.BytesIO()
    _photo((200, 100)).save(buf, "JPEG", dpi=(72, 72))
    img, dpi = P.load_image_bytes(buf.getvalue())
    assert dpi is None


# ------------------------------------------------------------------ 52 / 56
def _stamped(blue_share=True):
    im = _photo()
    d = ImageDraw.Draw(im)
    for r in (230, 200, 140):          # a big red stamp …
        d.ellipse((260 - r, 330 - r, 260 + r, 330 + r), outline=RED, width=10)
    d.polygon([(260, 220), (300, 380), (170, 290), (350, 290), (220, 380)], outline=RED, width=8)
    _signature(d, ox=40, oy=10)          # … with a blue signature over it
    return im


def test_r52_blue_ink_is_preferred_over_a_red_stamp():
    ph, r = _process(_stamped())
    assert r.ink_state == "found"
    hue, chroma = P.lab_hue_chroma(r.ink_rgb)
    assert P.BLUE_HUE[0] <= hue < P.BLUE_HUE[1], r.ink_rgb
    # remark 56: the stamp rings are not in the result
    rgb = ph.rgb[r.mask].astype(int)
    reddish = (rgb[:, 0] - rgb[:, 2] > 40).mean()
    assert reddish < 0.02, reddish


def test_r52_red_ink_alone_is_still_found():
    im = _photo()
    _signature(ImageDraw.Draw(im), color=RED)
    _ph, r = _process(im)
    assert r.ink_state == "found" and r.stroke_count >= 1
    assert "stamp_ink" in r.doubts              # 48, criterion 6: the ink has a stamp colour


# ------------------------------------------------------------------ 55
def test_r55_print_next_to_blue_ink_is_dropped():
    im = _photo()
    d = ImageDraw.Draw(im)
    _signature(d)
    for y in (380, 410):                 # dark grey «printed» lines crossing the signature area
        for x in range(120, 700, 18):
            d.rectangle((x, y, x + 10, y + 12), fill=(40, 40, 44))
    ph, r = _process(im)
    rgb = ph.rgb[r.mask].astype(int)
    grey = (np.abs(rgb[:, 2] - rgb[:, 0]) < 15).mean()
    assert grey < 0.03, grey


# ------------------------------------------------------------------ 53 / 57
def test_r53_separate_flourish_is_inside_the_auto_frame():
    im = _photo((1200, 700))
    d = ImageDraw.Draw(im)
    _signature(d, ox=100, oy=-40)
    # underline ~10 mm below the signature, a hand-drawn arc (remark 72: a ruler-straight line that runs
    # past the signature on both ends is ruling and goes, see tests/test_remarks9.py)
    arc = [(180 + 720 * k / 40, 470 - 20 * k / 40 + 60 * (k / 40) * (1 - k / 40)) for k in range(41)]
    d.line(arc, fill=BLUE, width=7, joint="curve")
    ph, r = _process(im)
    fx, fy, fw, fh = r.frame
    assert fy + fh > 470 and fx < 180 and fx + fw > 900, r.frame
    assert r.stroke_count == 2


def test_r53_printed_text_line_is_not_a_flourish():
    im = _photo((1200, 700))
    d = ImageDraw.Draw(im)
    _signature(d, ox=100, oy=-40)
    for x in range(200, 860, 22):        # a line of «letters» under the signature
        d.rectangle((x, 455, x + 12, 470), fill=BLUE)
    _ph, r = _process(im)
    fx, fy, fw, fh = r.frame
    assert fy + fh < 455, r.frame


def test_r57_auto_frame_takes_crossed_strokes_whole():
    m = np.zeros((400, 600), bool)
    m[100:300, 200:400] = False
    yy, xx = np.ogrid[:400, :600]
    m |= (np.abs(yy - 200) < 4) & (xx > 220) & (xx < 420)       # main stroke
    m |= (np.abs(yy - 170) < 4) & (xx > 150) & (xx < 260)       # separate stroke reaching 15 px left of the box
    m |= (np.abs(yy - 230) < 4) & (xx > 240) & (xx < 400)
    x, y, w, h = P.auto_frame_for(m, 300.0)
    assert x <= 150 - 4, (x, y, w, h)


def test_r57_tight_crop_png_is_not_cut():
    im = Image.new("RGBA", (500, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line([(0, 250), (499, 40)], fill=(30, 50, 255, 255), width=6)    # touches both edges
    d.line([(40, 60), (120, 200), (200, 60)], fill=(30, 50, 255, 255), width=6)
    ph, r = _process(im, dpi=None)
    full = P.process(ph, P.ProcessParams(), frame=(0, 0, 500, 300)).mask
    assert int(full.sum()) - int(r.mask.sum()) <= 2
    assert r.doubts == ()                        # 48: the photo edge does not count as a cut


# ------------------------------------------------------------------ 48: criteria
def test_r48_clean_signature_has_no_doubts():
    im = _photo()
    _signature(ImageDraw.Draw(im))
    _ph, r = _process(im)
    assert r.stroke_count >= 1 and r.doubts == ()


def test_r48_pale_signature():
    im = _photo()
    _signature(ImageDraw.Draw(im), color=(188, 191, 217))     # darkness ≈ 42 of 255
    _ph, r = _process(im, sensitivity=100)
    assert r.stroke_count >= 1 and "pale" in r.doubts


def test_r48_busy_background():
    im = _photo()
    d = ImageDraw.Draw(im)
    _signature(d)
    rng = np.random.default_rng(3)
    for x in range(160, 640, 40):           # remark 68: only fragments > 1 mm² count (15 px ≈ 1.4 mm²)
        for y in range(385, 545, 40):
            d.ellipse((x, y, x + 15, y + 15), fill=BLUE)
    _ph, r = _process(im, denoise=0)
    assert "busy" in r.doubts


def test_r48_cut_by_user_frame_is_not_reported_but_auto_cut_is():
    im = _photo()
    _signature(ImageDraw.Draw(im))
    ph, r = _process(im, frame=(300, 200, 120, 200))
    assert "cut" not in r.doubts and "several" not in r.doubts       # the user drew this frame
    dark = P._darkness(ph, True)
    mask = r.mask
    pre = P.process(ph, P.ProcessParams(), frame=(0, 0, 1000, 640)).mask
    assert "cut" in P.assess_doubts(ph, dark, mask, (300, 200, 120, 200), pre, None, auto_frame=True)


def test_r48_too_few_and_dense():
    im = _photo((2000, 1400))
    ImageDraw.Draw(im).ellipse((990, 690, 1000, 700), fill=BLUE)
    _ph, r = _process(im, denoise=0)
    assert r.stroke_count >= 1 and "few" in r.doubts
    im = _photo()
    d = ImageDraw.Draw(im)
    for k in range(0, 160, 7):            # dense hatching: strokes cover most of the frame
        d.line([(300, 200 + k), (520, 200 + k)], fill=BLUE, width=5)
    _ph, r = _process(im)
    assert "dense" in r.doubts


def test_r48_several_signatures():
    im = _photo((1800, 640))
    d = ImageDraw.Draw(im)
    _signature(d)
    _signature(d, ox=900)
    _ph, r = _process(im)
    assert "several" in r.doubts


def test_r48_stamp_under_signature_is_a_doubt():
    _ph, r = _process(_stamped())
    assert "stamp_ink" in r.doubts


def test_r48_job_status_doubt_does_not_block_export():
    bt = B.Batch()
    bt.items = [B.Job(path=Path(f"/x/{i}.jpg")) for i in range(3)]
    for j in bt.items:
        j.done_version, j.stroke_count = j.version, 3
    bt.items[1].doubts = ("pale",)
    bt.note_attention()
    assert [j.status for j in bt.items] == ["ready", "doubt", "ready"]
    assert bt.bar_state() == "warn" and len(bt.attention()) == 1 and bt.blocking() == []
    assert bt.ready_for_export()                 # doubts never block
    assert bt.next_attention() == 1
    bt.items[2].stroke_count = 0                 # not found → blocks, as before
    assert not bt.ready_for_export() and len(bt.attention()) == 2


def test_r48_apply_result_copies_doubts(tmp_path):
    im = _photo((1800, 640))
    d = ImageDraw.Draw(im)
    _signature(d)
    _signature(d, ox=900)
    ph, r = _process(im)
    j = B.Job(path=tmp_path / "a.jpg")
    j.apply_result(ph, r, j.version)
    assert j.status == "doubt" and "several" in j.doubts


# ------------------------------------------------------------------ regression on the user's photos (if present)
@pytest.mark.skipif(not (R48 / "zip3").exists(), reason="user test photos not on this machine")
def test_r48_clean_photoshop_pngs_pass_and_photos_with_stamps_are_marked():
    files = sorted(glob.glob(str(R48 / "zip3" / "*" / "*.png")))
    assert len(files) == 59
    marked = {}
    for f in files:
        img, dpi = P.load_image(Path(f))
        ph = P.prepare_photo(img, dpi, Path(f).name)
        r = P.process(ph, P.ProcessParams())
        assert r.stroke_count > 0, f
        if r.doubts:
            marked[Path(f).name] = r.doubts
        if hashlib.md5(Path(f).name.encode()).hexdigest() == "3982a02b317e8a239158fbb80cf8c68a":   # local photo 4          # 57: the tip of «Л» is no longer cut
            H, W = r.mask.shape
            full = P.process(ph, P.ProcessParams(), frame=(0, 0, W, H)).mask
            assert int(full.sum()) == int(r.mask.sum())
    assert marked == {}
    for name in ("p3.jpg", "p4.jpg"):
        img, dpi = P.load_image(R48 / name)
        assert dpi is None                                # 54: the files say 72 DPI
        r = P.process(P.prepare_photo(img, dpi, name), P.ProcessParams())
        assert r.doubts, name
        if name == "p3.jpg":                              # 52 / 53: the blue pen, with the underline
            hue, _c = P.lab_hue_chroma(r.ink_rgb)
            assert P.BLUE_HUE[0] <= hue < P.BLUE_HUE[1] and r.stroke_count <= 3


# ================================================================== i18n / help (47, 49, 50, 58)
def test_r46_58_i18n_rows_and_csv_identity():
    r = rows()
    assert len(r) >= 340          # remark 59–71 added rows (test_remarks8)
    assert CSV.read_bytes() == PROMPT_CSV.read_bytes()
    assert r["settings.add_color"][2:4] == ["Добавить цвет", "Add color"]
    assert r["settings.delete_color.title"][2:4] == ["Удалить цвет «{name}»?", "Delete color “{name}”?"]
    assert r["settings.delete_color.default_note"][2] == "По умолчанию станет {name}"
    assert r["color.example_burgundy"][2:4] == ["Бордо", "Burgundy"]
    assert r["settings.dxf_line"][2:4] == ["Толщина DXF", "DXF thickness"]
    assert r["settings.dxf_line.desc"][2:4] == ["Толщина линий в DXF-файле, в миллиметрах",
                                                "Line thickness in the DXF file, in millimeters"]
    assert r["export.color.delete"][2:4] == ["Удалить цвет", "Delete color"]


def test_r49_help_texts():
    r = rows()
    assert r["help.process.frame2"][2].startswith("Чтобы изменить рамку, нажмите «Рамка области»")
    assert "Ctrl+Z и Ctrl+Y" in r["help.process.eraser"][2] and "Ctrl+Z and Ctrl+Y" in r["help.process.eraser"][3]
    assert "(Ctrl+V)" in r["help.prep.add_text"][2] and "«Пакетная обработка папки»" in r["help.prep.add_text"][2]
    assert "«Удалить шаблон»" in r["help.formats.size_templates"][2]
    assert r["help.formats.toggles"][2].startswith("Каждый формат включается переключателем")
    assert "«Проверить сейчас»" in r["help.start.privacy_text"][2]
    assert "после подтверждения" in r["help.batch.all_text"][2]
    assert "программа сначала спросит «Начать заново?»." in r["help.batch.add_remove_text"][2]
    assert r["help.start.settings"][2:4] == ["Параметры", "Settings"]
    assert "разрешение PNG, толщина линий SVG и DXF, папка" in r["help.start.settings_text"][2]
    assert "PNG resolution, SVG and DXF line thickness, save location" in r["help.start.settings_text"][3]
    assert "(по умолчанию — «Спрашивать»)" in r["help.batch.exists_text"][2]
    for k in ("png_res", "svg_thickness", "png_margin", "dxf_text"):
        assert r[f"help.formats.{k}"][2].endswith("Значение по умолчанию задаётся в параметрах."), k
        assert r[f"help.formats.{k}"][3].endswith("The default is set in Settings."), k
    assert "(по умолчанию подпись_{имя})" in r["help.batch.save_text"][2]
    assert r["help.formats.color"][2].endswith("в Параметрах › Экспорт › «Цвет подписи по умолчанию».")
    # 48: the help text is unchanged
    assert r["help.batch.attention_text"][2].startswith("Если программа не уверена в результате")


def test_r49_help_start_has_settings_card():
    from ui.dialogs import formats_help as FH
    from core.i18n import I18n
    t = I18n(CSV, "ru").t
    titles = FH.card_titles(FH._start(t))
    assert titles[-1] == "Параметры"


# ================================================================== UI (real app under X)
@pytest.fixture(scope="module")
def app(tmp_path_factory):
    if not os.environ.get("DISPLAY"):
        pytest.skip("no X display")
    tmp = tmp_path_factory.mktemp("appdata_r7")
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


def close_all():
    from ui.widgets.overlay import Popup
    while Popup.current is not None:
        Popup.close_current()


def settings(app):
    close_all()
    if not app.settings_open:
        app.open_settings()
    pump(app, 60)
    return app.settings_page


def test_r46_cancel_button_normal_width_on_the_right(app):
    from ui.dialogs.update import UpdateDialog
    from ui.widgets.controls import Button
    dlg = UpdateDialog(app, "1.1", lambda: None, lambda: None, lambda: None)
    pump(app, 30)
    two = [w for w in dlg.widgets if isinstance(w, Button)]
    w2 = two[0].lw
    dlg.start_download()
    pump(app, 30)
    btns = [w for w in dlg.widgets if isinstance(w, Button)]
    assert len(btns) == 1 and abs(btns[0].lw - w2) < 1.0
    assert abs((btns[0].lx + btns[0].lw) - (two[1].lx + two[1].lw)) < 1.0     # right edge as «Позже»
    dlg.close()


def test_r51_export_card_order(app):
    sp = settings(app)
    exp = dict(sp.groups)["shell.step.export"]
    assert exp == [sp.c_formats, sp.c_sizes, sp.c_margin, sp.c_color, sp.c_dpi, sp.c_svg, sp.c_dxf]


def test_r50_dxf_card_sets_the_default_and_screen3_remembers_quick_change(app):
    sp = settings(app)
    assert sp.dxf_line_box.get() == "0,18"
    assert str(sp.dxf_line_box.entry.cget("justify")) == "left"
    assert sp._apply_dxf_line("0,35") is True and app.settings.get("dxf_line_mm") == 0.35
    assert sp._apply_dxf_line("9") is False
    app.settings.set("last_export", {"dxf_line_mm": 0.5})
    assert ex.resolve_dxf_line(app.settings.get("last_export"), app.settings.get("dxf_line_mm")) == 0.5
    sp._apply_dxf_line("0,25")                                    # Settings change forgets the quick value
    assert "dxf_line_mm" not in app.settings.get("last_export")
    assert ex.resolve_dxf_line(app.settings.get("last_export"), app.settings.get("dxf_line_mm")) == 0.25
    app.settings.reset_to_defaults()
    assert app.settings.get("dxf_line_mm") == 0.18


def test_r47_colour_card_rows_menu_and_delete(app):
    from ui.widgets.overlay import Popup
    app.settings.set("custom_colors", [{"id": "1", "name": "Бордо", "hex": "#7A1F2B"}])
    app.settings.set("default_color", "custom:1")
    sp = settings(app)
    sp.c_color.is_open = True
    sp.sync()
    pump(app, 40)
    items = sp._color_items()
    assert [k for k, *_ in items][:5] == [k for k, _ in ex.BUILTIN_COLORS] and items[-1][0] == "custom:1"
    assert sp._color_summary() == "Бордо"
    assert sp.c_color.height() == sp.c_color.head_h() + sp._colors_body_h()
    assert sp.btn_add_color.winfo_ismapped() and all(b.winfo_ismapped() for b in sp.color_more[:len(items)])
    sp._color_menu(2)                                             # built-in: only «Сделать по умолчанию»
    pump(app, until=lambda: Popup.current is not None, timeout=2)
    assert [(it.text, bool(it.disabled)) if it else None for it in Popup.current.items] == [("Сделать по умолчанию", False)]
    close_all()
    sp._color_menu(len(items) - 1)                                # own default colour
    pump(app, until=lambda: Popup.current is not None, timeout=2)
    assert [(it.text, bool(it.disabled)) if it else None for it in Popup.current.items] == [
        ("Сделать по умолчанию", True), ("Изменить", False), None, ("Удалить", False)]
    close_all()
    dlg = sp._delete_color("custom:1")
    assert "Бордо" in "".join(dlg.title_lines)
    assert "По умолчанию станет Синий" in "".join(t for ln in dlg.lines for t, _ in ln)
    dlg._activate(1)                                              # «Отмена»
    assert app.settings.get("custom_colors")
    dlg = sp._delete_color("custom:1")
    dlg._activate(0)
    pump(app, 30)
    assert app.settings.get("custom_colors") == [] and app.settings.get("default_color") == ex.DEFAULT_COLOR_KEY


def test_r47_edit_colour_dialog_prefilled(app):
    from ui.dialogs.color_dialog import CustomColorDialog
    from ui.dialogs import colors as C
    app.settings.set("custom_colors", [{"id": "4", "name": "Фиолетовый", "hex": "#3A2F8F"}])
    sp = settings(app)
    sp._edit_color("custom:4")
    pump(app, 40)
    from ui.widgets.overlay import Popup
    dlg = Popup.current
    assert isinstance(dlg, CustomColorDialog)
    assert dlg.f_name.get() == "Фиолетовый" and dlg.f_hex.get().upper() == "#3A2F8F"
    assert [b[0] for b in dlg.buttons_spec] == ["Отмена", "Сохранить"]
    dlg.f_name.set("Мой фиолетовый")
    dlg.submit()
    pump(app, 30)
    assert C.custom_colors(app)[0]["name"] == "Мой фиолетовый" and C.custom_colors(app)[0]["id"] == "4"
    app.settings.set("custom_colors", [])


def test_r58_swatches_wrap_and_delete_link(app):
    from ui.pages import export_page as EP
    app.settings.set("custom_colors", [{"id": str(i), "name": f"Цвет {i}", "hex": "#%02X3050" % (i * 20)}
                                       for i in range(1, 11)])
    if app.export_page is None:
        from ui.pages.export_page import ExportPage
        app.export_page = ExportPage(app.root, app)
    ep = app.export_page
    ep.changed = lambda: None                                      # no photo here: layout only
    ep.color_key = ex.DEFAULT_COLOR_KEY
    ep.color_open = True
    ep.c_color.rebuild()
    ep.c_color.layout(0, 0, 424)
    per = ep.c_color.per_row(424)
    assert len(ep.c_color.swatches) == 16 and per < 16 and ep.c_color.rows == 2
    xs = [s.lx + s.lw for s in ep.c_color.swatches]
    assert max(xs) <= 424 - 15 + 2                                 # nothing past the card edge
    assert not ep.c_color.delete_link.winfo_ismapped() or ep.c_color.delete_link.lw == 0
    h_builtin = ep.c_color.body_h
    ep.color_key = "custom:3"
    ep.c_color.layout(0, 0, 424)
    assert ep.c_color.body_h == h_builtin + EP.COLOR_DELETE_ROW_H
    assert ep.c_color.delete_link.label == "Удалить цвет"
    dlg = ep.ask_delete_color("custom:3")
    assert dlg is not None
    dlg._activate(0)
    pump(app, 30)
    assert ep.color_key == ex.DEFAULT_COLOR_KEY and len(app.settings.get("custom_colors")) == 9
    assert ep.ask_delete_color("blue") is None                    # built-in colours are not deleted
    close_all()
    app.settings.set("custom_colors", [])


def test_r49_help_page_renders_settings_card(app):
    close_all()
    if app.settings_open:
        app.close_settings()
    app.open_help("start") if hasattr(app, "open_help") else None
    pump(app, 60)
    from ui.dialogs import formats_help as FH
    assert "Параметры" in FH.card_titles(FH._start(app.t))
