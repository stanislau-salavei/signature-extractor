"""Remark 73: photos on tinted (yellow) paper.
On such paper the camera tints everything, so the ink looks olive like the print.  After a per-channel
white balance against the paper (each channel / its blurred background) the handwriting is less tinted
than the print, the table lines and the stamp: the pen ink is the group of dark stroke-interior pixels
that lies furthest from the paper tint.  Every dark pixel close to such an ink pixel is kept."""
from typing import Optional

import cv2
import numpy as np

from core.processing import _components, long_lines

PAPER_TINT_C = 20.0      # paper chroma (Lab) from which the paper counts as tinted; white paper ≤ 7, yellow 38–49
MIN_GAP = 5.0            # the two groups along the tint direction must be this far apart
GROW_MM = 0.35
PIECE_PCT = 30.0
SPECK_MM2 = 0.3         # tiny ink pieces far from the strokes (stamp dust) go
# remark 113 (audit B4)
SMALL_SIDE_PX = 400      # a photo with a shorter side is processed at full size (else on a 4× smaller copy)
PAPER_MIN_PX = 100       # fewer sampled paper pixels than this → no paper tint
INNER_MIN_PX = 200       # fewer inner stroke pixels than this → no split by the tint direction
SPECK_NEAR_MM = 1.0           # stroke edges are tinted too: keep dark pixels this close to an ink pixel


def _lerp(a, b, t):
    # numpy's own lerp (numpy/lib/_function_base_impl.py), so results match np.percentile
    diff = b - a
    out = np.asanyarray(a + diff * t)
    sel = t >= 0.5
    out[sel] = (b - diff * (1 - t))[sel]
    return out


def _gperc(g, x, q, n):
    """Per-group percentile q of x (groups g in 0..n-1), like np.percentile(..., method='linear')."""
    out = np.full(n, np.nan)
    if g.size == 0:
        return out
    o = np.lexsort((x, g)); xs = x[o]
    cnt = np.bincount(g, minlength=n); st = np.concatenate([[0], np.cumsum(cnt)[:-1]])
    has = np.flatnonzero(cnt > 0)
    pos = (q / 100.0) * (cnt[has] - 1)
    lo = np.floor(pos).astype(np.int64); hi = np.minimum(lo + 1, cnt[has] - 1)
    t = pos - lo
    a = xs[st[has] + lo]; b = xs[st[has] + hi]
    out[has] = _lerp(a, b, t.astype(a.dtype) if np.issubdtype(a.dtype, np.floating) else t)
    return out


