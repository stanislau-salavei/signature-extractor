"""Remark 117 (audit B8): what screen 3 shows, computed and cached outside the UI.

The export page only asks: is the PNG / the trace for this geometry ready, which jobs to run in the
background worker, how large the files are.  Remark 103 (step a): only the traces the chosen formats need
are made — the filled outline for SVG «Как в исходнике», the centreline for DXF and SVG «Заданная толщина».
Audit C8: the SVG / DXF sizes for the badge are computed together with the trace in the worker.
Audit B10: the preview PNG bytes are reused on «Сохранить» when nothing that changes the file differs."""
from __future__ import annotations

from typing import Callable, Dict, Optional, Sequence, Tuple

from core import export as ex


def geom_key(source, geom) -> Optional[tuple]:
    if geom is None:
        return None
    return (id(source), round(geom.content_w_mm, 6), round(geom.content_h_mm, 6),
            round(geom.file_w_mm, 6), round(geom.file_h_mm, 6))


def needed_traces(formats: Sequence[str], svg_mode: str) -> Tuple[bool, bool]:
    """(outline, centreline) the chosen formats need (remark 103a)."""
    svg = "SVG" in formats
    return svg and svg_mode != "stroke", "DXF" in formats or (svg and svg_mode == "stroke")


class ExportPreviewModel:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """New photo / new source: nothing cached."""
        self.png: Optional[tuple] = None        # (key, image, kb, png bytes, geometry)
        self.trace: Optional[tuple] = None      # (geom key, outline or None, centreline or None)
        self._kb: Dict[tuple, float] = {}
        self._gen = 0                           # bumps with every new trace (badge size cache key)

    # ------------------------------------------------------------------ PNG
    @staticmethod
    def png_key(source, geom, rgb, dpi) -> tuple:
        return (geom_key(source, geom), tuple(rgb), dpi)

    def png_ready(self, key) -> bool:
        return bool(self.png and self.png[0] == key)

    @property
    def png_image(self):
        return self.png[1]

    @property
    def png_kb(self):
        return self.png[2]

    def png_job(self, source, geom, rgb, dpi) -> Callable[[], tuple]:
        key = self.png_key(source, geom, rgb, dpi)

        def render():
            img = ex.render_png(source, geom, rgb, dpi)
            data = ex.png_bytes(img, dpi)
            return key, img, ex.estimate_kb(len(data)), data, geom
        return render

    def set_png(self, res: tuple) -> None:
        self.png = res

    def png_bytes_for(self, source, geom, rgb, dpi) -> Optional[bytes]:
        """B10: the preview PNG file when it was made for exactly this source, geometry, colour and DPI."""
        if self.png_ready(self.png_key(source, geom, rgb, dpi)) and self.png[4] == geom:
            return self.png[3]
        return None

    # ------------------------------------------------------------------ traces
    def trace_ready(self, gkey, formats: Sequence[str], svg_mode: str) -> bool:
        if not self.trace or self.trace[0] != gkey:
            return False
        need_o, need_c = needed_traces(formats, svg_mode)
        return (not need_o or self.trace[1] is not None) and (not need_c or self.trace[2] is not None)

    @property
    def outline(self):
        return self.trace[1] if self.trace else None

    @property
    def centerline(self):
        return self.trace[2] if self.trace else None

    def trace_job(self, source, geom, formats: Sequence[str], svg_mode: str,
                  kb_params: Sequence[tuple] = ()) -> Callable[[], tuple]:
        """Background job: the missing traces for this geometry (a trace made earlier for it is kept), then
        the badge sizes for ``kb_params`` = [(fmt, rgb, dxf_line_mm, svg_mode, svg_line_mm), …] (C8)."""
        gkey = geom_key(source, geom)
        need_o, need_c = needed_traces(formats, svg_mode)
        have = self.trace if self.trace and self.trace[0] == gkey else (gkey, None, None)

        def trace():
            outline = have[1] if have[1] is not None or not need_o else ex.trace_outline(source, geom)
            cl = have[2] if have[2] is not None or not need_c else ex.trace_centerline(source, geom)
            sizes = [(p, _vector_kb(outline, cl, *p)) for p in kb_params]
            return (gkey, outline, cl), sizes
        return trace

    def set_trace(self, res: tuple) -> None:
        trace, sizes = res
        self.trace = trace
        self._gen += 1
        self._kb = {}
        for p, kb in sizes:
            if kb is not None:
                self._kb[p + (self._gen,)] = kb

    def vector_kb(self, fmt, rgb, dxf_line_mm, svg_mode, svg_line_mm):
        """Badge size: SVG / DXF bytes for the cached trace (DXF also depends on colour and thickness)."""
        key = (fmt, tuple(rgb), dxf_line_mm, svg_mode, svg_line_mm, self._gen)
        if key not in self._kb:
            self._kb[key] = _vector_kb(self.outline, self.centerline, *key[:5])
        return self._kb[key]


def _vector_kb(outline, cl, fmt, rgb, dxf_line_mm, svg_mode, svg_line_mm):
    if fmt == "SVG":
        return ex.vector_sizes_kb(outline, cl, rgb, svg_mode=svg_mode, svg_line_mm=svg_line_mm).get("SVG")
    return ex.vector_sizes_kb(None, cl, rgb, dxf_line_mm).get("DXF")
