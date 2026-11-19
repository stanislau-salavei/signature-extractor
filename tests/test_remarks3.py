"""Remarks 20–26 (2026-11-17): SVG thickness modes, help texts, in-window dialogs, live crop frame."""
import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from core import export as ex

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "i18n" / "strings_ru_en.csv"
NS = "{http://www.w3.org/2000/svg}"


def rows():
    return {r[0]: r for r in csv.reader(CSV.open(encoding="utf-8-sig", newline=""))}


@pytest.fixture(scope="module")
def source():
    m = np.zeros((200, 600), dtype=bool)
    m[95:105, 40:560] = True                      # 10 px bar
    m[30:170, 295:305] = True                     # crossing 10 px bar
    return ex.source_from_mask(m, 300, (20, 30, 120), "X")


# ------------------------------------------------------------------ 22: SVG thickness
def test_svg_defaults():
    assert ex.DEFAULT_SVG_MODE == "original" and ex.DEFAULT_SVG_LINE_MM == 0.18
    job = ex.ExportJob(None, ex.SizeChoice.original(), 0.5, (0, 0, 0), 300, ("SVG",))
    assert job.svg_mode == "original" and job.svg_line_mm == 0.18
    assert ex.clamp_svg_mode("bogus") == "original" and ex.clamp_svg_mode("stroke") == "stroke"


def test_svg_stroke_document_is_centreline_with_stroke(source):
    job = ex.ExportJob(source, ex.SizeChoice.box(15, 5), 0.5, (27, 42, 138), 600, ("SVG",), svg_mode="stroke",
                       svg_line_mm=0.25)
    svg = ex.build_outputs(job)["SVG"].decode()
    root = ET.fromstring(svg)
    assert root.get("width") == "15mm" and root.get("height") == "5mm" and root.get("viewBox") == "0 0 15 5"
    g = root.find(f"{NS}g")
    assert g.get("fill") == "none" and g.get("stroke") == "#1B2A8A" and g.get("stroke-width") == "0.25"
    assert g.get("stroke-linecap") == "round" and g.get("stroke-linejoin") == "round"
    paths = g.findall(f"{NS}path")
    assert 1 <= len(paths) <= 4                   # two crossing strokes, no outline rings
    assert not root.findall(f".//{NS}path[@fill]")


def test_svg_original_mode_is_filled_outline(source):
    job = ex.ExportJob(source, ex.SizeChoice.box(15, 5), 0.5, (27, 42, 138), 600, ("SVG",))
    svg = ex.build_outputs(job)["SVG"].decode()
    assert 'fill="#1B2A8A"' in svg and "stroke-width" not in svg


def test_svg_line_is_separate_from_dxf(source):
    job = ex.ExportJob(source, ex.SizeChoice.box(15, 5), 0.5, (0, 0, 0), 600, ("SVG", "DXF"), dxf_line_mm=0.5,
                       svg_mode="stroke", svg_line_mm=0.13)
    out = ex.build_outputs(job)
    assert 'stroke-width="0.13"' in out["SVG"].decode()
    assert b"0.5" in out["DXF"]


def test_vector_kb_follows_svg_mode(source):
    geom = ex.compute_geometry(*source.size_px, source.dpi, ex.SizeChoice.box(15, 5), 0.5)
    outline, cl = ex.trace_outline(source, geom), ex.trace_centerline(source, geom)
    a = ex.vector_sizes_kb(outline, cl, (0, 0, 0))["SVG"]
    b = ex.vector_sizes_kb(outline, cl, (0, 0, 0), svg_mode="stroke")["SVG"]
    assert a == ex.vector_sizes_kb(outline, None, (0, 0, 0))["SVG"]
    assert b == ex.estimate_kb(len(ex.svg_stroke_document(cl, (0, 0, 0)).encode()))


def test_svg_settings(tmp_path, monkeypatch):
    import importlib
    import json
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import core.settings as mod
    mod = importlib.reload(mod)
    s = mod.SettingsManager([])
    assert s.get("svg_mode") == "original" and s.get("svg_line_mm") == 0.18
    s.set("svg_mode", "stroke")
    s.set("svg_line_mm", 0.3)
    s2 = mod.SettingsManager([])
    assert s2.get("svg_mode") == "stroke" and s2.get("svg_line_mm") == 0.3 and s2.get("dxf_line_mm") == 0.18
    d = tmp_path / "Signature Extractor"
    (d / "settings.json").write_text(json.dumps({"svg_mode": "thick", "svg_line_mm": 9, "settings_version": 2}),
                                     encoding="utf-8")
    s3 = mod.SettingsManager([])
    assert s3.get("svg_mode") == "original" and s3.get("svg_line_mm") == 0.18


# ------------------------------------------------------------------ 20, 21, 23: texts
def test_kompas_is_always_kompas_3d():
    text = CSV.read_text(encoding="utf-8-sig")
    assert not re.search(r"(КОМПАС|KOMPAS)(?!-3D)", text)
    r = rows()
    assert r["export.dxf.desc"][2] == "Для AutoCAD и КОМПАС-3D, линии в мм"
    assert r["export.dxf.desc"][3] == "For AutoCAD and KOMPAS-3D, lines in mm"   # remark 28


