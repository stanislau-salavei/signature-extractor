"""Stage 3 export logic: sizing, colour, writers, file names."""
import io
import math
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core import export as ex


def make_mask(w=600, h=200, stroke=6):
    """A wavy signature-like stroke, ink=True."""
    m = np.zeros((h, w), dtype=bool)
    yy, xx = np.mgrid[0:h, 0:w]
    for x0 in range(20, w - 20):
        y = h / 2 + (h / 3) * math.sin(x0 / 40.0)
        m |= (xx - x0) ** 2 + (yy - y) ** 2 <= (stroke / 2) ** 2
    return m


@pytest.fixture(scope="module")
def source():
    big = np.zeros((300, 700), dtype=bool)
    big[40:240, 50:650] = make_mask()
    return ex.source_from_mask(big, 300, (20, 30, 120), "IMG_1")


# ------------------------------------------------------------------ numbers
def test_mm_to_px_rounding():
    assert ex.mm_to_px(128.2, 300) == 1514
    assert ex.mm_to_px(128.2, 600) == 3028
    assert ex.mm_to_px(128.2, 150) == 757
    assert ex.mm_to_px(25.4, 600) == 600
    assert ex.round_half_up(2.5) == 3


def test_parse_and_format_number():
    assert ex.parse_number("2,5") == 2.5
    assert ex.parse_number(" 3 ") == 3.0
    assert ex.parse_number("abc") is None
    assert ex.format_number(14.0, "ru") == "14,0"
    assert ex.format_number(14.0, "en") == "14.0"


# ------------------------------------------------------------------ sizing
def test_15x5_fits_inside_padding_and_keeps_aspect():
    geom = ex.compute_geometry(600, 200, 300, ex.SizeChoice.box(15, 5), margin_mm=0.5)
    assert geom.content_w_mm <= 14.0 + 1e-9 and geom.content_h_mm <= 4.0 + 1e-9
    assert max(geom.content_w_mm / 14.0, geom.content_h_mm / 4.0) == pytest.approx(1.0)
    assert geom.content_w_mm / geom.content_h_mm == pytest.approx(3.0)
    assert geom.box_mm == (15.0, 5.0)
    assert ex.SizeChoice.box(15, 5).is_cell_15x5


def test_15x5_tall_signature_limited_by_height():
    geom = ex.compute_geometry(100, 100, 300, ex.SizeChoice.box(15, 5), 0.5)
    assert geom.content_h_mm == pytest.approx(4.0)
    assert geom.content_w_mm == pytest.approx(4.0)


@pytest.mark.parametrize("box", [(15, 5), (20, 8), (35, 12)])   # 15 × 5, custom size, template
@pytest.mark.parametrize("margin", [0, 0.5, 1.5, 2])
def test_box_margin_applies_and_file_is_box(box, margin):
    """Remark 7: «Поле рамки» works in every box mode; the file stays exactly the box."""
    g = ex.compute_geometry(600, 200, 300, ex.SizeChoice.box(*box), margin)
    assert (g.file_w_mm, g.file_h_mm) == (float(box[0]), float(box[1]))
    assert ex.FIT_FILE_IS_BOX
    ox, oy = g.offset_mm
    assert ox >= margin - 1e-9 and oy >= margin - 1e-9
    assert min(ox, oy) == pytest.approx(margin)          # fitted against the binding side
    assert ox == pytest.approx((box[0] - g.content_w_mm) / 2)


def test_box_margin_changes_signature_size():
    g05 = ex.compute_geometry(600, 200, 300, ex.SizeChoice.box(15, 5), 0.5)
    g15 = ex.compute_geometry(600, 200, 300, ex.SizeChoice.box(15, 5), 1.5)
    assert g05.content_h_mm == pytest.approx(4.0) and g15.content_h_mm == pytest.approx(2.0)


def test_default_margin_is_half_mm():
    assert ex.DEFAULT_MARGIN_MM == 0.5


def test_margin_fits():
    assert ex.margin_fits(ex.SizeChoice.box(15, 5), 2.4)
    assert not ex.margin_fits(ex.SizeChoice.box(15, 5), 2.5)
    assert ex.margin_fits(ex.SizeChoice.original(), 20)
    assert not ex.valid_box_size(6, 6, margin_mm=3)