def white_balance(rgb: np.ndarray) -> np.ndarray:
    """Each channel divided by its paper background (closing + blur).  The background is smooth, so it is
    computed on a 4× smaller copy and scaled back — same result, ~10× faster."""
    h, w = rgb.shape[:2]; k = max(15, (min(h, w) // 25) | 1)
    f = 4 if min(h, w) >= SMALL_SIDE_PX else 1
    small = cv2.resize(rgb, (max(1, w // f), max(1, h // f)), interpolation=cv2.INTER_AREA) if f > 1 else rgb
    ks = max(5, (k // f) | 1)
    se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ks, ks))
    bg = cv2.GaussianBlur(cv2.morphologyEx(small, cv2.MORPH_CLOSE, se), (0, 0), ks / 3)
    if f > 1:
        bg = cv2.resize(bg, (w, h), interpolation=cv2.INTER_LINEAR)
    out = rgb.astype(np.float32) / np.maximum(bg.astype(np.float32), 1) * 255
    return np.clip(out, 0, 255).astype(np.uint8)


def paper_tint(lab: np.ndarray, core: np.ndarray):
    # remark 102 (audit C4): every 7th pixel first, then the mask (no copy of the whole frame); the sample is
    # another 1/7 of the paper, so the median may differ in the last digits
    px = lab.reshape(-1, 3)[::7][~core.ravel()[::7]].astype(np.float32)
    if px.shape[0] < PAPER_MIN_PX:
        return None
    a, b = float(np.median(px[:, 1])) - 128.0, float(np.median(px[:, 2])) - 128.0
    c = float(np.hypot(a, b))
    return (a / c, b / c, c) if c >= PAPER_TINT_C else None


def tinted_ink(rgb: np.ndarray, lab: np.ndarray, core: np.ndarray, ppm: float) -> Optional[dict]:
    t = paper_tint(lab, core)
    if t is None:
        return None
    ua, ub, _c = t
    wrgb = white_balance(rgb)
    wlab = cv2.cvtColor(wrgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    proj = (wlab[..., 1] - 128.0) * ua + (wlab[..., 2] - 128.0) * ub       # along the paper tint
    inner = cv2.erode(core.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    if inner.sum() < INNER_MIN_PX:
        return None
    L = wlab[..., 0][inner]
    sel = L <= np.percentile(L, 60)                                          # dark interiors only
    v = proj[inner][sel].astype(np.float32).reshape(-1, 1)
    cv2.setRNGSeed(12345)
    _, lab_k, cen = cv2.kmeans(v, 2, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1), 3, cv2.KMEANS_PP_CENTERS)
    lo, hi = sorted(float(c) for c in cen.ravel())
    if hi - lo < MIN_GAP:
        return None
    thr = (lo + hi) / 2.0
    lk = lab_k.ravel(); ci = int(np.argmin(cen.ravel()))
    A_ = (wlab[..., 1] - 128.0)[inner][sel]; B_ = (wlab[..., 2] - 128.0)[inner][sel]
    ink_c = np.array([np.median(A_[lk == ci]), np.median(B_[lk == ci])]); prt_c = np.array([np.median(A_[lk != ci]), np.median(B_[lk != ci])])
    # decide per stroke piece, not per pixel: table lines are cut out first so they don't glue print to ink
    lines = long_lines(core, ppm)
    body = core & ~lines if lines is not None else core.copy()
    n, lbl, st, _ = _components(body)
    flat = lbl.ravel(); Lf = wlab[..., 0].ravel()
    pa = (wlab[..., 1] - 128.0).ravel(); pb = (wlab[..., 2] - 128.0).ravel()
    pr2 = np.hypot(pa - ink_c[0], pb - ink_c[1]) - np.hypot(pa - prt_c[0], pb - prt_c[1])   # < 0: nearer the ink
    pr = proj.ravel()
    ids = flat[flat > 0]
    # median of each piece's darker pixels along the tint direction
    order = np.argsort(ids, kind="stable"); ids_s = ids[order]; vals = pr[flat > 0][order]; vals2 = pr2[flat > 0][order]; ls = Lf[flat > 0][order]
    med = np.full(n, np.inf, np.float32); med2 = np.full(n, np.inf, np.float32)
    # per piece, vectorised (same numbers as np.percentile, linear interpolation)
    gid = ids_s
    cnt_all = np.bincount(gid, minlength=n)
    lmed = _gperc(gid, ls, 50.0, n)
    dk = ls <= lmed[gid]
    g2 = gid[dk]
    pm = _gperc(g2, vals[dk], PIECE_PCT, n); pm2 = _gperc(g2, vals2[dk], 50.0, n)
    okp = cnt_all >= 3; okp[0] = False
    med[okp] = pm[okp].astype(np.float32); med2[okp] = pm2[okp].astype(np.float32)
    ink_ids = np.flatnonzero((med <= thr) & (med2 <= 0.0))
    ink_px = np.isin(lbl, ink_ids)
    areas = st[:, cv2.CC_STAT_AREA]
    big = ink_ids[areas[ink_ids] >= SPECK_MM2 * ppm * ppm]
    small = ink_ids[areas[ink_ids] < SPECK_MM2 * ppm * ppm]
    if small.size and big.size:
        rr = max(1, int(round(SPECK_NEAR_MM * ppm)))
        near_big = cv2.dilate(np.isin(lbl, big).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rr + 1, 2 * rr + 1))) > 0
        far = np.isin(lbl, small) & ~near_big
        ink_px &= ~far
    grown = ink_px.astype(np.float32)
    if lines is not None:     # where a stroke crosses a table line, keep the line pixels next to the stroke
        r = max(1, int(round(GROW_MM * ppm)))
        near = cv2.dilate(ink_px.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))) > 0
        grown[lines & near] = 1.0
    seed = ink_px & inner
    sel_ink = ink_px & (wlab[..., 0] <= np.percentile(wlab[..., 0][ink_px], 50))
    # the print is black: what tint is left on it after the white balance is the camera cast — take it off the ink
    li = float(np.median(wlab[..., 0][sel_ink])); ai = float(np.median(wlab[..., 1][sel_ink])); bi = float(np.median(wlab[..., 2][sel_ink]))
    fix = np.uint8([[[np.clip(li, 0, 255), np.clip(ai - prt_c[0], 0, 255), np.clip(bi - prt_c[1], 0, 255)]]])
    ink_rgb = tuple(int(x) for x in cv2.cvtColor(fix, cv2.COLOR_LAB2RGB)[0, 0])
    return dict(lines=lines, ink_c=ink_c, prt_c=prt_c, weight=grown, seed=seed, ink_rgb=ink_rgb, thr=thr, centres=(lo, hi), share=float(ink_px.sum()) / max(1, inner.sum()))


# --- cleanup after the table lines are gone (tinted path only) ---------------------------------------------
BRIDGE_PX = 2           # a crossing gap is bridged if ink lies above and below (or left/right) within line width + this
SPECK_MAX_MM2 = 4.0     # pieces smaller than this ...
SPECK_FAR_MM = 1.5      # ... and farther than this from a real stroke are dust
STROKE_MM2 = 10.0       # a «real stroke» piece
ROW_TOL_MM = 0.8        # small pieces whose centres sit on one row ...
ROW_MIN_N = 4           # ... at least this many ...
ROW_SPAN_MM = 25.0      # ... spread over this length are the leftovers of a printed line
BRIDGE_ANGLES = (20, 30, 40, 50, 60, 75, 90, 105, 120, 130, 140, 150, 160)   # stroke slants that may cross a horizontal line


TICKS = True     # remark 73: ticks of the table lines are removed (only crossings and stroke ends stay)


BAND_MIN_MM = 25.0       # 73c: a table line band is at least this long (after joining across strokes)
GAP_ANGLES = (40, 50, 60, 75, 90, 105, 120, 130, 140)
CROSS_RUN_MM = 1.5        # past the line a crossing stroke goes on along the same slant this far
CROSS_FRAC = 0.6         # share of those pixels that must be ink (a hairline may be broken)
END_MIN_ANG = 40          # a stroke ending on the line: its foot is kept along slants this steep ...
END_FAR_MM = 0.0          # ... when no crossing stroke is this close (else it is a tick beside the crossing)
CROSS_ANGLES = tuple(range(20, 161, 10))   # slants (°) at which a stroke may cross a horizontal line


def _crossing(mask, base, band_h, band_v, dark, t, k, run=7, ppm=9.3, steep=False, feet=True):
    """Ink pixels of a table-line band that belong to a stroke crossing the line: from the pixel, a ray at
    some slant leaves the band on both sides and goes on in ink (a tick beside a stroke leaves it onto
    paper).  Plus feet: band ink reached straight down/up from a stroke that ends on the line."""
    h, w = mask.shape
    keep = np.zeros((h, w), bool)
    near = cv2.dilate(base.astype(np.uint8), np.ones((k, k), np.uint8)) > 0
    for band, off in ((band_h, 0), (band_v, 90)):
        cy, cx = np.nonzero(band & near & mask)
        if cy.size == 0:
            continue
        ok = np.zeros(cy.size, bool)
        for ang in CROSS_ANGLES:
            if steep and not (END_MIN_ANG <= ang <= 180 - END_MIN_ANG):
                continue
            th = np.deg2rad(ang + off); dx, dy = np.cos(th), -np.sin(th)
            smax = int(np.ceil((2 * t + 3) / max(0.3, abs(np.sin(np.deg2rad(ang)))))) + 2   # a band may be locally thicker
            todo = np.flatnonzero(~ok)
            if todo.size == 0:
                break
            both = np.zeros(cy.size, bool); both[todo] = True
            for sgn in (1, -1):
                todo = np.flatnonzero(both)
                if todo.size == 0:
                    break
                py, px = cy[todo], cx[todo]
                # walk off the band, then the stroke must go on along the ray for `run` pixels
                cnt = np.zeros(todo.size, np.int32); out_ = np.zeros(todo.size, bool); steps = np.zeros(todo.size, np.int32)
                for s_ in range(1, smax + run + 1):
                    yy = np.rint(py + sgn * s_ * dy).astype(np.int64); xx = np.rint(px + sgn * s_ * dx).astype(np.int64)
                    inside = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
                    yy = np.clip(yy, 0, h - 1); xx = np.clip(xx, 0, w - 1)
                    out_ |= ~band[yy, xx] & inside
                    if s_ > smax and not out_.any():
                        break
                    live = out_ & (steps < run)
                    if s_ > smax and not live.any():
                        break
                    cnt += live & base[yy, xx] & inside; steps += live
                side = out_ & (cnt >= CROSS_FRAC * run)
                both[todo] &= side
            ok |= both
        keep[cy[ok], cx[ok]] = True
    # a stroke that ends on the line (a foot, a corner): reached straight from above/below, no crossing near
    if not feet:
        return keep
    foot = _reach(mask, base, band_h, band_v, 3 * t + 2)
    if keep.any() and END_FAR_MM > 0:
        r = max(1, int(round(END_FAR_MM * ppm)))
        foot &= ~(cv2.dilate(keep.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))) > 0)
    return keep | foot


