"""Screen 2 preview: before/after slider, background modes, crop frame, eraser, eyedropper, zoom.

The whole picture is composed with PIL at device resolution (photo, result over the chosen
background, crop frame, divider + handle with soft shadows, translucent pills and the background
segmented control); only texts are Tk items, so everything stays anti-aliased."""
from __future__ import annotations

import logging
import math
import sys
import time
from typing import Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageTk

from core import processing as P
from ui import gfx
from ui.theme import F, S, Scale, Theme, blend, rgb, text_width
from ui.widgets.base import Box, Tooltip
from ui.widgets.overlay import _paste_clip

log = logging.getLogger(__name__)

ZOOM_STEPS = (25, 33, 50, 67, 75, 100, 125, 150, 200, 300, 400, 600, 800)
IS_WIN = sys.platform.startswith("win")
CUR_NWSE = "size_nw_se" if IS_WIN else "bottom_right_corner"
CUR_NESW = "size_ne_sw" if IS_WIN else "bottom_left_corner"
CUR_WE = "sb_h_double_arrow"
CUR_NS = "sb_v_double_arrow"
CHECKER = {"light": ("#FFFFFF", "#E6E8EC"), "dark": ("#2A2A2A", "#1C1C1C")}
BG_WHITE = "#FFFFFF"
BG_DARK = "#1C1C1C"