def test_original_uses_dpi_and_margin():
    geom = ex.compute_geometry(600, 300, 300, ex.SizeChoice.original(), 2)
    assert geom.content_w_mm == pytest.approx(50.8)
    assert geom.file_w_mm == pytest.approx(54.8)
    assert geom.file_h_mm == pytest.approx(25.4 + 4)
    assert geom.box_mm is None


def test_no_dpi_falls_back_to_300():
    src = ex.source_from_mask(make_mask(), None)
    assert not src.has_dpi and src.dpi == 300
    geom = ex.compute_geometry(*src.size_px, src.dpi, ex.SizeChoice.original(), 0)
    assert geom.content_w_mm == pytest.approx(src.size_px[0] / 300 * 25.4)


def test_box_too_small_and_validation():
    with pytest.raises(ValueError):
        ex.compute_geometry(10, 10, 300, ex.SizeChoice.box(1, 5), 0.5)
    assert not ex.valid_box_size(1.0, 5)
    assert not ex.valid_box_size(None, 5)
    assert ex.valid_box_size(20, 8)


def test_size_choice_for_key():
    sizes = [{"id": "7", "name": "Штамп", "w_mm": 20, "h_mm": 8}]
    assert ex.size_choice_for_key("original", sizes).kind == "original"
    c = ex.size_choice_for_key("tpl:7", sizes)
    assert (c.box_w_mm, c.box_h_mm) == (20, 8)
    assert ex.size_choice_for_key("tpl:missing", sizes).is_cell_15x5
    assert ex.size_choice_for_key("custom", sizes, (30, 10)).box_w_mm == 30


def test_tight_bbox_crop(source):
    w, h = source.size_px
    assert source.mask[0].any() and source.mask[-1].any()
    assert source.mask[:, 0].any() and source.mask[:, -1].any()
    assert w <= 600 and h <= 200


# ------------------------------------------------------------------ colours
def test_resolve_color():
    custom = [{"id": "1", "name": "Фиолетовый", "hex": "#5B3FA0"}]
    assert ex.resolve_color("black", custom, None) == (0, 0, 0)
    assert ex.resolve_color("blue", custom, None) == ex.hex_to_rgb("#1B2A8A")
    assert ex.resolve_color("custom:1", custom, None) == (0x5B, 0x3F, 0xA0)
    assert ex.resolve_color("as_photo", custom, (10, 20, 30)) == (10, 20, 30)
    # unknown → default blue
    assert ex.resolve_color("custom:404", custom, None) == ex.hex_to_rgb("#1B2A8A")


def test_remove_custom_color_resets_default():
    custom = [{"id": "1", "hex": "#5B3FA0"}, {"id": "2", "hex": "#000001"}]
    left, default = ex.remove_custom_color(list(custom), "1", "custom:1")
    assert [c["id"] for c in left] == ["2"] and default == "blue"
    left, default = ex.remove_custom_color(list(custom), "2", "black")
    assert default == "black"


def test_remove_custom_size_resets_default():
    sizes = [{"id": "3", "w_mm": 20, "h_mm": 8}]
    left, default = ex.remove_custom_size(list(sizes), "3", "tpl:3")
    assert left == [] and default == "15x5"


def test_hex_roundtrip():
    assert ex.rgb_to_hex(ex.hex_to_rgb("#1b2a8a")) == "#1B2A8A"


# ------------------------------------------------------------------ PNG
def test_png_15x5_600dpi_is_box_size(source):
    job = ex.ExportJob(source, ex.SizeChoice.box(15, 5), 0.5, (27, 42, 138), 600, ("PNG",))
    data = ex.build_outputs(job)["PNG"]
    img = Image.open(io.BytesIO(data))
    assert img.mode == "RGBA"
    assert img.size == (354, 118)  # 15 × 5 mm at 600 DPI
    assert round(img.info["dpi"][0]) == 600
    a = np.asarray(img)[..., 3]
    assert a.max() == 255 and a.min() == 0
    assert ((a > 0) & (a < 255)).any(), "edges must be anti-aliased"
    pad = ex.mm_to_px(0.5, 600) - 1  # 0.5 mm transparent padding on every side
    assert a[:pad].max() == 0 and a[-pad:].max() == 0
    assert a[:, :pad].max() == 0 and a[:, -pad:].max() == 0
    ys, xs = np.nonzero(a)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    assert abs(cx - 354 / 2) <= 2 and abs(cy - 118 / 2) <= 2  # centred
    rgb = np.asarray(img)[..., :3][a > 0]
    assert (rgb == (27, 42, 138)).all()