def _runs_with(m, seed):
    """Vertical runs of m (per column) that contain a seed pixel."""
    h, w = m.shape
    st = m & ~np.vstack([np.zeros((1, w), bool), m[:-1]])
    rid = np.cumsum(st, axis=0, dtype=np.int32) + (np.arange(w, dtype=np.int32) * (h + 1))[None, :]
    rid = np.where(m, rid, 0)
    good = np.zeros(int(rid.max()) + 1, bool)
    good[rid[seed & m]] = True
    good[0] = False
    return good[rid]


def _reach(cand, base, band_h, band_v, n=None):
    """Ink pixels on a line band joined to ink off the band by a straight vertical run (horizontal for a
    vertical line).  A stroke that crosses or ends on the line is reached from above or below; a tick that
    only runs along the line is not."""
    keep = np.zeros(cand.shape, bool)
    seed = base & cand
    for band, vert in ((band_h, True), (band_v, False)):
        room = cand & band
        if not room.any():
            continue
        ys, xs = np.nonzero(room)            # a run needs only the seed pixel next to the band: crop
        c = (slice(max(0, ys.min() - 2), ys.max() + 3), slice(max(0, xs.min() - 2), xs.max() + 3))
        m = room[c] | seed[c]
        r = _runs_with(m, seed[c]) if vert else _runs_with(m.T, seed[c].T).T
        keep[c] |= r & band[c]
    return keep


