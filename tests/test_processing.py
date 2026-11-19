"""Stage 1–2 core: input scanning, loading, processing, frame, eraser, ink states, history."""
import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from core import processing as P
from core.history import HistoryStack


def make_photo(ink=(30, 50, 150), size=(1200, 800), dpi=300, lines=True):
    img = Image.new("RGB", size, (246, 244, 238))
    d = ImageDraw.Draw(img)
    if lines:
        for y in range(60, size[1], 60):
            d.line((0, y, size[0], y), fill=(200, 205, 215), width=1)
    pts = [(300 + i * 12, 400 + int(60 * np.sin(i / 3))) for i in range(50)]
    d.line(pts, fill=ink, width=6)
    d.line((320, 470, 900, 440), fill=ink, width=5)
    buf = io.BytesIO()
    img.save(buf, "PNG", dpi=(dpi, dpi))
    return buf.getvalue()


@pytest.fixture
def photo_file(tmp_path):
    p = tmp_path / "IMG_4821.png"
    p.write_bytes(make_photo())
    return p


def load(p):
    img, dpi = P.load_image(p)
    return P.prepare_photo(img, dpi, p.name)


def test_scan_inputs_sorts_files(tmp_path, photo_file):
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / ".hidden.png").write_bytes(b"x")
    big = tmp_path / "big.jpg"
    with big.open("wb") as f:
        f.truncate(P.MAX_FILE_BYTES + 1)
    res = P.scan_inputs([tmp_path])
    assert [p.name for p in res.photos] == ["IMG_4821.png"]
    assert [p.name for p in res.skipped_other] == ["notes.txt"]
    assert [p.name for p in res.too_large] == ["big.jpg"]


def test_supported_extensions():
    for ext in (".jpg", ".JPEG", ".png", ".heic", ".tif", ".webp", ".bmp"):
        assert P.is_supported_image(Path("a" + ext))
    assert not P.is_supported_image(Path("a.pdf"))


def test_load_reads_dpi(photo_file):
    img, dpi = P.load_image(photo_file)
    assert img.size == (1200, 800)
    assert dpi == pytest.approx(300, abs=1)


def test_damaged_file_raises(tmp_path):
    bad = tmp_path / "scan.png"
    bad.write_bytes(b"not an image")
    with pytest.raises(P.ImageLoadError):
        P.load_image(bad)


def test_large_photo_downscaled():
    img = Image.new("RGB", (6400, 1000), "white")
    ph = P.prepare_photo(img, 600, "x.png")
    assert max(ph.size) == P.WORK_MAX_SIDE
    assert ph.work_dpi == pytest.approx(300)


def test_process_finds_signature_and_removes_lines(photo_file):
    ph = load(photo_file)
    res = P.process(ph, P.ProcessParams())
    assert not res.empty
    x, y, w, h = res.frame
    assert 250 <= x <= 330 and 300 <= y <= 360 and w > 550
    # ruled line far from the signature is removed
    assert not res.mask[60, 50:250].any()
    assert res.ink_state in ("found", "same")


def test_ink_found_close_to_real_colour(photo_file):
    res = P.process(load(photo_file), P.ProcessParams())
    if res.ink_state == "found":
        assert np.abs(np.array(res.ink_rgb) - np.array((30, 50, 150))).max() < 60


def test_ink_filter_off_state(photo_file):
    res = P.process(load(photo_file), P.ProcessParams(ink_filter=False))
    assert res.ink_state == "off"


def test_manual_ink(photo_file):
    ph = load(photo_file)
    rgb = P.sample_color(ph, 300, 400 + int(60 * np.sin(0)))
    res = P.process(ph, P.ProcessParams(ink_mode="manual", ink_rgb=rgb))
    assert res.ink_state == "manual" and not res.empty


def test_custom_frame_limits_mask(photo_file):
    ph = load(photo_file)
    res = P.process(ph, P.ProcessParams(), frame=(280, 300, 200, 200))
    ys, xs = np.nonzero(res.mask)
    assert xs.min() >= 280 and xs.max() < 480
    assert res.frame == (280, 300, 200, 200)


def test_frame_clamped():
    assert P.clamp_frame((-10, -10, 50, 50), 100, 100)[:2] == (0, 0)
    x, y, w, h = P.clamp_frame((90, 90, 50, 50), 100, 100)
    assert x + w <= 100 and y + h <= 100


def test_eraser_removes_ink(photo_file):
    ph = load(photo_file)
    base = P.process(ph, P.ProcessParams())
    stroke = P.EraserStroke(points=tuple((float(x), 440.0) for x in range(320, 900, 10)), radius=40)
    er = P.process(ph, P.ProcessParams(), frame=base.frame, eraser=[stroke])
    assert er.mask.sum() < base.mask.sum()
    assert not er.mask[430:450, 400:800].any()


def test_empty_photo_reports_no_signature():
    ph = P.prepare_photo(Image.new("RGB", (800, 600), (250, 250, 250)), None, "blank.png")
    res = P.process(ph, P.ProcessParams())
    assert res.empty


def test_result_rgba_colour(photo_file):
    res = P.process(load(photo_file), P.ProcessParams())
    im = P.result_rgba(res, (0, 0, 0))
    assert im.mode == "RGBA" and im.size == res.mask.shape[::-1]


def test_fine_tune_thickness_changes_mask(photo_file):
    ph = load(photo_file)
    thin = P.process(ph, P.ProcessParams(thickness=-2)).mask.sum()
    thick = P.process(ph, P.ProcessParams(thickness=2)).mask.sum()
    assert thick > thin


def test_history_undo_redo():
    h = HistoryStack()
    for s in (1, 2, 3):
        h.push(s)
    assert h.can_undo()
    assert h.undo() == 2
    assert h.undo() == 1
    assert h.redo() == 2
    h.push(9)
    assert not h.can_redo()