def test_approved_help_texts():
    r = rows()
    assert r["help.formats.png_margin"][2].startswith("Поле рамки: отступ от подписи до края файла. Задаётся в карточке "
                                                      "«Размер подписи» и действует на все форматы.")   # + remark 49
    assert r["help.formats.dxf"][2] == "DXF — для AutoCAD и КОМПАС-3D"
    assert r["help.formats.svg_thickness"][2].startswith(
        "Толщина: «Как в оригинале» сохраняет штрихи такими, как на снимке, а «Заданная толщина» рисует линию "
        "по середине штриха выбранной толщины (по умолчанию 0,18 мм).")
    # remark 49 (item 6) replaced the toggles text
    assert r["help.formats.toggles"][2] == ("Каждый формат включается переключателем в своей карточке. В карточке PNG "
                                            "выбирается разрешение, в карточке SVG — режим толщины, в карточке DXF — "
                                            "толщина линии.")
    assert "PNG card" not in r["export.png.margin"][4].split("moved there from the PNG card")[0]
    for k in ("export.svg.mode", "export.svg.mode.original", "export.svg.mode.stroke", "export.svg.line",
              "export.svg.line.desc"):
        assert r[k][2] and r[k][3]
    assert r["export.svg.mode.original"][2] == "Как в оригинале" and r["export.svg.mode.stroke"][2] == "Заданная толщина"


def test_formats_help_order():
    """Remark 41: «Форматы экспорта» is cards; «Поле рамки» stays in the «Размер подписи» card after «Свой размер»."""
    fh = pytest.importorskip("ui.dialogs.formats_help")
    r = rows()
    t = lambda k, **kw: r[k][2] if k in r else k
    blocks = fh.formats_blocks(t)
    cards = {d[1] or d[0]: ["".join(s for s, _ in x[1]) for x in d[2] if x[0] == "li"] for k, d in blocks if k == "card"}
    size = cards[r["export.size"][2]]
    margin_i = next(i for i, d in enumerate(size) if d.startswith("Поле рамки"))
    custom_i = next(i for i, d in enumerate(size) if d.startswith("«Свой размер"))
    assert margin_i == custom_i + 1
    assert any(s.startswith("Толщина: «Как в оригинале»") for s in cards[r["help.formats.svg"][2]])


# ------------------------------------------------------------------ 24, 25: in-window dialogs
def test_no_child_windows_left():
    assert not (ROOT / "ui" / "dialogs" / "child.py").exists()
    for p in (ROOT / "ui").rglob("*.py"):
        src = p.read_text(encoding="utf-8")
        assert "ChildWindow" not in src and "Toplevel(" not in src, p
    fh = pytest.importorskip("ui.dialogs.formats_help")
    cd = pytest.importorskip("ui.dialogs.color_dialog")
    from ui.dialogs.content import ContentDialog
    assert issubclass(fh.HelpWindow, ContentDialog) and issubclass(cd.CustomColorDialog, ContentDialog)


def test_help_fits_minimum_window():
    fh = pytest.importorskip("ui.dialogs.formats_help")
    dlg = object.__new__(fh.HelpWindow)
    dlg.app = SimpleNamespace(height=lambda: 648)
    dlg._content_h = 5000
    panel = 1 + dlg._body_h() + 81 + 1
    assert panel <= 648 - 2 * 16
    dlg._content_h = 200                                         # short topics: no empty space
    assert dlg.scroll_h() == 200


# ------------------------------------------------------------------ 26: live crop frame
def _preview():
    pv_mod = pytest.importorskip("ui.pages.preview")
    pv = object.__new__(pv_mod.Preview)
    res = SimpleNamespace(frame=(10, 10, 100, 50))
    pv.app = SimpleNamespace(job=SimpleNamespace(result=res))
    pv.drag, pv.pending_frame, pv._await = None, None, None
    pv._redraw_after, pv._last_redraw = None, 0.0
    return pv, res


def test_live_frame_during_drag_and_until_reprocessed():
    pv, res = _preview()
    assert pv._live_frame() is None
    pv.drag, pv.pending_frame = ("frame", "r", (0, 0), res.frame), (10, 10, 60, 50)
    assert pv._live_frame() == (10, 10, 60, 50)
    pv.drag, pv.pending_frame = None, None
    pv._await = ((10, 10, 60, 50), res)                          # released, full processing running
    assert pv._live_frame() == (10, 10, 60, 50)
    pv.app.job.result = SimpleNamespace(frame=(10, 10, 60, 50))  # full result arrived
    assert pv._live_frame() is None and pv._await is None


def test_live_redraw_is_throttled(monkeypatch):
    pv, _ = _preview()
    calls, scheduled = [], []
    pv.redraw = lambda: calls.append(1)
    pv.after = lambda ms, fn: scheduled.append((ms, fn)) or "id"
    pv.after_cancel = lambda i: None
    now = [100.0]
    monkeypatch.setattr("ui.pages.preview.time.monotonic", lambda: now[0])
    pv._redraw_live()
    assert len(calls) == 1 and not scheduled
    now[0] += 0.010
    pv._redraw_live()
    pv._redraw_live()                                            # coalesced into one trailing redraw
    assert len(calls) == 1 and len(scheduled) == 1 and scheduled[0][0] <= pv.LIVE_MS
    scheduled[0][1]()
    assert len(calls) == 2