def _run_median(b):
    """Median length of the vertical runs of a bool mask (thickness of horizontal lines)."""
    if not b.any():
        return 0
    d = np.diff(np.vstack([np.zeros((1, b.shape[1]), np.int8), b.astype(np.int8), np.zeros((1, b.shape[1]), np.int8)]), axis=0)
    st_ = np.nonzero(d.T == 1); en_ = np.nonzero(d.T == -1)
    runs = en_[1] - st_[1]
    return int(np.median(runs)) if runs.size else 0


def _line_kernel(k, ang):
    ker = np.zeros((k, k), np.uint8); c = k // 2; r = c * 1.0
    dx, dy = np.cos(np.deg2rad(ang)) * r, -np.sin(np.deg2rad(ang)) * r
    cv2.line(ker, (int(round(c - dx)), int(round(c - dy))), (int(round(c + dx)), int(round(c + dy))), 1, 1)
    return ker


ROW_FLAT = 1.2          # leftover dashes are flat: height ≤ this (mm)


def _morph(img, op, kernel):
    """morphologyEx as on the whole photo: the line part works on a crop around the lines, and a kernel
    longer than the crop must not take the crop edge for ink (OpenCV's default border does), so the crop is
    padded with empty paper by the kernel size first."""
    py, px = kernel.shape[0], kernel.shape[1]
    big = cv2.copyMakeBorder(img, py, py, px, px, cv2.BORDER_CONSTANT, value=0)
    return cv2.morphologyEx(big, op, kernel)[py:py + img.shape[0], px:px + img.shape[1]]