@pytest.mark.parametrize("dpi,expected", [(150, (89, 30)), (300, (177, 59)), (600, (354, 118))])
def test_png_box_px(source, dpi, expected):
    geom = ex.compute_geometry(*source.size_px, source.dpi, ex.SizeChoice.box(15, 5), 2)
    assert ex.render_png(source, geom, (0, 0, 0), dpi).size == expected


@pytest.mark.parametrize("dpi", [150, 300, 600])
def test_png_original_with_margin(source, dpi):
    geom = ex.compute_geometry(*source.size_px, source.dpi, ex.SizeChoice.original(), 2)
    img = ex.render_png(source, geom, (0, 0, 0), dpi)
    assert img.size == (ex.mm_to_px(geom.file_w_mm, dpi), ex.mm_to_px(geom.file_h_mm, dpi))
    a = np.asarray(img)[..., 3]
    m = ex.mm_to_px(2, dpi)
    assert a[:m - 1].max() == 0 and a[:, :m - 1].max() == 0


@pytest.mark.parametrize("margin", [0.5, 3])
def test_png_box_transparent_band_is_margin(source, margin):
    """Remark 7: in 20 × 8 the empty band on the binding side equals the margin."""
    geom = ex.compute_geometry(*source.size_px, source.dpi, ex.SizeChoice.box(20, 8), margin)
    img = ex.render_png(source, geom, (0, 0, 0), 600)
    assert img.size == (ex.mm_to_px(20, 600), ex.mm_to_px(8, 600))
    a = np.asarray(img)[..., 3]
    ys, xs = np.nonzero(a)
    band = min(xs.min(), ys.min(), a.shape[1] - 1 - xs.max(), a.shape[0] - 1 - ys.max())
    assert abs(band - ex.mm_to_px(margin, 600)) <= 3


# ------------------------------------------------------------------ tracing
@pytest.fixture(scope="module")
def outline(source):
    geom = ex.compute_geometry(*source.size_px, source.dpi, ex.SizeChoice.box(15, 5), 0.5)
    return ex.trace_outline(source, geom)


@pytest.fixture(scope="module")
def centerline(source):
    geom = ex.compute_geometry(*source.size_px, source.dpi, ex.SizeChoice.box(15, 5), 0.5)
    return ex.trace_centerline(source, geom)


def test_svg_document(outline):
    svg = ex.svg_document(outline, (27, 42, 138))
    assert 'width="' in svg and 'mm" height="' in svg and "viewBox=\"0 0 " in svg
    assert 'fill="#1B2A8A"' in svg and "evenodd" in svg
    assert "opacity" not in svg
    import xml.etree.ElementTree as ET
    root = ET.fromstring(svg.encode("utf-8"))
    vb = [float(v) for v in root.get("viewBox").split()]
    assert vb[2] == pytest.approx(outline.file_w_mm, abs=1e-3)
    assert float(root.get("width")[:-2]) == pytest.approx(vb[2], abs=1e-3)


def test_svg_document_is_box_size(outline):
    svg = ex.svg_document(outline, (0, 0, 0))
    assert 'width="15mm" height="5mm" viewBox="0 0 15 5"' in svg


def test_dxf_extents_are_box(centerline):
    doc = ex.dxf_document(centerline, (0, 0, 0))
    assert tuple(doc.header["$EXTMAX"])[:2] == (15, 5)


def test_vector_sizes_kb(outline, centerline):
    kb = ex.vector_sizes_kb(outline, centerline, (27, 42, 138))
    assert set(kb) == {"SVG", "DXF"} and kb["SVG"] >= 1 and kb["DXF"] >= 1


def test_outline_inside_box_padding(outline):
    polys = ex.outline_polygons(outline)
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    assert min(xs) >= 0.5 - 0.15 and max(xs) <= 14.5 + 0.15
    assert min(ys) >= 0.5 - 0.15 and max(ys) <= 4.5 + 0.15


def test_outline_stays_inside_file(outline):
    polys = ex.outline_polygons(outline)
    assert polys
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    assert min(xs) >= -0.2 and max(xs) <= outline.file_w_mm + 0.2
    assert min(ys) >= -0.2 and max(ys) <= outline.file_h_mm + 0.2


