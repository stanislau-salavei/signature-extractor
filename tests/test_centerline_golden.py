"""Reference («golden») tests of the centreline trace (audit remark 100, centreline part).

The exact output of ``centerline_paths`` / ``trace_centerline`` and of the SVG-stroke and DXF
files built from it is pinned by SHA-256 hashes for two sizes (original, 40 × 15 mm box), so a
refactoring of ``stitch_edges`` / ``resolve_bridges`` / ``join_chains`` must not change a single
coordinate.  Only hashes are stored — no image data.

* Synthetic cases (strokes drawn here) always run.
* Local sample photos are not in the repository (personal data); set ``SE_SAMPLE_GOLDEN=1`` to
  check them as well (folders from ``SE_SAMPLE_DIRS``, ``os.pathsep``-separated).
* ``SE_GOLDEN_WRITE=1`` rewrites the stored hashes (only after an intended output change).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from core import export as E  # noqa: E402
from core import processing as P  # noqa: E402
from core.centerline import centerline_paths  # noqa: E402

GOLDEN = Path(__file__).parent / "golden" / "centerline_golden.json"
WRITE = os.environ.get("SE_GOLDEN_WRITE") == "1"
SAMPLE_DIRS = os.environ.get("SE_SAMPLE_DIRS", os.pathsep.join([
    "/workspace/win_test_images", "/workspace/rewrite/testdata", "/workspace/private_test_data"]))
EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".heic"}
SIZES = (("orig", E.SizeChoice.original()), ("box40x15", E.SizeChoice.box(40, 15)))
RGB = (20, 40, 160)


def _sha(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _dxf_norm(b: bytes) -> bytes:
    b = re.sub(rb"\{[0-9A-Fa-f-]{36}\}", b"{G}", b)
    b = re.sub(rb"@ \d{4}-\d\d-\d\dT[0-9:.+]+", b"@ T", b)
    b = re.sub(rb"24\d{5}\.\d+", b"JD", b)       # Julian-date header timestamps
    # geometry only: HEADER (units, extents) + ENTITIES; the OBJECTS order follows the hash seed
    keep = [m.group(0) for m in re.finditer(rb"(?:^|\n)  0\r?\nSECTION\r?\n  2\r?\n(HEADER|ENTITIES)\r?\n.*?\nENDSEC", b, re.S)]
    assert len(keep) == 2, "DXF sections not found"
    return b"".join(keep)


def _fingerprint(src) -> dict:
    """Hashes of the exact centreline (repr of every float) and of the SVG-stroke / DXF files."""
    out = {}
    sw, sh = src.size_px
    for name, size in SIZES:
        geom = E.compute_geometry(sw, sh, src.dpi, size, 1.0)
        cl = E.trace_centerline(src, geom)
        job = E.ExportJob(src, size, 1.0, RGB, 600, ("SVG", "DXF"), svg_mode="stroke")
        files = E.build_outputs(job, centerline=cl)
        out[name] = {"paths": _sha(repr(cl.paths)), "n": len(cl.paths),
                     "svg": _sha(files["SVG"]), "dxf": _sha(_dxf_norm(files["DXF"]))}
    return out


# ------------------------------------------------------------------ synthetic strokes
def _canvas(h=260, w=620):
    return np.zeros((h, w), np.uint8)


def _poly(img, pts, t, closed=False):
    cv2.polylines(img, [np.round(np.asarray(pts)).astype(np.int32)], closed, 255, t, cv2.LINE_AA)


def _bezier(rng, n_ctrl, h, w):
    c = rng.uniform((20, 20), (w - 20, h - 20), size=(n_ctrl, 2))
    s = np.linspace(0, 1, 160)[:, None]
    pts = c
    while len(pts) > 1:
        pts = pts[:-1, None, :] * (1 - s) + pts[1:, None, :] * s if pts.ndim == 2 else pts[:-1] * (1 - s) + pts[1:] * s
    return pts.reshape(-1, 2)


def _case_cross(img):
    _poly(img, [(40, 40), (580, 220)], 9)
    _poly(img, [(40, 220), (580, 40)], 9)


def _case_shallow(img):
    _poly(img, [(20, 120), (600, 150)], 10)
    _poly(img, [(20, 165), (600, 105)], 10)


def _case_parallel(img):
    xs = np.linspace(30, 590, 120)
    _poly(img, np.c_[xs, 130 + 40 * np.sin(xs / 60)], 9)
    _poly(img, np.c_[xs, 140 + 40 * np.sin(xs / 60 + 0.25)], 9)


def _case_loops(img):
    t = np.linspace(0, 6 * np.pi, 600)
    _poly(img, np.c_[60 + t * 25 + 45 * np.cos(t), 130 + 70 * np.sin(t)], 8)


def _case_teardrop(img):
    t = np.linspace(-np.pi / 2, 3 * np.pi / 2, 200)
    _poly(img, np.c_[300 + 80 * np.cos(t), 110 + 70 * np.sin(t)], 9)
    _poly(img, [(300, 40), (300, 245)], 9)
    _poly(img, [(80, 230), (560, 230)], 7)


def _case_ring_dots(img):
    cv2.circle(img, (200, 130), 80, 255, 10, cv2.LINE_AA)
    cv2.circle(img, (420, 130), 4, 255, -1, cv2.LINE_AA)
    cv2.circle(img, (520, 60), 6, 255, -1, cv2.LINE_AA)
    _poly(img, [(330, 200), (600, 200)], 6)


def _case_star(img):
    c = np.array([310, 130])
    for a in np.linspace(0, np.pi, 4, endpoint=False):
        d = 110 * np.array([np.cos(a), np.sin(a)])
        _poly(img, [c - d, c + d], 8)


def _case_spurs(img):
    _poly(img, [(30, 130), (590, 130)], 14)
    for x in range(80, 560, 70):
        _poly(img, [(x, 130), (x + 8, 100 - (x % 3) * 8)], 6)


def _random_case(seed):
    def draw(img):
        rng = np.random.default_rng(seed)
        h, w = img.shape
        for _ in range(int(rng.integers(2, 5))):
            _poly(img, _bezier(rng, int(rng.integers(4, 8)), h, w), int(rng.integers(5, 13)))
    return draw


CASES = {"cross": _case_cross, "shallow": _case_shallow, "parallel": _case_parallel, "loops": _case_loops,
         "teardrop": _case_teardrop, "ring_dots": _case_ring_dots, "star": _case_star, "spurs": _case_spurs}
CASES.update({f"random_{s}": _random_case(s) for s in range(1, 13)})


def _synthetic_source(name):
    img = _canvas()
    CASES[name](img)
    return E.source_from_mask(img >= 128, 300, RGB, name)


def _synthetic_bitmap_fp(name):
    """centerline_paths straight on the bitmap (no resampling) as well."""
    img = _canvas()
    CASES[name](img)
    return _sha(repr(centerline_paths(img >= 128)))


# ------------------------------------------------------------------ golden store
def _load():
    return json.loads(GOLDEN.read_text("utf-8")) if GOLDEN.exists() else {}


_store = _load()


def _check(section, key, got):
    if WRITE:
        _store.setdefault(section, {})[key] = got
        GOLDEN.write_text(json.dumps(_store, indent=1, sort_keys=True, ensure_ascii=False) + "\n", "utf-8")
        return
    want = _store.get(section, {}).get(key)
    assert want is not None, f"no golden for {section}/{key} (run with SE_GOLDEN_WRITE=1)"
    assert got == want, f"centreline output changed for {section}/{key}"


@pytest.mark.parametrize("name", sorted(CASES))
def test_centerline_golden_synthetic(name):
    got = _fingerprint(_synthetic_source(name))
    got["bitmap"] = _synthetic_bitmap_fp(name)
    _check("synthetic", name, got)


def _samples():
    out = []
    for d in SAMPLE_DIRS.split(os.pathsep):
        root = Path(d)
        if root.is_dir():
            for p in sorted(root.rglob("*")):
                if p.is_file() and p.suffix.lower() in EXTS:
                    out.append((f"{root.name}/{p.relative_to(root).as_posix()}", p))
    return out


@pytest.mark.skipif(os.environ.get("SE_SAMPLE_GOLDEN") != "1", reason="local sample photos: set SE_SAMPLE_GOLDEN=1")
@pytest.mark.parametrize("key,path", _samples() if os.environ.get("SE_SAMPLE_GOLDEN") == "1" else [])
def test_centerline_golden_samples(key, path):
    try:
        img, dpi = P.load_image(path)
    except P.ImageLoadError:            # deliberately broken / oversized test files
        _check("samples", key, {"load_error": True})
        return
    res = P.process(P.prepare_photo(img, dpi, path.name), P.ProcessParams())
    got = {"empty": True} if res.empty else _fingerprint(E.source_from_result(res))
    _check("samples", key, got)