def _on_lines(mask, alpha, alpha_raw, line_px, ppm, removed):
    """The table-line part of clean(), on a crop around the lines."""
    h, w = mask.shape
    L = max(5, int(round(BAND_MIN_MM * ppm)))   # only long lines (a table border), not a straight stroke
    Lc = max(5, int(round(10 * ppm)))          # join the line across the strokes that cross it
    lp8 = line_px.astype(np.uint8)
    g3 = np.ones((3, 3), np.uint8)
    band_h = cv2.dilate(_morph(_morph(lp8, cv2.MORPH_CLOSE, np.ones((1, Lc), np.uint8)), cv2.MORPH_OPEN, np.ones((1, L), np.uint8)), g3) > 0
    band_v = cv2.dilate(_morph(_morph(lp8, cv2.MORPH_CLOSE, np.ones((Lc, 1), np.uint8)), cv2.MORPH_OPEN, np.ones((L, 1), np.uint8)), g3) > 0
    L5 = max(5, int(round(5 * ppm)))          # gap filling also on shorter (tilted) line pieces, as before
    gap_h = cv2.dilate(_morph(lp8, cv2.MORPH_OPEN, np.ones((1, L5), np.uint8)), g3) > 0
    gap_v = cv2.dilate(_morph(lp8, cv2.MORPH_OPEN, np.ones((L5, 1), np.uint8)), g3) > 0
    if removed is not None and removed.any():      # where the ruling step cut ink, whatever its length
        rm8 = cv2.dilate(removed.astype(np.uint8), g3); l3 = max(3, int(round(3 * ppm)))
        rv = _morph(rm8, cv2.MORPH_OPEN, np.ones((l3, 1), np.uint8)) > 0
        band_v |= rv
        band_h |= (rm8 > 0) & ~rv & ~band_v
    band = band_h | band_v
    gap_h |= band_h; gap_v |= band_v
    if band.any() or gap_h.any() or gap_v.any():
        ys_, xs_ = np.nonzero(band) if band.any() else (np.array([0]), np.array([0]))
        bc = (slice(ys_.min(), ys_.max() + 1), slice(xs_.min(), xs_.max() + 1))
        t = max(3, _run_median(band_h[bc]), _run_median(band_v[bc].T))      # band thickness (px)
        k = 2 * (t + BRIDGE_PX) + 1                                   # a 30° slant still spans the band
        ys, xs = np.nonzero(band | gap_h | gap_v)
        y0, y1, x0, x1 = max(0, ys.min() - k), min(h, ys.max() + k + 1), max(0, xs.min() - k), min(w, xs.max() + k + 1)
        if TICKS:     # 73c: on a table line keep only ink of a stroke that crosses it or ends on it
            # 1) gaps the line cut in a stroke: close along steep slants, only on the line, only dark pixels
            kg = 2 * (max(3, int(round(0.6 * ppm))) + BRIDGE_PX) + 1
            sub = mask[y0:y1, x0:x1].astype(np.uint8); addh = np.zeros(sub.shape, bool); addv = np.zeros(sub.shape, bool)
            for ang in GAP_ANGLES:
                for tgt, a_ in ((addh, ang), (addv, ang + 90)):
                    tgt |= cv2.morphologyEx(sub, cv2.MORPH_CLOSE, _line_kernel(kg, a_)) > 0
            fill = np.zeros((h, w), bool)
            fill[y0:y1, x0:x1] = (addh & gap_h[y0:y1, x0:x1]) | (addv & gap_v[y0:y1, x0:x1])
            fill &= ~mask & (alpha_raw >= 0.5)
            m1 = mask | fill
            # 2) every pixel on the line must belong to a stroke that crosses it (rays) or ends on it (reach)
            base = m1 & ~band
            cs = (slice(y0, y1), slice(x0, x1))        # all the work happens around the lines
            keep = np.zeros((h, w), bool)
            keep[cs] = _crossing(m1[cs], base[cs], band_h[cs], band_v[cs], None, t, k, run=max(4, int(round(CROSS_RUN_MM * ppm))), ppm=ppm)
            keep &= cv2.morphologyEx((keep | base).astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)) > 0
            gone = mask & band & ~keep
            new = base | keep
            add = new & ~mask
            mask = new
            alpha = np.where(add, np.maximum(alpha, alpha_raw), alpha)
            if gone.any():
                fr = (cv2.dilate(gone.astype(np.uint8), g3) > 0) & ~mask
                alpha = np.where(gone | fr, 0.0, alpha)
        else:
            base = mask
            sub = base[y0:y1, x0:x1].astype(np.uint8); addh = np.zeros(sub.shape, bool); addv = np.zeros(sub.shape, bool)
            for ang in BRIDGE_ANGLES:
                for tgt, a_ in ((addh, ang), (addv, ang + 90)):
                    tgt |= cv2.morphologyEx(sub, cv2.MORPH_CLOSE, _line_kernel(k, a_)) > 0
            add = np.zeros((h, w), bool)
            add[y0:y1, x0:x1] = (addh & band_h[y0:y1, x0:x1]) | (addv & band_v[y0:y1, x0:x1])
            add &= ~base & (alpha_raw >= 0.5)
            if add.any():
                mask = mask | add
                alpha = np.where(add, np.maximum(alpha, alpha_raw), alpha)
    return mask, alpha