def test_chord_step(outline):
    polys = ex.outline_polygons(outline, 0.05)
    steps = [math.dist(a, b) for p in polys for a, b in zip(p, p[1:])]
    assert np.percentile(steps, 95) <= 0.1


def test_dxf_r2010_centerline_polylines_no_hatch(centerline, tmp_path):
    """Remark 9: open centreline LWPOLYLINEs with the chosen thickness; no HATCH, no SPLINE."""
    import ezdxf
    data = ex.dxf_bytes(ex.dxf_document(centerline, (27, 42, 138)))
    path = tmp_path / "s.dxf"
    path.write_bytes(data)
    doc = ezdxf.readfile(path)
    assert doc.dxfversion == "AC1024"  # R2010
    assert doc.header["$INSUNITS"] == 4
    assert doc.header["$LWDISPLAY"] == 1
    msp = doc.modelspace()
    types = {e.dxftype() for e in msp}
    assert types == {"LWPOLYLINE"}
    pls = list(msp.query("LWPOLYLINE"))
    assert 1 <= len(pls) <= 3            # one wavy stroke → one (at most a few) polylines
    for pl in pls:
        assert not pl.closed
        assert pl.rgb == (27, 42, 138)
        assert pl.dxf.const_width == pytest.approx(0.18)
        assert pl.dxf.lineweight == 18
        for x, y, *_ in pl.get_points():
            assert -0.01 <= x <= 15.01 and -0.01 <= y <= 5.01


@pytest.mark.parametrize("width,lw", [(0.18, 18), (0.35, 35), (0.5, 50), (0.27, 25), (0.01, 5)])
def test_dxf_line_width_is_written(centerline, width, lw):
    doc = ex.dxf_document(centerline, (0, 0, 0), width)
    pl = doc.modelspace().query("LWPOLYLINE")[0]
    assert pl.dxf.const_width == pytest.approx(width)
    assert pl.dxf.lineweight == lw


def test_dxf_line_width_clamped():
    assert ex.clamp_dxf_line("x") == ex.DEFAULT_DXF_LINE_MM == 0.18
    assert ex.clamp_dxf_line(0) == 0.01 and ex.clamp_dxf_line(99) == 5.0


def test_centerline_runs_along_stroke_middle():
    from core.centerline import centerline_paths
    m = np.zeros((60, 200), dtype=bool)
    m[24:37, 10:190] = True               # 13 px thick horizontal bar, middle row 30.5
    paths = centerline_paths(m)
    assert len(paths) == 1
    pts, closed = paths[0]
    assert not closed
    ys = [y for _, y in pts]
    assert all(abs(y - 30.5) <= 1.0 for y in ys)
    xs = [x for x, _ in pts]
    assert min(xs) < 25 and max(xs) > 175


def test_centerline_ring_is_closed():
    from core.centerline import centerline_paths
    yy, xx = np.mgrid[0:120, 0:120]
    r = np.hypot(yy - 60, xx - 60)
    paths = centerline_paths((r >= 30) & (r <= 38))
    assert len(paths) == 1 and paths[0][1]
    rr = [math.hypot(x - 60, y - 60) for x, y in paths[0][0]]
    assert all(31 <= v <= 37 for v in rr)


def test_centerline_prunes_spurs():
    from core.centerline import centerline_paths
    m = np.zeros((60, 200), dtype=bool)
    m[24:37, 10:190] = True
    m[20:24, 100:102] = True              # a small bump on the edge must not become a branch
    assert len(centerline_paths(m)) == 1


def test_centerline_keeps_real_branches():
    from core.centerline import centerline_paths
    m = np.zeros((200, 200), dtype=bool)
    m[96:104, 10:190] = True              # «+»: two long strokes crossing
    m[10:190, 96:104] = True
    paths = centerline_paths(m)
    total = sum(math.dist(a, b) for pts, _ in paths for a, b in zip(pts, pts[1:]))
    assert total > 300                    # ≈ 2 × 170 px of centreline
    assert 2 <= len(paths) <= 4


def _line_mask(h, w, segments, th=12):
    import cv2
    m = np.zeros((h, w), np.uint8)
    for (x0, y0), (x1, y1) in segments:
        cv2.line(m, (x0, y0), (x1, y1), 255, th, cv2.LINE_AA)
    return m > 127


