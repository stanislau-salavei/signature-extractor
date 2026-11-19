"""Remarks 72–76 (2026-11-18): ink-coloured ruling is removed (72), tinted (yellow) paper and table forms (73),
one photo with no signature shows the yellow card under the image instead of dialog 30 (74), and the colour
clustering is repeatable (76). Remark 75 (AI) stays postponed."""
import os
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from core import processing as P
from core import ruling as R
from core import tinted as T

from tests.test_remarks8 import app, pump, close_all      # noqa: F401  (shared UI fixture)

PAPER = (246, 245, 241)
BLUE = (30, 45, 140)
from tests.i18n_prompt_diff import R48  # noqa: E402  (local photos; tests skip without them)
ZIP4 = R48 / "zip4"
PPM = 300 / 25.4


def _process(img, dpi=300.0):
    ph = P.prepare_photo(img, dpi, "t.png")
    return ph, P.process(ph, P.ProcessParams())


def _sig(d, ox=0, oy=0, color=BLUE, width=8):
    pts = [(400 + ox + 55 * k, 300 + oy + (55 if k % 2 else -55)) for k in range(9)]
    d.line(pts, fill=color, width=width, joint="curve")


# ------------------------------------------------------------------ 76
def test_r76_ink_detection_is_repeatable_whatever_the_rng_state():
    im = Image.new("RGB", (1200, 640), PAPER)
    d = ImageDraw.Draw(im)
    _sig(d)
    d.text((100, 500), "Иванов И.И. 12.03.2026", fill=(40, 40, 40))
    for k in range(12):
        d.ellipse((150 + 70 * k, 560, 170 + 70 * k, 580), fill=(150, 60, 60))
    out = []
    for seed in (1, 999, 31337):
        cv2.setRNGSeed(seed)
        _, r = _process(im)
        out.append((r.ink_rgb, tuple(r.frame), int(r.mask.sum()), r.ink_state, tuple(r.doubts)))
    assert out[0] == out[1] == out[2]


def test_r76_seed_is_set_in_the_code():
    src = (Path(P.__file__)).read_text(encoding="utf-8")
    assert "cv2.setRNGSeed(12345)" in src


# ------------------------------------------------------------------ 72
def _ruled(underline=False, own_stroke=False):
    im = Image.new("RGB", (1800, 700), PAPER)
    d = ImageDraw.Draw(im)
    _sig(d)
    if underline:           # ink-coloured ruler line far past both ends of the signature
        d.line((60, 330, 1740, 330), fill=BLUE, width=5)
    if own_stroke:          # the signature's own straight final stroke: starts inside the signature
        d.line((840, 300, 1060, 300), fill=BLUE, width=8)
    return im


def test_r72_ink_coloured_ruling_goes_crossings_stay_frame_is_the_signature():
    _, base = _process(_ruled())
    _, r = _process(_ruled(underline=True))
    bx, by, bw, bh = base.frame
    fx, fy, fw, fh = r.frame
    assert fx >= bx - 40 and fx + fw <= bx + bw + 40          # the line does not widen the frame
    assert r.mask[328:333, 60:300].sum() == 0 and r.mask[328:333, 1000:1740].sum() == 0
    assert r.stroke_count <= base.stroke_count + 1            # crossings kept: the signature is not cut apart
    assert r.mask.sum() >= 0.9 * base.mask.sum()
    assert "several" not in r.doubts


def test_r72_signatures_own_straight_stroke_stays():
    _, base = _process(_ruled())
    _, r = _process(_ruled(own_stroke=True))
    assert r.mask[296:305, 900:1050].sum() > 0.8 * 150 * 8      # the stroke is part of the signature
    assert r.frame[0] + r.frame[2] >= 1050


def test_r72_ruling_function_keeps_crossing_pixels():
    m = np.zeros((600, 1800), bool)
    m[300:305, 50:1750] = True                                   # ruling
    st = np.zeros((600, 1800), np.uint8)
    cv2.line(st, (850, 150), (950, 450), 1, 8)                  # a stroke crossing it
    m |= st > 0
    rl = R.ruling(m, PPM)
    assert rl is not None
    assert rl[300:305, 60:800].all() and rl[300:305, 1000:1740].all()
    assert not (rl & (st > 0))[300:305].any()                   # crossing pixels stay


def test_r72_short_line_inside_the_signature_is_not_ruling():
    m = np.zeros((600, 1800), bool)
    m[300:305, 700:1100] = True                                 # 34 mm, but no ink beyond: not lone, not past
    st = np.zeros((600, 1800), np.uint8)
    cv2.polylines(st, [np.array([[650 + 60 * k, 250 + (100 if k % 2 else 0)] for k in range(9)], np.int32)], False, 1, 8)
    m |= st > 0
    rl = R.ruling(m, PPM)
    assert rl is None or not rl[300:305, 720:1080].any()


# ------------------------------------------------------------------ 73
def test_r73_paper_tint_white_none_yellow_found():
    white = cv2.cvtColor(np.full((200, 200, 3), PAPER, np.uint8), cv2.COLOR_RGB2LAB)
    yellow = cv2.cvtColor(np.full((200, 200, 3), (236, 220, 140), np.uint8), cv2.COLOR_RGB2LAB)
    core = np.zeros((200, 200), bool)
    assert T.paper_tint(white, core) is None
    t = T.paper_tint(yellow, core)
    assert t is not None and t[2] >= T.PAPER_TINT_C and t[1] > 0.8      # tint direction ≈ +b (yellow)


