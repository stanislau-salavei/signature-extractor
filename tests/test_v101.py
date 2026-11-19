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