def _dist_to_segment(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)))
    return math.hypot(px - ax - t * (bx - ax), py - ay - t * (by - ay))


@pytest.mark.parametrize("dy", [60, 110, 160])          # ≈ 7°…19° on each side
def test_centerline_shallow_crossing_has_no_bridge(dy):
    """Remark 11: two strokes crossing at a shallow angle give two long straight strokes — no short
    spurious segment between two junctions, no notch where the strokes share ink."""
    from core.centerline import centerline_paths
    a, b = ((20, 200 - dy), (580, 200 + dy)), ((20, 200 + dy), (580, 200 - dy))
    paths = centerline_paths(_line_mask(400, 600, [a, b]))
    assert len(paths) == 2
    for pts, closed in paths:
        assert not closed
        length = sum(math.dist(p, q) for p, q in zip(pts, pts[1:]))
        assert length > 480                                  # each path is a whole stroke
        seg = min((a, b), key=lambda s: _dist_to_segment(pts[0], *s))
        assert max(_dist_to_segment(p, *seg) for p in pts) < 6   # stays on its own stroke


def test_centerline_shallow_merge_rung_is_dropped():
    """Two nearly parallel strokes touching for a while: each stays one stroke, no cross-bar."""
    from core.centerline import centerline_paths
    a = ((20, 150), (580, 230))
    b = ((20, 250), (580, 130))
    paths = centerline_paths(_line_mask(400, 600, [a, b], th=16))
    assert len(paths) == 2
    assert all(sum(math.dist(p, q) for p, q in zip(pts, pts[1:])) > 480 for pts, _ in paths)


def test_centerline_branch_at_clear_angle_is_kept():
    """«λ»: a branch leaving a stroke at ≈ 35° stays a separate line that reaches the stroke."""
    from core.centerline import centerline_paths
    a = ((40, 380), (300, 40))
    b = ((170, 210), (420, 380))
    paths = centerline_paths(_line_mask(420, 460, [a, b]))
    assert len(paths) == 2
    longest = max(paths, key=lambda pp: sum(math.dist(p, q) for p, q in zip(pp[0], pp[0][1:])))
    other = [pp for pp in paths if pp is not longest][0][0]
    assert max(_dist_to_segment(p, *a) for p in longest[0]) < 6
    assert min(_dist_to_segment(p, *a) for p in (other[0], other[-1])) < 8   # branch touches the stroke


def test_centerline_short_crossbar_is_not_crossed():
    """«H» with a short cross-bar: the bar stays a bar (the legs are not turned into an «X»)."""
    from core.centerline import centerline_paths
    paths = centerline_paths(_line_mask(300, 300, [((100, 30), (100, 270)), ((170, 30), (170, 270)),
                                                   ((100, 150), (170, 150))]))
    for pts, _ in paths:
        xs = [x for x, _ in pts]
        ys = [y for _, y in pts]
        if max(xs) - min(xs) > 40:            # anything spanning both legs must be the horizontal bar
            assert max(ys) - min(ys) < 12


def test_svg_has_no_thickening(source):
    """Remark 8: the SVG bitmap is the plain 50 % threshold — thin strokes are not widened."""
    assert ex.MIN_STROKE_MM == 0
    thin = np.zeros((80, 400), dtype=bool)
    thin[10:12, 20:380] = True            # 2 px ≈ 0.17 mm at 300 DPI — used to be widened to 0.18 mm+
    thin[70:72, 20:380] = True
    src = ex.source_from_mask(thin, 300)
    geom = ex.compute_geometry(*src.size_px, src.dpi, ex.SizeChoice.original(), 0)
    bm, ppx, ppy = ex.trace_bitmap(src, geom)
    plain = ex.trace_bitmap(src, geom, min_stroke_mm=0)[0]
    assert (bm == plain).all()
    widened = ex.trace_bitmap(src, geom, min_stroke_mm=0.4)[0]
    assert widened.sum() > bm.sum()


