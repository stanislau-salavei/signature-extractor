"""Version 1.0.1: code audit remarks 94–118 (2026-11-19). Behaviour of the program does not change."""
import base64
import re
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


# ================================================================== 99: pi-heif instead of pillow-heif
def test_r99_pi_heif_decoder_only():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    spec = (ROOT / "packaging" / "SignatureExtractor.spec").read_text(encoding="utf-8")
    assert re.search(r"^pi-heif\b", req, re.M) and "pillow-heif" not in req
    assert 'collect_submodules("pi_heif")' in spec and "collect_submodules(\"pillow_heif\")" not in spec


def test_r99_heic_sample_decodes(tmp_path):
    from core import processing as P
    from ui import smoke
    assert P.heif_available()
    p = tmp_path / "s.HEIC"
    p.write_bytes(base64.b64decode(smoke.SMOKE_HEIC))
    img, dpi = P.load_image(p)
    assert img.size == (64, 48) and img.mode == "RGB" and dpi is None
    assert np.abs(np.asarray(img).astype(int) - 250).max() <= 2


# ================================================================== 94: exact versions for the build
def test_r94_constraints_pin_every_requirement():
    pins = {}
    for line in (ROOT / "packaging" / "constraints-win.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            name, _, ver = line.partition("==")
            assert ver and re.fullmatch(r"[0-9][0-9A-Za-z.]*", ver), line
            pins[name.lower().replace("_", "-")] = ver
    for f in ("requirements.txt", "requirements-dev.txt", "packaging/requirements-build.txt"):
        for line in (ROOT / f).read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            if line and not line.startswith("-r"):
                name = re.split(r"[<>=!~ ]", line)[0].lower().replace("_", "-")
                assert name in pins, (f, name)
    wf = (ROOT / ".github" / "workflows" / "build-installer.yml").read_text(encoding="utf-8")
    assert "-c packaging/constraints-win.txt" in wf and "-r requirements-dev.txt" in wf


# ================================================================== 98, 104, 105: smaller build; D7, D8
def test_r98_r104_r105_spec_excludes():
    spec = (ROOT / "packaging" / "SignatureExtractor.spec").read_text(encoding="utf-8")
    assert '"opencv_videoio_ffmpeg" not in b[0].lower()' in spec and spec.index("a.binaries = [") < spec.index("COLLECT(")
    for ext in ("**/*.c", "**/*.pyx", "**/*.pxd", "**/*.pyi", "**/*.h", "**/tests/**"):
        assert f'"{ext}"' in spec
    assert '"PIL.AvifImagePlugin", "PIL._avif"' in spec
    assert "AI" not in spec and "remark 78" not in spec                    # D8: no stale AI comments
    assert '"onnxruntime", "torch",' in spec                               # the excludes themselves stay
    wf = (ROOT / ".github" / "workflows" / "build-installer.yml").read_text(encoding="utf-8")
    assert "opencv_videoio_ffmpeg*" in wf and "_avif*" in wf               # checked in the built program


def test_d7_pytest_not_a_runtime_requirement():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "pytest" not in req
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "-r requirements.txt" in dev and re.search(r"^pytest\b", dev, re.M)


def test_r105_smoke_checks_png_and_jpeg():
    src = (ROOT / "ui" / "smoke.py").read_text(encoding="utf-8")
    assert 'out["png_jpeg"]' in src and 'isinstance(out["png_jpeg"], list)' in src


# ================================================================== 106–109, 111, A14: dead code
def test_r106_unused_core_functions_removed():
    from core import batch as B, processing as P
    assert not hasattr(P, "detect_ink") and not hasattr(P, "_chroma") and hasattr(P, "detect_ink_ex")
    assert not hasattr(B.Batch, "no_dpi_items")
    assert "Test hook" in P.load_image_bytes.__doc__


def test_r107_unused_ui_members_removed():
    from ui import theme, updates
    from ui.pages import export_page, settings_page
    from ui.widgets import controls
    assert not hasattr(export_page.ExportPage, "delete_color")
    assert not hasattr(settings_page.SettingsPage, "reveal_about") and not hasattr(settings_page, "_ver")
    assert not hasattr(theme, "Sf") and not hasattr(controls.Toggle, "label_width")
    for mod, names in ((settings_page, ("lic_y", "right_w", "size_menu", "color_menu")), (updates, ("last_result",))):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert not any(re.search(rf"\.{n}\b", src) for n in names), mod
    for f, n in (("ui/app.py", "_sys_dark"), ("ui/pages/import_page.py", "_spin_job"),
                 ("ui/widgets/controls.py", "def set_labels")):
        assert n not in (ROOT / f).read_text(encoding="utf-8"), f


def test_r108_test_hooks_marked():
    from core import batch as B
    from ui.dialogs import formats_help
    from ui.widgets import scroll
    assert "Test hook" in B.SaveSession.finished.__doc__
    assert "Test hook" in formats_help.card_titles.__doc__
    assert "Test hook" in scroll.BarMixin.thumb_rect.__doc__ and "Test hook" in scroll.BarMixin.arrows_shown.__doc__
    assert "test hook (remark 108)" in (ROOT / "core" / "settings.py").read_text(encoding="utf-8")


def test_r109_no_pending_skipped():
    for f in ("core/state.py", "ui/app.py"):
        assert "pending_skipped" not in (ROOT / f).read_text(encoding="utf-8")


def test_r111_unused_icons_removed():
    icons = ROOT / "assets" / "icons"
    for n in ("chev_down_combo", "gpu", "hc_ai", "info_filled", "minimize", "sparkle"):
        assert not (icons / f"{n}.png").exists(), n
    assert list(icons.glob("help_*.png"))


def test_a14_one_scrollbar_mixin():
    from ui.widgets import batch, scroll
    assert issubclass(scroll.ScrollBar, scroll.BarMixin) and issubclass(batch._HBar, scroll.BarMixin)
    for cls in (scroll.ScrollBar, batch._HBar):
        assert "thumb_rect" not in cls.__dict__ and "_thumb" not in cls.__dict__


# ================================================================== 118: small findings A7–A13
def test_a7_a11_unused_constants_and_parameters_removed():
    import inspect
    from core import export, processing, ruling, tinted
    from ui.dialogs import color_dialog, formats_help
    from ui.pages import settings_page
    from ui.widgets import controls, overlay
    for mod, names in ((export, ["CELL_PADDING_MM"]), (processing, ["THICKNESS_RANGE"]), (ruling, ["RULE_SPAN"]),
                       (tinted, ["SOFT", "SEED_AT", "SEED_MM2"]), (color_dialog, ["BOARD_H"]),
                       (formats_help, ["FOOT_H", "PAD_B"]), (settings_page, ["COLOR_COMBO_MIN", "COLOR_COMBO_MAX"]),
                       (overlay, ["SEPARATOR"])):
        for n in names:
            assert not hasattr(mod, n), (mod.__name__, n)
    assert "start_rgb" not in inspect.signature(color_dialog.CustomColorDialog.__init__).parameters
    assert "compact_text" not in inspect.signature(controls.ToolButton.__init__).parameters
    assert "translucent_track" not in inspect.signature(controls.Segmented.__init__).parameters
    from ui import app as A
    assert "force" not in inspect.signature(A.App.layout).parameters


def test_a8_a9_a10_ruff_clean():
    import shutil
    import subprocess
    ruff = shutil.which("ruff") or str(Path(__import__("sys").executable).with_name("ruff"))
    if not Path(ruff).exists():
        pytest.skip("ruff is not installed")
    r = subprocess.run([ruff, "check", "--no-cache", "--select", "F401,F841,B023,SIM222,RUF034", "core", "ui"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    for f in ("core/tinted.py", "ui/pages/export_page.py"):
        assert "if True:" not in (ROOT / f).read_text(encoding="utf-8"), f
    assert "if False else" not in (ROOT / "ui/pages/export_page.py").read_text(encoding="utf-8")


def test_a13_repository_urls_in_one_place():
    from core import updater as U, version as V
    from ui import app as A
    from ui.pages import settings_page as SP
    assert V.REPO_URL == "https://github.com/" + V.REPO_SLUG and V.API_LATEST.startswith("https://api.github.com/repos/" + V.REPO_SLUG)
    assert A.REPO_URL == SP.REPO_URL == V.REPO_URL and U.API_LATEST == V.API_LATEST
    assert A.LICENSE_URL == SP.LICENSE_URL == V.LICENSE_URL
    for f in list((ROOT / "core").glob("*.py")) + list((ROOT / "ui").rglob("*.py")):
        if f.name != "version.py":
            t = f.read_text(encoding="utf-8")
            assert "stanislau-salavei/signature-extractor" not in t and "gpl-3.0.html" not in t, f


# ================================================================== 101: PNG decoded once; B13: one orientation table
def _png_with_exif_after_idat(path, orientation):
    import io
    import struct
    import zlib
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (30, 20), (250, 250, 250)).save(buf, "PNG")
    raw = buf.getvalue()
    e = Image.Exif()
    e[0x0112] = orientation
    data = e.tobytes()
    chunk = struct.pack(">I", len(data)) + b"eXIf" + data + struct.pack(">I", zlib.crc32(b"eXIf" + data) & 0xFFFFFFFF)
    path.write_bytes(raw[:-12] + chunk + raw[-12:])          # IEND is the last 12 bytes


def test_r101_png_orientation_without_pixel_decoding(tmp_path, monkeypatch):
    from PIL import Image, PngImagePlugin
    from core import processing as P
    e = Image.Exif()
    e[0x0112] = 6
    before = tmp_path / "before.png"
    Image.new("RGB", (30, 20), (250, 250, 250)).save(before, exif=e.tobytes())
    after = tmp_path / "after.png"
    _png_with_exif_after_idat(after, 6)
    plain = tmp_path / "plain.png"
    Image.new("RGB", (30, 20), (250, 250, 250)).save(plain)
    assert not P.png_meta_after_idat(before) and not P.png_meta_after_idat(plain) and P.png_meta_after_idat(after)
    loads = []
    real = PngImagePlugin.PngImageFile.load
    monkeypatch.setattr(PngImagePlugin.PngImageFile, "load", lambda self: loads.append(1) or real(self))
    for p in (before, plain):
        loads.clear()
        img, _ = P.load_image(p)
        assert not loads, p                                          # pixels decoded once (OpenCV)
    assert P.load_image(before)[0].size == (20, 30) and P.load_image(plain)[0].size == (30, 20)
    loads.clear()
    assert P.load_image(after)[0].size == (20, 30) and loads         # rare file: the old, slow way
    (tmp_path / "cut.png").write_bytes(plain.read_bytes()[:20])
    assert P.png_meta_after_idat(tmp_path / "cut.png")


def test_b13_one_orientation_table():
    from PIL import Image, ImageOps
    from core import processing as P
    src = (ROOT / "core" / "processing.py").read_text(encoding="utf-8")
    assert src.count("Image.Transpose.ROTATE_270") == 1 and "exif_transpose" not in src.replace("ImageOps.exif_transpose)", "")
    im = Image.new("RGB", (5, 3))
    im.putpixel((0, 0), (255, 0, 0))
    for o in range(1, 9):
        e = Image.Exif()
        e[0x0112] = o
        im.info["exif"] = e.tobytes()
        im._exif = None
        a = P._normalize(im)
        b = ImageOps.exif_transpose(im)
        assert a.size == b.size and a.tobytes() == b.tobytes(), o


# ================================================================== 102: paper tint, C9: lazy imports
def test_r102_paper_tint_samples_first():
    import cv2
    from core import tinted as T
    rgb = np.full((300, 400, 3), (245, 232, 160), np.uint8)
    rgb[100:140, 50:350] = (30, 40, 120)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    core = np.zeros((300, 400), bool)
    core[100:140, 50:350] = True
    ua, ub, c = T.paper_tint(lab, core)
    px = lab.reshape(-1, 3)[~core.ravel()][::7].astype(np.float32)      # the 1.0 formula
    a, b = float(np.median(px[:, 1])) - 128.0, float(np.median(px[:, 2])) - 128.0
    assert abs(c - float(np.hypot(a, b))) < 0.5 and c >= T.PAPER_TINT_C
    assert "[::7][~core.ravel()[::7]]" in (ROOT / "core" / "tinted.py").read_text(encoding="utf-8")


def test_c9_heif_and_updater_imported_lazily():
    import subprocess
    import sys
    code = ("import sys; import core.processing as P; a = 'pi_heif' in sys.modules; P.heif_available(); "
            "print(a, 'pi_heif' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert out == ["False", "True"]
    from ui import app as A
    assert isinstance(A.App.__dict__["updates"], property)


# ================================================================== 96 + 116: plates, 97: photo cache
def _cases():
    import random
    rnd = random.Random(5)
    cols = ["#FFFFFF", "#F3F3F3", "#0067C0", "#E5E5E5", None]
    for _ in range(40):
        w, h = rnd.choice([rnd.uniform(5, 40), rnd.uniform(40, 700)]), rnd.choice([rnd.uniform(5, 40), rnd.uniform(40, 700)])
        yield w, h, dict(radius=rnd.choice([0, 4, 8, min(w, h) / 2]), fill=rnd.choice(cols), stroke=rnd.choice(cols),
                         stroke_w=rnd.choice([1, 1.5]), stroke_bottom=rnd.choice([None, "#000000"]),
                         stroke_top=rnd.choice([None, "#1F1F1F"]), bg=rnd.choice(cols),
                         fill_alpha=rnd.choice([1, 0.5]))


@pytest.mark.parametrize("factor", [1.0, 1.25, 1.5])
def test_r96_plate_same_pixels_as_whole_drawing(factor):
    from ui import gfx
    from ui.theme import Scale
    old = Scale.factor
    Scale.factor = factor
    try:
        for w, h, kw in _cases():
            st = gfx.ShapeStyle(**kw)
            W, H = max(1, int(round(w * factor))), max(1, int(round(h * factor)))
            try:
                whole = np.asarray(gfx._plate_px(W, H, st, (W, H)))
            except ValueError:          # degenerate tiny boxes fail in Pillow the same way as in 1.0
                continue
            assert np.array_equal(np.asarray(gfx.plate(w, h, st)), whole), (w, h, kw)
            assert np.array_equal(np.asarray(gfx.rrect(w, h, kw["radius"], kw["fill"], kw["stroke"], kw["stroke_w"],
                                                       kw["stroke_top"], kw["stroke_bottom"], bg=kw["bg"],
                                                       fill_alpha=kw["fill_alpha"])), whole)
        for w, h, r in [(1000, 600, 8), (300, 40, 14), (28, 28, 14), (700, 90, 2)]:
            W, H = int(round(w * factor)), int(round(h * factor))
            k = gfx.SS * factor
            seg = gfx._dash_segments(W * gfx.SS, H * gfx.SS, 1.5 * k, r * k, 4 * k, 4 * k)
            whole = np.asarray(gfx._dash_band(seg, 1.5 * k, "#0067C0", 0, 0, W, H, (W, H)))
            assert np.array_equal(np.asarray(gfx.dashed_rrect(w, h, r, "#0067C0")), whole), (w, h, r)
    finally:
        Scale.factor = old


def test_r96_large_plate_is_fast():
    import time
    from ui import gfx
    t = time.perf_counter()
    gfx.rrect(1000, 600, 8, "#FFFFFF", "#E5E5E5", bg="#F3F3F3")
    assert time.perf_counter() - t < 0.12


def test_r97_photo_cache_limited_by_bytes(monkeypatch):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("no X display")
    import tkinter as tk
    from PIL import Image
    from ui import gfx
    root = tk.Tk()
    try:
        gfx.clear_cache()
        monkeypatch.setattr(gfx, "PHOTO_CACHE_BYTES", 100 * 100 * 4 * 3)
        for i in range(10):
            gfx.photo(("t", i), lambda: Image.new("RGBA", (100, 100)))
        assert gfx.cache_bytes() <= gfx.PHOTO_CACHE_BYTES and len(gfx._photo_cache) == 3
        assert ("t", 9, gfx.Scale.factor) in gfx._photo_cache and ("t", 0, gfx.Scale.factor) not in gfx._photo_cache
        gfx.photo(("t", 7), lambda: 1 / 0)                    # hit: no factory call, becomes most recent
        gfx.photo(("t", 10), lambda: Image.new("RGBA", (100, 100)))
        assert ("t", 7, gfx.Scale.factor) in gfx._photo_cache and ("t", 8, gfx.Scale.factor) not in gfx._photo_cache
    finally:
        gfx.clear_cache()
        root.destroy()


# ================================================================== 118: B14 worker polling, C7 theme
def test_b14_worker_busy_and_on_submit():
    import threading
    from core.worker import BackgroundWorker
    w = BackgroundWorker()
    calls, got = [], []
    w.on_submit = lambda: calls.append(1)
    assert not w.busy()
    ev = threading.Event()
    w.submit("a", lambda: ev.wait(5) or 1, got.append, None)
    assert calls == [1] and w.busy()
    ev.set()
    import time
    for _ in range(200):
        w.poll()
        if got:
            break
        time.sleep(0.01)
    assert got == [1] and not w.busy()
    w.submit("b", lambda: 2, got.append, None)
    w.cancel("b")
    for _ in range(200):
        w.poll()
        if not w.busy():
            break
        time.sleep(0.01)
    assert not w.busy() and got == [1]


def test_b14_c7_app_source():
    src = (ROOT / "ui" / "app.py").read_text(encoding="utf-8")
    assert "self.root.after(30, self._poll_worker)\n" in src and "if self.worker.busy():" in src
    assert "if changed or initial:" in src