def test_r73_tinted_path_not_used_on_white_paper():
    im = Image.new("RGB", (1200, 640), PAPER)
    _sig(ImageDraw.Draw(im))
    rgb = np.asarray(im)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    core = np.zeros(rgb.shape[:2], bool)
    core[180:420, 380:900] = True
    assert T.tinted_ink(rgb, lab, core, PPM) is None


def test_r73_group_percentile_matches_numpy():
    rng = np.random.default_rng(5)
    g = rng.integers(0, 7, 3000)
    x = rng.normal(size=3000)
    for q in (0, 10, 30, 50, 90, 100):
        got = T._gperc(g, x, q, 8)
        for k in range(7):
            assert got[k] == pytest.approx(np.percentile(x[g == k], q))
        assert np.isnan(got[7])


def _tick_case():
    H, W = 600, 1200
    line = np.zeros((H, W), bool)
    line[298:303, 50:1150] = True                       # removed table line
    st = np.zeros((H, W), np.uint8)
    cv2.line(st, (560, 150), (640, 450), 1, 8)
    mask = (st > 0) & ~line                             # stroke cut by the line removal
    tick = np.zeros((H, W), bool)
    tick[298:303, 575:600] = True
    tick[298:303, 615:640] = True                       # line leftovers beside the stroke
    mask |= tick
    alpha = mask.astype(np.float32)
    alpha_raw = (mask | line).astype(np.float32)
    return mask, alpha, alpha_raw, line, (st > 0)


def test_r73_ticks_go_gap_filled_stroke_kept():
    mask, alpha, alpha_raw, line, st = _tick_case()
    m2, _ = T.clean(mask.copy(), alpha.copy(), alpha_raw, line, PPM)
    assert m2[298:303, 575:590].sum() == 0 and m2[298:303, 625:640].sum() == 0     # ticks
    assert m2[298:303, 592:612].sum() > 0                                           # crossing bridged
    assert cv2.connectedComponents(m2.astype(np.uint8))[0] - 1 == 1
    kept = mask & ~line
    assert (kept & ~m2).sum() <= 0.005 * kept.sum()                                 # the stroke stays (a dust pixel may go)


def test_r73_line_crop_equals_whole_photo():
    """The line part runs on a crop around the lines; a crop shorter than the morphology kernel must give the
    same result as the whole photo (the crop edge is not ink)."""
    mask, alpha, alpha_raw, line, _ = _tick_case()
    full, _ = T._on_lines(mask.copy(), alpha.copy(), alpha_raw, line, PPM, None)
    ys, xs = np.nonzero(line)
    mg = int(round(3 * PPM)) + 2
    c = (slice(ys.min() - mg, ys.max() + mg + 1), slice(xs.min() - mg, xs.max() + mg + 1))
    part, _ = T._on_lines(mask[c].copy(), alpha[c].copy(), alpha_raw[c], line[c], PPM, None)
    out = mask.copy()
    out[c] = part
    assert np.array_equal(out, full)


YELLOW = {   # local photos with personal data (not in the repository); values = the approved prototype
    "IMG_20261118_194507.jpg": (5, (634, 1238, 1109, 669), (67, 71, 103)),
    "IMG_20261118_194526.jpg": (9, (664, 1232, 980, 511), (120, 124, 153)),
    "IMG_20261118_194536.jpg": (8, (648, 1096, 1039, 612), (90, 91, 121)),
}


@pytest.mark.parametrize("name", sorted(YELLOW))
def test_r73_yellow_forms_match_the_prototype(name):
    f = ZIP4 / name
    if not f.exists():
        pytest.skip("local photo not available")
    img, dpi = P.load_image(f)
    ph = P.prepare_photo(img, dpi, name)
    r = P.process(ph, P.ProcessParams())
    n, frame, rgb = YELLOW[name]
    assert r.stroke_count == n and tuple(r.frame) == frame and tuple(r.ink_rgb) == rgb
    assert r.ink_state == "found" and not r.doubts


# ================================================================== 74 (UI)
@pytest.fixture(scope="module")
def blank_photo(tmp_path_factory):
    p = tmp_path_factory.mktemp("r9") / "blank.png"
    Image.new("RGB", (1200, 800), PAPER).save(p, dpi=(300, 300))
    return p


def test_r74_single_photo_not_found_card_under_the_image(app, blank_photo):
    from ui.widgets.overlay import Popup
    close_all()
    app.go_home()
    app.open_paths([blank_photo])
    pump(app, until=lambda: app.page == "process" and app.job is not None and app.job.processed)
    pump(app, 150)
    pp = app.process_page
    assert app.batch is None and app.job.status == "attention"
    assert Popup.current is None                                      # no dialog 30
    assert pp.warn_bar.visible and not pp.strip.visible and not hasattr(pp, "note")
    assert pp.warn_bar.title == "Требует внимания"
    assert pp.warn_bar.msg == app.t("batch.reason_not_found")
    assert not pp.warn_bar.action.visible
    assert pp.warn_bar.ly > pp.preview.ly                             # under the image, as in the batch
    assert pp.bar.next.disabled