def test_svg_stroke_width_matches_source(source):
    """Outline area / stroke length ≈ source stroke width (6 px at 300 DPI = 0.508 mm)."""
    geom = ex.compute_geometry(*source.size_px, source.dpi, ex.SizeChoice.original(), 0)
    outline = ex.trace_outline(source, geom)
    area = 0.0
    for poly in ex.outline_polygons(outline):
        a = 0.0
        for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
            a += x1 * y2 - x2 * y1
        area += abs(a) / 2
    cl = ex.trace_centerline(source, geom)
    length = sum(math.dist(a, b) for pts, _ in cl.paths for a, b in zip(pts, pts[1:]))
    width = area / length
    assert width == pytest.approx(6 / 300 * 25.4, rel=0.15)


def test_thin_strokes_are_thickened():
    m = np.zeros((100, 200), dtype=bool)
    m[50, 10:190] = True  # 1 px wide line
    out = ex.thicken_thin_strokes(m, 5.0)
    assert out.sum() > m.sum() * 3
    assert out[m].all()
    thick = np.zeros_like(m)
    thick[30:70, 10:190] = True
    assert ex.thicken_thin_strokes(thick, 5.0).sum() == thick.sum()


def test_build_all_formats(source):
    job = ex.ExportJob(source, ex.SizeChoice.box(15, 5), 0.5, (0, 0, 0), 300, ex.ALL_FORMATS, 0.35)
    out = ex.build_outputs(job)
    assert set(out) == {"PNG", "SVG", "DXF"}
    assert out["SVG"].startswith(b"<?xml")
    assert b"\n  0\nHATCH\n" not in out["DXF"]


# ------------------------------------------------------------------ names
def test_expand_template():
    when = datetime(2026, 11, 17)
    assert ex.expand_template("подпись_{имя}", "IMG_1051", when) == "подпись_IMG_1051"
    assert ex.expand_template("{name}_{date}", "a", when) == "a_2026-11-17"
    assert ex.expand_template("{дата}", "a", when) == "2026-11-17"


@pytest.mark.parametrize("raw,expected", [
    ('a<b>c:d"e/f\\g|h?i*j', "a_b_c_d_e_f_g_h_i_j"),
    ("name. . ", "name"),
    ("CON", "_CON"),
    ("lpt1.txt", "_lpt1.txt"),
    ("", "signature"),
    ("tab\there", "tab_here"),
])
def test_sanitize(raw, expected):
    assert ex.sanitize_filename(raw) == expected


def test_sanitize_length():
    assert len(ex.sanitize_filename("x" * 400)) == 180


def test_strip_known_ext():
    assert ex.strip_known_ext("a.PNG") == "a"
    assert ex.strip_known_ext("a.txt") == "a.txt"


def test_numbering_covers_whole_format_set(tmp_path):
    (tmp_path / "s.png").write_bytes(b"x")
    assert ex.numbered_base(tmp_path, "s", ["PNG", "DXF"]) == "s (2)"
    (tmp_path / "s (2).dxf").write_bytes(b"x")
    assert ex.numbered_base(tmp_path, "s", ["PNG", "DXF"]) == "s (3)"
    assert ex.numbered_base(tmp_path, "s", ["SVG"]) == "s"


def test_resolve_base_modes(tmp_path):
    (tmp_path / "s.png").write_bytes(b"x")
    assert ex.resolve_base(tmp_path, "s", ["PNG"], "add_number") == ("s (2)", [])
    assert ex.resolve_base(tmp_path, "s", ["PNG"], "replace") == ("s", [])
    base, conflicts = ex.resolve_base(tmp_path, "s", ["PNG", "SVG"], "ask")
    assert base == "s" and conflicts == [tmp_path / "s.png"]
    assert ex.resolve_base(tmp_path, "free", ["PNG"], "ask") == ("free", [])


def test_write_outputs_atomic(tmp_path):
    (tmp_path / "s.png").write_bytes(b"old")
    written = ex.write_outputs(tmp_path, "s", {"PNG": b"new", "DXF": b"d"})
    assert written == [tmp_path / "s.png", tmp_path / "s.dxf"]
    assert (tmp_path / "s.png").read_bytes() == b"new"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                    reason="needs POSIX permissions and non-root")
def test_write_outputs_error_leaves_no_temp(tmp_path):
    ro = tmp_path / "ro"
    ro.mkdir()
    (ro / "s.png").write_bytes(b"old")
    ro.chmod(0o500)
    try:
        with pytest.raises(OSError):
            ex.write_outputs(ro, "s", {"PNG": b"new"})
        assert (ro / "s.png").read_bytes() == b"old"
    finally:
        ro.chmod(0o700)
