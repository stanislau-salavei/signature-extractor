"""Remark 72: plain ruling (straight lines without verticals) is removed from the mask
without cutting the signature.
* candidates: straight thin lines ≥ RULE_MIN_MM (opening with line kernels at ±3° around horizontal / vertical);
* a candidate is ruling if it runs past the other ink of its band by ≥ RULE_PAST_MM on BOTH ends (ruling crosses
  the signature; a signature's own straight stroke starts or ends inside it — фото 1), or it is a lone line
  ≥ RULE_LONE_MM with no other ink in its band;
* inside a table (``table=True``) every straight line ≥ RULE_MIN_MM goes;
* where a stroke crosses the line the pixels stay: only line pixels whose run across the line is no thicker
  than the line itself are removed."""
import math
from typing import Optional
import logging
import numpy as np, cv2

log = logging.getLogger(__name__)

RULE_MIN_MM = 25.0
RULE_PAST_MM = 5.0
RULE_LONE_MM = 60.0
RULE_BAND_MM = 8.0
RULE_GAP_MM = 1.5
HEAL_PX = 2
DEBUG = False
ANGLES = (-3.0, -1.5, 0.0, 1.5, 3.0)


def _opening(m8, L, vertical, gap=0):
    acc = np.zeros(m8.shape, np.uint8)
    if gap > 1:      # bridge small breaks of a pale line first (the result is cut back to the mask)
        m8 = cv2.morphologyEx(m8, cv2.MORPH_CLOSE, np.ones((gap, 1) if vertical else (1, gap), np.uint8))
    # a thin tilted line steps by a pixel now and then: thicken across the line so the kernel fits
    m8 = cv2.dilate(m8, np.ones((1, 3) if vertical else (3, 1), np.uint8))
    for ang in ANGLES:
        r = math.radians(ang); dx, dy = math.cos(r) * (L - 1) / 2.0, math.sin(r) * (L - 1) / 2.0
        if vertical:
            dx, dy = dy, dx
        kw, kh = int(abs(dx)) * 2 + 1, int(abs(dy)) * 2 + 1
        k = np.zeros((kh, kw), np.uint8); cx, cy = kw // 2, kh // 2
        cv2.line(k, (int(round(cx - dx)), int(round(cy - dy))), (int(round(cx + dx)), int(round(cy + dy))), 1, 1)
        acc |= cv2.morphologyEx(m8, cv2.MORPH_OPEN, k)
    return acc


def _runs(mask, axis):
    """Length of the run of mask pixels through each pixel along ``axis`` (0 = vertical runs)."""
    m = mask if axis == 0 else mask.T
    h = m.shape[0]
    up = np.zeros(m.shape, np.int32); dn = np.zeros(m.shape, np.int32)
    prev = np.zeros(m.shape[1], np.int32)
    for y in range(h):
        prev = np.where(m[y], prev + 1, 0); up[y] = prev
    prev = np.zeros(m.shape[1], np.int32)
    for y in range(h - 1, -1, -1):
        prev = np.where(m[y], prev + 1, 0); dn[y] = prev
    run = up + dn - 1
    return run if axis == 0 else run.T


def ruling(mask: np.ndarray, ppm: float, table: bool = False) -> Optional[np.ndarray]:
    L = int(round(RULE_MIN_MM * ppm))
    if L < 20 or min(mask.shape) < L // 2 or not mask.any():
        return None
    h, w = mask.shape
    m8 = mask.astype(np.uint8)
    out = np.zeros(mask.shape, bool)
    past, lone, band = RULE_PAST_MM * ppm, RULE_LONE_MM * ppm, int(round(RULE_BAND_MM * ppm))
    cand_all = np.zeros(mask.shape, bool)
    opened = {}
    for vertical in (False, True):
        opened[vertical] = (_opening(m8, L, vertical, max(2, int(round(RULE_GAP_MM * ppm)))) > 0) & mask
        cand_all |= opened[vertical]
    if not cand_all.any():
        return None
    grown_all = cv2.dilate(cand_all.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    rest = mask & ~grown_all
    for vertical in (False, True):
        op = opened[vertical]
        if not op.any():
            continue
        n, lab, st, _ = cv2.connectedComponentsWithStats(op.astype(np.uint8), connectivity=8)
        run = None
        for i in range(1, n):
            x, y, cw, ch, _a = st[i]
            length = ch if vertical else cw
            ok = table
            if not ok:
                if vertical:
                    sub = rest[:, max(0, x - band):min(w, x + cw + band)]
                    ys = np.flatnonzero(sub.any(axis=1)); lo_, hi_ = y, y + ch
                else:
                    sub = rest[max(0, y - band):min(h, y + ch + band), :]
                    ys = np.flatnonzero(sub.any(axis=0)); lo_, hi_ = x, x + cw
                if ys.size == 0:
                    ok = length >= lone
                else:
                    ok = lo_ <= ys.min() - past and hi_ >= ys.max() + past
                pass   # (a «spans 60 % of the photo» rule cut tight PNGs: фото 2, IMG_1041)
            if DEBUG:
                log.debug('cand %s %s len %s ok %s', vertical, (x, y, cw, ch), length, ok)
            if not ok:
                continue
            comp = lab == i
            if run is None:
                run = _runs(mask, 0 if not vertical else 1)
            t = float(np.percentile(run[comp], 25))        # the line's own thickness (strokes along it are thicker)
            # the straight line itself (robust fit): a stroke that runs along the line for a while and
            # leaves it is not part of it (photo 1's tail next to a ruled line)
            ys_, xs_ = np.nonzero(comp)
            vx, vy, x0_, y0_ = cv2.fitLine(np.column_stack([xs_, ys_]).astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
            yy, xx = np.mgrid[max(0, y - 3):min(h, y + ch + 3), max(0, x - 3):min(w, x + cw + 3)]
            dist = np.abs((xx - x0_) * vy - (yy - y0_) * vx)
            near = np.zeros(mask.shape, bool)
            near[yy, xx] = dist <= t / 2.0 + 1.0
            line_px = near & mask & (run <= t + max(2.0, 0.3 * ppm))
            # a stroke crossing (or ending on) the line has ink just beside the line band: keep those columns
            d = int(math.ceil(t / 2.0 + 2))
            if vertical:
                side = np.roll(mask & ~near, d, 1) | np.roll(mask & ~near, -d, 1)
            else:
                side = np.roll(mask & ~near, d, 0) | np.roll(mask & ~near, -d, 0)
            keep = cv2.dilate(side.astype(np.uint8), np.ones((1, 3) if not vertical else (3, 1), np.uint8)) > 0
            out |= line_px & ~keep
    if out.any():   # heal: line pixels touching the remaining strokes go back (no 1-px breaks at crossings)
        rest_ink = (mask & ~out).astype(np.uint8)
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * HEAL_PX + 1, 2 * HEAL_PX + 1))
        out &= ~(cv2.dilate(rest_ink, k) > 0)
    return out if out.any() else None