def clean(mask, alpha, alpha_raw, line_px, ppm, removed=None):
    """Returns (mask, alpha) with (1) strokes rejoined where a removed table line cut them, (2) dashes left
    from a faint table line and (3) small dust far from the strokes removed."""
    h, w = mask.shape
    if line_px is not None and line_px.any():
        src = line_px if removed is None else (line_px | removed)
        ys, xs = np.nonzero(src); mg = int(round(3 * ppm)) + 2
        c = (slice(max(0, ys.min() - mg), min(h, ys.max() + mg + 1)), slice(max(0, xs.min() - mg), min(w, xs.max() + mg + 1)))
        mask = mask.copy(); alpha = alpha.copy()
        mask[c], alpha[c] = _on_lines(mask[c], alpha[c], alpha_raw[c], line_px[c], ppm, None if removed is None else removed[c])
    n, lbl, st, cen = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if n <= 2:
        return mask, alpha
    area = st[:, cv2.CC_STAT_AREA].astype(np.float32) / (ppm * ppm)
    big = np.flatnonzero(area >= STROKE_MM2); big = big[big != 0]
    small = np.flatnonzero((area < SPECK_MAX_MM2)); small = small[small != 0]
    kill = set()
    # (2) rows of flat little dashes
    flat = [i for i in small if st[i, cv2.CC_STAT_HEIGHT] <= ROW_FLAT * ppm]
    if len(flat) >= ROW_MIN_N:
        ys = np.array([cen[i, 1] for i in flat]); order = np.argsort(ys)
        grp = [[flat[order[0]]]]
        for a_, b_ in zip(order[:-1], order[1:], strict=True):
            (grp[-1].append(flat[b_]) if ys[b_] - ys[a_] <= ROW_TOL_MM * ppm else grp.append([flat[b_]]))
        for g in grp:
            xs = [st[i, 0] for i in g] + [st[i, 0] + st[i, 2] for i in g]
            if len(g) >= ROW_MIN_N and max(xs) - min(xs) >= ROW_SPAN_MM * ppm:
                kill.update(g)
    # (3) dust far from strokes
    if big.size:
        r = max(1, int(round(SPECK_FAR_MM * ppm)))
        near = cv2.dilate(np.isin(lbl, big).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))) > 0
        hit = np.unique(lbl[near & (lbl > 0)])
        kill.update(int(i) for i in small if i not in set(hit.tolist()))
    if kill:
        km = np.isin(lbl, list(kill))
        mask = mask & ~km
        fringe = (cv2.dilate(km.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0) & ~mask
        alpha = np.where(km | fringe, 0.0, alpha)
    return mask, alpha