class Preview(Box):
    def __init__(self, master, app, page):
        super().__init__(master, bg="bg")
        self.app, self.page = app, page
        self.split = 0.38
        self.zoom = 1.0              # relative to «fit»
        self.center: Optional[Tuple[float, float]] = None   # work px at view centre (None = fit)
        self.bg_mode = 0             # 0 checker, 1 white, 2 dark
        self.tool = None             # None | frame | eraser — nothing is active until a tool is clicked
        self.pipette = False
        self.drag = None
        self.pending_frame = None
        self.stroke_pts = []
        self.mouse = None
        self.hover_frame = False
        self._cache = {}
        self._img = None
        # remark 26: live crop-frame preview while dragging
        self._live = None            # (key, ProcessResult of the whole photo) — fast preview source
        self._live_req = None        # key of the request in flight
        self._await = None           # (frame, result shown at release) — keep the live view until reprocessed
        self._redraw_after = None
        self._last_redraw = 0.0
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<ButtonPress-2>", self._pan_start)
        self.bind("<B2-Motion>", self._pan_move)
        self.bind("<ButtonPress-3>", self._pan_start)
        self.bind("<B3-Motion>", self._pan_move)
        self.bind("<MouseWheel>", lambda e: self._wheel(e, 1 if e.delta > 0 else -1))
        self.bind("<Button-4>", lambda e: self._wheel(e, 1))
        self.bind("<Button-5>", lambda e: self._wheel(e, -1))

    # ------------------------------------------------------------------ state
    @property
    def job(self):
        """The current photo once it is loaded and has a result (a batch photo may still be loading)."""
        job = self.app.job
        if job is None or getattr(job, "result", None) is None or \
                (hasattr(job, "photo") and job.photo is None):
            return None
        return job

    def invalidate(self, what="all"):
        if what == "all":
            self._cache.clear()
        else:
            for k in list(self._cache):
                if isinstance(k, str) and k.startswith(what):
                    del self._cache[k]
        self.redraw()

    def refresh(self):
        self._cache.clear()
        super().refresh()

    def inner(self):
        return self.lw - 2, self.lh - 2

    def fit_scale(self) -> float:
        """Logical px per work px at «По размеру»."""
        if not self.job:
            return 1.0
        iw, ih = self.job.photo.size
        w, h = self.inner()
        return min(w / iw, h / ih)

    def scale(self) -> float:
        return self.fit_scale() * self.zoom

    def view_center(self):
        if self.center is None and self.job:
            iw, ih = self.job.photo.size
            return iw / 2, ih / 2
        return self.center or (0, 0)

    def to_view(self, x, y):
        """work px -> logical px inside the preview widget."""
        s = self.scale()
        cx, cy = self.view_center()
        w, h = self.inner()
        return 1 + w / 2 + (x - cx) * s, 1 + h / 2 + (y - cy) * s

    def to_work(self, vx, vy):
        s = self.scale()
        cx, cy = self.view_center()
        w, h = self.inner()
        return cx + (vx - 1 - w / 2) / s, cy + (vy - 1 - h / 2) / s

    def set_zoom(self, z, anchor=None):
        z = max(ZOOM_STEPS[0] / 100, min(ZOOM_STEPS[-1] / 100, z))
        if not self.job:
            return
        if anchor is not None:
            wx, wy = self.to_work(*anchor)
        cx, cy = self.view_center()
        self.zoom = z
        if anchor is not None:
            s = self.scale()
            w, h = self.inner()
            cx = wx - (anchor[0] - 1 - w / 2) / s
            cy = wy - (anchor[1] - 1 - h / 2) / s
        self.center = (cx, cy)
        self._clamp_center()
        self.invalidate("view")
        self.page.on_zoom()

    def fit(self):
        self.zoom = 1.0
        self.center = None
        self.invalidate("view")
        self.page.on_zoom()

    def zoom_step(self, d):
        cur = round(self.zoom * 100)
        if d > 0:
            nxt = next((z for z in ZOOM_STEPS if z > cur), ZOOM_STEPS[-1])
        else:
            nxt = next((z for z in reversed(ZOOM_STEPS) if z < cur), ZOOM_STEPS[0])
        self.set_zoom(nxt / 100)

    def _clamp_center(self):
        if not self.job or self.center is None:
            return
        iw, ih = self.job.photo.size
        s = self.scale()
        w, h = self.inner()
        cx, cy = self.center
        hw, hh = w / 2 / s, h / 2 / s
        cx = min(max(cx, hw), iw - hw) if iw > 2 * hw else iw / 2
        cy = min(max(cy, hh), ih - hh) if ih > 2 * hh else ih / 2
        self.center = (cx, cy)

    def set_tool(self, tool):
        self.tool = tool
        self.pipette = False
        self._update_cursor(None)
        if tool == "frame":
            self._ensure_live()      # warm the live-preview source before the first drag
        self.redraw()

    def set_pipette(self, on):
        self.pipette = on
        self._update_cursor(None)
        self.redraw()

    def set_bg_mode(self, i):
        if i != self.bg_mode:
            self.bg_mode = i
            self.invalidate("view")

    # ------------------------------------------------------------------ composition
    def _bg_image(self, W, H):
        key = ("bg", W, H, self.bg_mode, Theme.mode, Scale.factor)
        im = self._cache.get(key)
        if im is None:
            if self.bg_mode == 0:
                c1, c2 = CHECKER[Theme.mode]
                im = gfx.checker(W, H, max(1, S(10)), c1, c2)
            else:
                im = Image.new("RGBA", (W, H), gfx.rgba(BG_WHITE if self.bg_mode == 1 else BG_DARK))
            self._cache = {k: v for k, v in self._cache.items() if k[0] != "bg"}
            self._cache[key] = im
        return im

    def _layers(self, W, H):
        """(before, after) RGBA images of the inner preview for the current view."""
        job = self.job
        res = job.result
        key = ("view", W, H, self.zoom, self.view_center(), id(res), self.bg_mode, Theme.mode, Scale.factor)
        hit = self._cache.get("view_layers")
        if hit and hit[0] == key:
            return hit[1], hit[2]
        bg = self._bg_image(W, H)
        before, after = bg.copy(), bg.copy()
        s_dev = self.scale() * Scale.factor
        iw, ih = job.photo.size
        cx, cy = self.view_center()
        # visible work rect
        x0, y0 = cx - W / 2 / s_dev, cy - H / 2 / s_dev
        x1, y1 = cx + W / 2 / s_dev, cy + H / 2 / s_dev
        sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(iw, x1), min(ih, y1)
        if sx1 > sx0 and sy1 > sy0:
            dx0, dy0 = int(round((sx0 - x0) * s_dev)), int(round((sy0 - y0) * s_dev))
            dw = max(1, int(round((sx1 - sx0) * s_dev)))
            dh = max(1, int(round((sy1 - sy0) * s_dev)))
            box = (sx0, sy0, sx1, sy1)
            ph = job.photo.image.resize((dw, dh), Image.Resampling.LANCZOS if s_dev < 1 else Image.Resampling.BILINEAR,
                                        box=box)
            before.paste(ph, (dx0, dy0))
            if res is not None:
                rgba = self._result_rgba(res)
                rr = rgba.resize((dw, dh), Image.Resampling.LANCZOS if s_dev < 1 else Image.Resampling.BILINEAR, box=box)
                after.alpha_composite(rr, (dx0, dy0))
        self._cache["view_layers"] = (key, before, after)
        return before, after

    # live crop-frame preview (remark 26) ---------------------------------------
    LIVE_MS = 33                     # redraw at most every ~33 ms while the frame is dragged

    def _live_key(self):
        job = self.job
        st = job.state
        return (id(job.photo), repr(st.params), repr(tuple(st.eraser)))

    def _ensure_live(self):
        """Process the whole photo once in the background (same parameters and eraser, frame = photo).
        While the frame is dragged its content is that result clipped to the frame — instant, and the
        full processing for the new frame runs on release."""
        job = self.job
        if not job or job.result is None:
            return
        key = self._live_key()
        if (self._live and self._live[0] == key) or self._live_req == key:
            return
        self._live_req = key
        photo, st, app = job.photo, job.state, self.app
        iw, ih = photo.size

        def work():
            return P.process(photo, st.params, (0, 0, iw, ih), st.eraser, app._ai_alpha(photo, st.params))

        def done(res):
            if self._live_req == key:
                self._live_req = None
            self._live = (key, res)
            if self._live_frame():
                self._cache.pop("live_view", None)
                self.redraw()

        def fail(exc):
            self._live_req = None
        app.worker.submit("frame_live", work, done, fail)

    def _live_frame(self):
        """Frame to preview live: the one being dragged, or the released one until its result arrives."""
        job = self.job
        if not job or job.result is None:
            return None
        if self.drag is not None and self.drag[0] == "frame" and self.pending_frame:
            return self.pending_frame
        if self._await:
            fr, res = self._await
            if job.result is res:
                return fr
            self._await = None
        return None

    def _live_layer(self, W, H, fr):
        """«After» layer with the live source clipped to frame ``fr`` (view resolution, cheap)."""
        job = self.job
        src = self._live[1] if (self._live and self._live[0] == self._live_key()) else job.result
        key = ("live", W, H, self.zoom, self.view_center(), id(src), self.bg_mode, Theme.mode, Scale.factor)
        hit = self._cache.get("live_view")
        if not hit or hit[0] != key:
            bg = self._bg_image(W, H)
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            s_dev = self.scale() * Scale.factor
            iw, ih = job.photo.size
            cx, cy = self.view_center()
            x0, y0 = cx - W / 2 / s_dev, cy - H / 2 / s_dev
            sx0, sy0 = max(0, x0), max(0, y0)
            sx1, sy1 = min(iw, cx + W / 2 / s_dev), min(ih, cy + H / 2 / s_dev)
            if sx1 > sx0 and sy1 > sy0:
                dx0, dy0 = int(round((sx0 - x0) * s_dev)), int(round((sy0 - y0) * s_dev))
                dw = max(1, int(round((sx1 - sx0) * s_dev)))
                dh = max(1, int(round((sy1 - sy0) * s_dev)))
                rr = self._result_rgba(src).resize(
                    (dw, dh), Image.Resampling.LANCZOS if s_dev < 1 else Image.Resampling.BILINEAR,
                    box=(sx0, sy0, sx1, sy1))
                layer.alpha_composite(rr, (dx0, dy0))
            hit = (key, bg, layer)
            self._cache["live_view"] = hit
        _, bg, layer = hit
        k = Scale.factor
        x, y, fw, fh = fr
        vx0, vy0 = self.to_view(x, y)
        vx1, vy1 = self.to_view(x + fw, y + fh)
        clip = Image.new("L", (W, H), 0)
        ImageDraw.Draw(clip).rectangle(((vx0 - 1) * k, (vy0 - 1) * k, (vx1 - 1) * k - 1, (vy1 - 1) * k - 1), fill=255)
        a = ImageChops.multiply(layer.getchannel("A"), clip)
        cut = layer.copy()
        cut.putalpha(a)
        out = bg.copy()
        out.alpha_composite(cut)
        return out

    def _redraw_live(self):
        """Throttled redraw while dragging the frame (at most every LIVE_MS, with a trailing redraw)."""
        now = time.monotonic()
        wait = self.LIVE_MS / 1000 - (now - self._last_redraw)
        if wait <= 0:
            if self._redraw_after is not None:
                self.after_cancel(self._redraw_after)
                self._redraw_after = None
            self._last_redraw = now
            self.redraw()
        elif self._redraw_after is None:
            def tick():
                self._redraw_after = None
                self._last_redraw = time.monotonic()
                self.redraw()
            self._redraw_after = self.after(int(wait * 1000) + 1, tick)

    def _result_rgba(self, res):
        hit = self._cache.get("res_rgba")
        if hit and hit[0] is res:
            return hit[1]
        im = P.result_rgba(res)
        self._cache["res_rgba"] = (res, im)
        return im

    def draw(self):
        w, h = self.lw, self.lh
        job = self.job
        Wd, Hd = S(w), S(h)
        out = Image.new("RGBA", (Wd, Hd), gfx.rgba(Theme.c("bg")))
        iw_l, ih_l = self.inner()
        W, H = max(1, S(1 + iw_l) - S(1)), max(1, S(1 + ih_l) - S(1))
        if job is None or job.result is None:
            inner = self._bg_image(W, H).copy()
        else:
            before, after = self._layers(W, H)
            live_fr = self._live_frame()
            inner = self._live_layer(W, H, live_fr) if live_fr else after.copy()
            sx = int(round(W * self.split))
            if sx > 0:
                inner.paste(before.crop((0, 0, sx, H)), (0, 0))
            self._draw_frame(inner)
            if self.tool == "eraser" and self.stroke_pts:
                pass
        # rounded clip of the inner area (radius 7 inside the 1 px stroke)
        # the clip mask and the border are cached: rendering them took ~0.4 s per frame and made every
        # drag (split, crop frame) stutter (found while doing remark 26)
        mask = self._static(("clip", iw_l, ih_l, inner.size, Scale.factor),
                            lambda: self._clip_mask(iw_l, ih_l, inner.size))
        out.paste(inner, (S(1), S(1)), mask)
        out.alpha_composite(self._static(("border", w, h, Theme.c("preview_border"), Scale.factor),
                                         lambda: gfx.rrect(w, h, 8, None, Theme.c("preview_border"))))
        self._overlays(out)
        self._img = ImageTk.PhotoImage(out)
        self._imgs.append(self._img)
        self.create_image(0, 0, image=self._img, anchor="nw")
        self._texts(out)
        self._cursor_items()

    _statics: dict = {}

    def _static(self, key, factory):
        """Size/theme-only images shared by every redraw (survive invalidate())."""
        im = Preview._statics.get(key)
        if im is None:
            if len(Preview._statics) > 16:
                Preview._statics.clear()
            im = Preview._statics[key] = factory()
        return im

    @staticmethod
    def _clip_mask(iw_l, ih_l, size):
        m = gfx.rrect(iw_l, ih_l, 7, "#FFFFFF").getchannel("A")
        return m if m.size == size else m.resize(size)

    # crop frame ---------------------------------------------------------------
    def frame_view(self):
        job = self.job
        if not job or job.result is None:
            return None
        fr = self.pending_frame or job.result.frame
        x, y, fw, fh = fr
        x0, y0 = self.to_view(x, y)
        x1, y1 = self.to_view(x + fw, y + fh)
        return x0, y0, x1, y1

    def _draw_frame(self, inner):
        """Crop frame is always visible.  Handles and the solid edit outline only with the frame tool;
        with no tool or with the eraser it is a read-only dashed outline."""
        fv = self.frame_view()
        if not fv:
            return
        k = Scale.factor
        x0, y0, x1, y1 = [(v - 1) * k for v in fv]
        acc = gfx.rgba(Theme.c("accent"))
        ov = Image.new("RGBA", inner.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        d.rectangle((x0, y0, x1, y1), fill=acc[:3] + (10,))
        active = self.tool == "frame"
        editing = active and (self.drag is not None and self.drag[0] == "frame" or self.hover_frame)
        lw = max(1, round(k * (2 if editing else 1)))
        if editing:
            d.rectangle((x0, y0, x1, y1), outline=acc, width=lw)
        else:
            dash, gap = 4 * k, 4 * k
            for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x0, y1, x1, y1), (x0, y0, x0, y1)):
                L = math.hypot(bx - ax, by - ay)
                t = 0.0
                while t < L:
                    t2 = min(L, t + dash)
                    d.line((ax + (bx - ax) * t / L, ay + (by - ay) * t / L,
                            ax + (bx - ax) * t2 / L, ay + (by - ay) * t2 / L), fill=acc, width=lw)
                    t = t2 + gap
        hs = (11 if editing else 9) * k
        for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)) if active else ():
            d.rounded_rectangle((cx - hs / 2, cy - hs / 2, cx + hs / 2, cy + hs / 2), radius=2 * k,
                                fill=(255, 255, 255, 255), outline=acc, width=max(1, round(k)))
        inner.alpha_composite(ov)

    # divider, handle, pills, segmented ---------------------------------------
    def _sprite(self, key, factory):
        k = ("sp",) + key + (Theme.mode, Scale.factor)
        im = self._cache.get(k)
        if im is None:
            im = factory()
            self._cache[k] = im
        return im

    def pill_rects(self):
        t = self.app.t
        b, a = t("process.compare.before"), t("process.compare.after")
        wb = text_width(b, 12, "semibold") + 24 + 2
        wa = text_width(a, 12, "semibold") + 24 + 2
        h = 22.4
        y = self.lh - 13 - h
        return (13, y, wb, h, b), (self.lw - 13 - wa, y, wa, h, a)

    def seg_rects(self):
        t = self.app.t
        labels = [t("process.bg.checker"), t("process.bg.white"), t("process.bg.dark")]
        ws = [text_width(l, 11.5) + 16 for l in labels]
        total = sum(ws) + 2 * 2 + 4 + 2
        x0, y0 = self.lw - 9 - total, 9
        segs = []
        x = x0 + 3
        for l, sw in zip(labels, ws):
            segs.append((x, y0 + 3, sw, 30, l))
            x += sw + 2
        return (x0, y0, total, 36), segs

    def _pill_alpha(self, rect):
        """Labels hide smoothly when the divider comes close (t108u)."""
        x, y, w, h, _ = rect
        sx = 1 + (self.lw - 2) * self.split
        dist = max(x - sx, sx - (x + w), 0)
        return max(0.0, min(1.0, (dist - 4) / 28))

    def _overlays(self, out):
        job = self.job
        k = Scale.factor
        if job is not None and job.result is not None:
            sx = 1 + (self.lw - 2) * self.split
            ih = self.lh - 2
            sh = self._sprite(("divsh", ih), lambda: gfx.shadow_box(2, ih, 0, [(0, 8, 0.35)], 12))
            _paste_clip(out, sh, S(sx - 1 - 12), S(1 - 12))
            line = Image.new("RGBA", (max(1, S(2)), S(ih)), (255, 255, 255, 255))
            _paste_clip(out, line, S(sx - 1), S(1))
            cy = 1 + ih / 2
            hd = self._sprite(("handle",), self._handle_sprite)
            _paste_clip(out, hd, S(sx - 18 - 14), S(cy - 18 - 14))
            for r in self.pill_rects():
                a = self._pill_alpha(r)
                if a <= 0.01:
                    continue
                x, y, w, h, _ = r
                sp = self._sprite(("pill", w), lambda w=w, h=h: self._pill_sprite(w, h))
                if a < 1:
                    sp = sp.copy()
                    sp.putalpha(sp.getchannel("A").point(lambda v, a=a: int(v * a)))
                _paste_clip(out, sp, S(x - 6), S(y - 6))
        (px, py, pw, ph), segs = self.seg_rects()
        panel = self._sprite(("segp", pw), lambda: self._seg_panel(pw, ph))
        _paste_clip(out, panel, S(px - 8), S(py - 8))
        x, y, w, h, _ = segs[self.bg_mode]
        on = self._sprite(("segon", w), lambda: self._seg_on(w, h))
        _paste_clip(out, on, S(x), S(y))

    def _handle_sprite(self):
        pad = 14
        im = gfx.shadow_box(36, 36, 18, [(2, 10, 0.28)], pad)
        im.alpha_composite(gfx.circle(36, "#FFFFFF"), (S(pad), S(pad)))
        ic = gfx.icon("compare", 16, "#1A1A1A")
        im.alpha_composite(ic, (S(pad + 10), S(pad + 10)))
        return im

    def _pill_sprite(self, w, h):
        pad = 6
        dark = Theme.dark()
        im = gfx.shadow_box(w, h, h / 2, [(1, 2, 0.35 if dark else 0.08)], pad)
        fill = "#202020" if dark else "#FFFFFF"
        stroke = blend("#FFFFFF", 0.16, "#202020") if dark else blend("#1A1A1A", 0.22, "#FFFFFF")
        im.alpha_composite(gfx.rrect(w, h, h / 2, fill, stroke, fill_alpha=0.92), (S(pad), S(pad)))
        return im

    def _seg_panel(self, w, h):
        pad = 8
        dark = Theme.dark()
        im = gfx.shadow_box(w, h, 4, [(1, 3, 0.35 if dark else 0.10)], pad)
        fill = "#202020" if dark else "#FFFFFF"
        stroke = blend("#FFFFFF", 0.09, "#202020") if dark else "#E5E5E5"
        im.alpha_composite(gfx.rrect(w, h, 4, fill, stroke, fill_alpha=0.92 if dark else 0.9), (S(pad), S(pad)))
        return im

    def _seg_on(self, w, h):
        im = gfx.rrect(w, h, 4, Theme.c("seg_on"), Theme.c("seg_on_stroke"))
        bar = gfx.rrect(16, 3, 1.5, Theme.c("accent"))
        im.alpha_composite(bar, (S(w / 2 - 8), S(h - 2 - 3)))
        return im

    def _texts(self, out):
        job = self.job
        dark = Theme.dark()
        if job is not None and job.result is not None:
            for r in self.pill_rects():
                a = self._pill_alpha(r)
                if a <= 0.05:
                    continue
                x, y, w, h, label = r
                fg = "#FFFFFF" if dark else "#1A1A1A"
                base = "#202020" if dark else "#FFFFFF"
                col = blend(fg, a, base) if a < 1 else fg
                self.create_text(S(x + w / 2), S(y + h / 2), text=label, font=F(12, "semibold"), fill=col)
        (px, py, pw, ph), segs = self.seg_rects()
        for i, (x, y, w, h, label) in enumerate(segs):
            col = Theme.c("text") if i == self.bg_mode else Theme.c("muted")
            self.create_text(S(x + w / 2), S(y + h / 2 - 2), text=label, font=F(11.5), fill=col)

    # cursor visuals -------------------------------------------------------------
    def _cursor_items(self):
        self.delete("cur")
        if self.mouse is None or not self.job:
            return
        mx, my = self.mouse
        if self._over_ui(mx, my):
            return
        if self.pipette:
            self.put_cached(mx, my - 22, ("ic", "pipette_cursor", 22, Theme.c("text")),
                            lambda: _outlined_icon("pipette_cursor", 22), tags="cur")
        elif self.tool == "eraser":
            r = 14
            self.create_oval(S(mx - r - 1), S(my - r - 1), S(mx + r + 1), S(my + r + 1), outline="#FFFFFF",
                             width=max(1, S(1)), tags="cur")
            self.create_oval(S(mx - r), S(my - r), S(mx + r), S(my + r), outline="#1A1A1A",
                             width=max(1, S(1)), tags="cur")
            if len(self.stroke_pts) > 1:
                pts = []
                for x, y in self.stroke_pts:
                    vx, vy = self.to_view(x, y)
                    pts += [S(vx), S(vy)]
                self.create_line(*pts, fill="#FFFFFF", width=S(28), capstyle="round", joinstyle="round",
                                 stipple="gray50", tags="cur")

    def _over_ui(self, x, y):
        (px, py, pw, ph), _ = self.seg_rects()
        return px <= x <= px + pw and py <= y <= py + ph

    # ------------------------------------------------------------------ hit testing
    def _hit(self, x, y):
        if self._over_ui(x, y):
            return ("seg",)
        if self.job is None or self.job.result is None:
            return None
        sx = 1 + (self.lw - 2) * self.split
        cy = self.lh / 2
        if (x - sx) ** 2 + (y - cy) ** 2 <= 18 ** 2 or abs(x - sx) <= 4:
            return ("split",)
        if self.pipette:
            return ("pipette",)
        if self.tool == "eraser":
            return ("erase",)
        fv = self.frame_view() if self.tool == "frame" else None   # frame is read-only without the tool
        if fv:
            x0, y0, x1, y1 = fv
            tol = 6
            nl, nr = abs(x - x0) <= tol, abs(x - x1) <= tol
            nt, nb = abs(y - y0) <= tol, abs(y - y1) <= tol
            inside_x = x0 - tol <= x <= x1 + tol
            inside_y = y0 - tol <= y <= y1 + tol
            edges = ""
            if inside_y and nl:
                edges += "l"
            if inside_y and nr and not nl:
                edges += "r"
            if inside_x and nt:
                edges += "t"
            if inside_x and nb and not nt:
                edges += "b"
            if edges:
                return ("frame", edges)
            if x0 < x < x1 and y0 < y < y1:
                return ("frame", "move")
        return ("pan",) if self.zoom > 1.0 + 1e-6 else None

    def _update_cursor(self, hit):
        cur = ""
        if hit is None:
            cur = ""
        elif hit[0] == "split":
            cur = CUR_WE
        elif hit[0] in ("pipette", "erase"):
            cur = "none" if IS_WIN or True else "crosshair"
        elif hit[0] == "frame":
            e = hit[1]
            cur = {"move": "fleur", "l": CUR_WE, "r": CUR_WE, "t": CUR_NS, "b": CUR_NS,
                   "lt": CUR_NWSE, "rb": CUR_NWSE, "rt": CUR_NESW, "lb": CUR_NESW}.get(e, "")
        elif hit[0] == "pan":
            cur = "fleur"
        elif hit[0] == "seg":
            cur = ""
        try:
            self.configure(cursor=cur)
        except Exception:
            self.configure(cursor="")

    # ------------------------------------------------------------------ events
    def _xy(self, e):
        return e.x / Scale.factor, e.y / Scale.factor

    def _motion(self, e):
        x, y = self._xy(e)
        self.mouse = (x, y)
        hit = self._hit(x, y)
        self._update_cursor(hit)
        hf = bool(hit and hit[0] == "frame")
        if hf != self.hover_frame:
            self.hover_frame = hf
            self.redraw()
        else:
            self._cursor_items()

    def _leave(self, e):
        self.mouse = None
        if self.hover_frame and self.drag is None:
            self.hover_frame = False
            self.redraw()
        else:
            self._cursor_items()

    def _press(self, e):
        x, y = self._xy(e)
        hit = self._hit(x, y)
        self.drag = None
        if not hit:
            return
        if hit[0] == "seg":
            _, segs = self.seg_rects()
            for i, (sx, sy, sw, sh, _) in enumerate(segs):
                if sx <= x <= sx + sw + 2:
                    self.set_bg_mode(i)
                    break
            return
        if hit[0] == "split":
            self.drag = ("split",)
        elif hit[0] == "pipette":
            wx, wy = self.to_work(x, y)
            iw, ih = self.job.photo.size
            if 0 <= wx < iw and 0 <= wy < ih:
                rgb_ = P.sample_color(self.job.photo, wx, wy)
                self.page.on_pipette(rgb_)
        elif hit[0] == "erase":
            self.stroke_pts = [self.to_work(x, y)]
            self.drag = ("erase",)
        elif hit[0] == "frame":
            self.drag = ("frame", hit[1], (x, y), tuple(self.job.result.frame))
            self.pending_frame = tuple(self.job.result.frame)
            self._ensure_live()
        elif hit[0] == "pan":
            self.drag = ("pan", (x, y), self.view_center())

    def _drag(self, e):
        if not self.drag:
            return
        x, y = self._xy(e)
        self.mouse = (x, y)
        kind = self.drag[0]
        if kind == "split":
            self.split = max(0.0, min(1.0, (x - 1) / max(1, self.lw - 2)))
            self.redraw()
        elif kind == "erase":
            self.stroke_pts.append(self.to_work(x, y))
            self._cursor_items()
        elif kind == "frame":
            _, edges, (x0, y0), (fx, fy, fw, fh) = self.drag
            s = self.scale()
            dx, dy = (x - x0) / s, (y - y0) / s
            iw, ih = self.job.photo.size
            l, t, r, b = fx, fy, fx + fw, fy + fh
            if edges == "move":
                dx = max(-l, min(iw - r, dx))
                dy = max(-t, min(ih - b, dy))
                l, r, t, b = l + dx, r + dx, t + dy, b + dy
            else:
                if "l" in edges:
                    l = min(max(0, l + dx), r - 8)
                if "r" in edges:
                    r = max(min(iw, r + dx), l + 8)
                if "t" in edges:
                    t = min(max(0, t + dy), b - 8)
                if "b" in edges:
                    b = max(min(ih, b + dy), t + 8)
            self.pending_frame = (int(round(l)), int(round(t)), int(round(r - l)), int(round(b - t)))
            self._redraw_live()
        elif kind == "pan":
            _, (x0, y0), (cx, cy) = self.drag
            s = self.scale()
            self.center = (cx - (x - x0) / s, cy - (y - y0) / s)
            self._clamp_center()
            self.invalidate("view")

    def _release(self, e):
        d, self.drag = self.drag, None
        if not d:
            return
        if d[0] == "erase" and self.stroke_pts:
            r = 14 / self.scale()
            stroke = P.EraserStroke(tuple(self.stroke_pts), r)
            self.stroke_pts = []
            self.page.on_erase(stroke)
        elif d[0] == "frame":
            fr, self.pending_frame = self.pending_frame, None
            if self._redraw_after is not None:
                self.after_cancel(self._redraw_after)
                self._redraw_after = None
            if fr and fr != tuple(self.job.result.frame):
                self._await = (fr, self.job.result)    # keep the live view until the full result arrives
                self.page.on_frame(fr)
            self.redraw()

    def _pan_start(self, e):
        x, y = self._xy(e)
        self.drag = ("pan", (x, y), self.view_center())

    def _pan_move(self, e):
        if self.drag and self.drag[0] == "pan":
            self._drag(e)

    def _wheel(self, e, d):
        if not self.job:
            return
        x, y = self._xy(e)
        self.set_zoom(self.zoom * (1.25 if d > 0 else 0.8), anchor=(x, y))


def _outlined_icon(name, size):
    """Eyedropper cursor: dark glyph with a white halo so it reads on any background."""
    base = gfx.icon(name, size, "#FFFFFF")
    from PIL import ImageFilter
    halo = base.filter(ImageFilter.MaxFilter(3))
    glyph = gfx.icon(name, size, "#1A1A1A")
    halo.alpha_composite(glyph)
    return halo
