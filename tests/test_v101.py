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
    assert P.HAS_HEIF
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
