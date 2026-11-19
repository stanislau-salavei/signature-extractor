"""Centreline («скелет») of a stroke bitmap for the DXF export (remark 9, 2026-11-17).

The DXF holds one open polyline along the middle of every stroke instead of a filled outline:
Zhang–Suen thinning → pixel graph (end points / junction clusters) → short spurs pruned →
chains joined through junctions left with two branches → smoothed and simplified polylines.
Pure numpy (+ cv2 for the distance transform and Douglas–Peucker); no UI imports.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

Pixel = Tuple[int, int]          # (row, col)
Path = Tuple[List[Tuple[float, float]], bool]   # (points (x, y) in pixels, closed)

# 8 neighbours in circular order N, NE, E, SE, S, SW, W, NW (dy, dx)
_RING = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))
_FOUR = {(-1, 0), (0, 1), (1, 0), (0, -1)}


# --------------------------------------------------------------------------- thinning
def zhang_suen(bm: np.ndarray) -> np.ndarray:
    """Classic Zhang–Suen thinning, vectorised; returns a one-pixel 8-connected skeleton."""
    img = np.pad(bm.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            p2, p3, p4 = img[:-2, 1:-1], img[:-2, 2:], img[1:-1, 2:]
            p5, p6, p7 = img[2:, 2:], img[2:, 1:-1], img[2:, :-2]
            p8, p9 = img[1:-1, :-2], img[:-2, :-2]
            ring = (p2, p3, p4, p5, p6, p7, p8, p9, p2)
            b = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            a = sum(((ring[i] == 0) & (ring[i + 1] == 1)).astype(np.uint8) for i in range(8))
            if step == 0:
                c1 = (p2 * p4 * p6) == 0
                c2 = (p4 * p6 * p8) == 0
            else:
                c1 = (p2 * p4 * p8) == 0
                c2 = (p2 * p6 * p8) == 0
            core = img[1:-1, 1:-1]
            rm = (core == 1) & (b >= 2) & (b <= 6) & (a == 1) & c1 & c2
            if rm.any():
                core[rm] = 0
                changed = True
        if not changed:
            break
    sk = img[1:-1, 1:-1].astype(bool)
    return _remove_staircase(sk)


def _remove_staircase(sk: np.ndarray) -> np.ndarray:
    """Drop redundant corner pixels of 4-connected staircases so lines are strictly 8-thin."""
    img = np.pad(sk.astype(np.uint8), 1)
    for pat in (((-1, 0), (0, 1)), ((0, 1), (1, 0)), ((1, 0), (0, -1)), ((0, -1), (-1, 0))):
        (ay, ax), (by, bx) = pat
        h, w = sk.shape
        core = img[1:-1, 1:-1]
        na = img[1 + ay:1 + ay + h, 1 + ax:1 + ax + w]
        nb = img[1 + by:1 + by + h, 1 + bx:1 + bx + w]
        # opposite diagonal must be empty, otherwise the pixel is part of a junction
        oy, ox = -(ay + by), -(ax + bx)
        no = img[1 + oy:1 + oy + h, 1 + ox:1 + ox + w]
        cnt = sum(img[1 + dy:1 + dy + h, 1 + dx:1 + dx + w] for dy, dx in _RING)
        rm = (core == 1) & (na == 1) & (nb == 1) & (no == 0) & (cnt == 2)
        core[rm] = 0
    return img[1:-1, 1:-1].astype(bool)


# --------------------------------------------------------------------------- graph
def _neighbours(sk: np.ndarray, p: Pixel) -> List[Pixel]:
    y, x = p
    h, w = sk.shape
    out = []
    for dy, dx in _RING:
        yy, xx = y + dy, x + dx
        if 0 <= yy < h and 0 <= xx < w and sk[yy, xx]:
            out.append((yy, xx))
    return out


def _crossings(sk: np.ndarray, p: Pixel) -> int:
    y, x = p
    h, w = sk.shape
    vals = []
    for dy, dx in _RING:
        yy, xx = y + dy, x + dx
        vals.append(bool(0 <= yy < h and 0 <= xx < w and sk[yy, xx]))
    return sum(1 for i in range(8) if not vals[i] and vals[(i + 1) % 8])


def skeleton_graph(sk: np.ndarray):
    """Return (nodes, edges).  nodes: id → (kind, [pixels]); edges: [start_id, end_id, [pixels]].

    End points have one crossing, junctions three or more (adjacent junction pixels form one node).
    Closed loops without nodes get ``None`` for both ends.
    """
    pix = [tuple(map(int, p)) for p in np.argwhere(sk)]
    kind: Dict[Pixel, str] = {}
    for p in pix:
        n = len(_neighbours(sk, p))
        c = _crossings(sk, p)
        if n == 0:
            kind[p] = "dot"
        elif c == 1 or n == 1:
            kind[p] = "end"
        elif c >= 3:
            kind[p] = "junc"
    node_of: Dict[Pixel, int] = {}
    nodes: Dict[int, Tuple[str, List[Pixel]]] = {}
    nid = 0
    for p, k in kind.items():
        if p in node_of:
            continue
        if k == "junc":
            stack, cluster = [p], []
            node_of[p] = nid
            while stack:
                q = stack.pop()
                cluster.append(q)
                for r in _neighbours(sk, q):
                    if kind.get(r) == "junc" and r not in node_of:
                        node_of[r] = nid
                        stack.append(r)
            nodes[nid] = ("junc", cluster)
        else:
            node_of[p] = nid
            nodes[nid] = (k, [p])
        nid += 1

    visited = set()
    seen_pairs = set()
    edges: List[list] = []

    def walk(start_node: Optional[int], first: Pixel, prev: Pixel) -> Tuple[Optional[int], List[Pixel]]:
        path = [first]
        visited.add(first)
        cur, before = first, prev
        while True:
            nb = [q for q in _neighbours(sk, cur) if q != before and q not in path[-3:]]
            hit = [q for q in nb if q in node_of and not (node_of[q] == start_node and len(path) < 2)]
            if hit:
                hit.sort(key=lambda q: (q[0] - cur[0], q[1] - cur[1]) not in _FOUR)
                path.append(hit[0])
                return node_of[hit[0]], path
            free = [q for q in nb if q not in node_of and q not in visited]
            if not free:
                return None, path
            free.sort(key=lambda q: (q[0] - cur[0], q[1] - cur[1]) not in _FOUR)
            before, cur = cur, free[0]
            path.append(cur)
            visited.add(cur)

    for n, (k, cluster) in nodes.items():
        for p in cluster:
            for q in _neighbours(sk, p):
                if q in node_of:
                    m = node_of[q]
                    if m != n:
                        key = (min(n, m), max(n, m), min(p, q), max(p, q))
                        if key not in seen_pairs and (max(n, m), min(n, m)) not in seen_pairs:
                            seen_pairs.add(key)
                            seen_pairs.add((max(n, m), min(n, m)))
                            edges.append([n, m, [p, q]])
                    continue
                if q in visited:
                    continue
                end, path = walk(n, q, p)
                edges.append([n, end, [p] + path])
    # closed loops (no nodes on them)
    for p in pix:
        if p in node_of or p in visited:
            continue
        nb = _neighbours(sk, p)
        end, path = walk(None, p, nb[0] if nb else p)
        closed = len(path) > 2 and max(abs(path[-1][0] - p[0]), abs(path[-1][1] - p[1])) <= 1
        edges.append([None, None, path + ([p] if closed else [])])
    return nodes, edges


def stitch_edges(edges, nodes=None, attach_px: float = 0.0):
    """Two walks can meet in the middle of one stroke and both stop there with a ``None`` end:
    join such halves back into one edge (their loose end pixels touch).  A loose end left over
    that lies within ``attach_px`` of a junction is attached to it (the walk stopped on a pixel
    of a neighbouring edge, just next to the junction)."""
    edges = [list(e) for e in edges]
    changed = True
    while changed:
        changed = False
        loose = []
        for i, (a, b, px) in enumerate(edges):
            if a is None and b is None:
                continue
            if a is None:
                loose.append((i, 0, px[0]))
            if b is None:
                loose.append((i, 1, px[-1]))
        for u in range(len(loose)):
            for v in range(u + 1, len(loose)):
                (i, ei, p), (j, ej, q) = loose[u], loose[v]
                if i == j or max(abs(p[0] - q[0]), abs(p[1] - q[1])) > 1:
                    continue
                pi = edges[i][2] if ei == 1 else edges[i][2][::-1]      # ... → loose end
                pj = edges[j][2] if ej == 0 else edges[j][2][::-1]      # loose end → ...
                start = edges[i][0] if ei == 1 else edges[i][1]
                end = edges[j][1] if ej == 0 else edges[j][0]
                if pi[-1] == pj[0]:
                    pj = pj[1:]
                merged = [start, end, pi + pj]
                edges = [e for k, e in enumerate(edges) if k not in (i, j)] + [merged]
                changed = True
                break
            if changed:
                break
    if nodes and attach_px > 0:
        juncs = [(n, cl) for n, (k, cl) in nodes.items() if k == "junc"]
        for e in edges:
            if (e[0] is None) == (e[1] is None):
                continue
            ei = 0 if e[0] is None else 1
            p = e[2][0] if ei == 0 else e[2][-1]
            best = None
            for n, cl in juncs:
                if n == e[1 - ei]:
                    continue
                q = min(cl, key=lambda c: (c[0] - p[0]) ** 2 + (c[1] - p[1]) ** 2)
                d = math.hypot(q[0] - p[0], q[1] - p[1])
                if d <= attach_px and (best is None or d < best[0]):
                    best = (d, n, q)
            if best is not None:
                e[ei] = best[1]
                e[2] = [best[2]] + e[2] if ei == 0 else e[2] + [best[2]]
    return edges


def _degrees(edges) -> Dict[int, int]:
    deg: Dict[int, int] = {}
    for a, b, _ in edges:
        for n in (a, b):
            if n is not None:
                deg[n] = deg.get(n, 0) + 1
    return deg


def _length(path: Sequence[Pixel]) -> float:
    return sum(math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1]) for i in range(len(path) - 1))


def prune_spurs(nodes, edges, spur_px: float, rounds: int = 3):
    """Remove short branches that end in an end point and hang off a junction."""
    for _ in range(rounds):
        deg = _degrees(edges)
        keep, removed = [], False
        for e in edges:
            a, b, path = e
            ends = [n for n in (a, b) if n is not None]
            leaf = [n for n in ends if nodes[n][0] == "end" and deg.get(n, 0) == 1]
            hub = [n for n in ends if deg.get(n, 0) >= 3]
            dangling = (a is None) != (b is None)          # walk stopped on a visited pixel
            tiny_loop = a is not None and a == b             # ring inside a junction cluster
            if (leaf or dangling or tiny_loop) and (hub or tiny_loop) and _length(path) < spur_px:
                removed = True
                continue
            keep.append(e)
        edges = keep
        if not removed:
            break
    return edges


def _unit(dy, dx):
    n = math.hypot(dy, dx) or 1.0
    return dy / n, dx / n


def _outward(pts, reach: float):
    """Unit direction (dy, dx) from pts[0] to the first point at least ``reach`` away (or the last)."""
    y0, x0 = pts[0]
    y, x = pts[-1]
    for yy, xx in pts[1:]:
        if math.hypot(yy - y0, xx - x0) >= reach:
            y, x = yy, xx
            break
    return _unit(y - y0, x - x0)


def _trim_start(pts, d: float):
    """Drop points from the start of ``pts`` until ``d`` px of length are gone (keeps ≥ 2 points)."""
    acc = 0.0
    k = 0
    while k < len(pts) - 2:
        step = math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1])
        if acc + step > d:
            break
        acc += step
        k += 1
    return pts[k:]


def hermite_join(p_in, p_out, trim: float, reach: float, trim_out: float = None):
    """Join ``p_in`` (ends at a junction) and ``p_out`` (starts at a junction, maybe another one).

    Inside the merged ink blob the skeleton follows the middle of the blob, not the strokes, so
    the last ``trim`` px of both branches are dropped and replaced with a cubic Hermite curve that
    keeps the branch tangents — the stroke goes smoothly through the junction (remark 11)."""
    trim_out = trim if trim_out is None else trim_out
    li, lo = _length(p_in), _length(p_out)
    a = _trim_start(p_in[::-1], min(trim, li / 3.0))[::-1]
    b = _trim_start(p_out, min(trim_out, lo / 3.0))
    t0 = _outward(a[::-1], reach)
    t0 = (-t0[0], -t0[1])                     # arriving direction
    t1 = _outward(b, reach)
    if not _tangents_agree(a[-1], t0, b[0], t1):
        return p_in + p_out[1:]                # odd geometry: keep the skeleton as it is
    curve = _hermite(a[-1], t0, b[0], t1)
    return a + curve + b


def _tangents_agree(p0, t0, p1, t1, min_dot: float = 0.35) -> bool:
    """Both tangents point roughly along the chord p0 → p1 (else a Hermite curve would loop)."""
    c = _unit(p1[0] - p0[0], p1[1] - p0[1])
    return t0[0] * c[0] + t0[1] * c[1] >= min_dot and t1[0] * c[0] + t1[1] * c[1] >= min_dot


def _reattach(paths, node, trim: float, reach: float, c):
    """Branches still ending at ``node`` (where another stroke now runs smoothly through the
    junction) lose their last ``trim`` px inside the blob and merge into the nearest stroke ``trim``
    px past the junction centre ``c``, on the side that keeps the branch direction — a teardrop
    loop flows into the stem instead of ending with a stub or a cross-bar."""
    for pi, pth in enumerate(paths):
        if pth is None:
            continue
        for e in (0, 1):
            if pth[e] != node:
                continue
            best_k = None
            for qi, other in enumerate(paths):
                if other is None or qi == pi or len(other[2]) < 3:
                    continue
                for k, (y, x) in enumerate(other[2]):
                    d2 = (y - c[0]) ** 2 + (x - c[1]) ** 2
                    if best_k is None or d2 < best_k[0]:
                        best_k = (d2, qi, k)
            if best_k is None or best_k[0] > (2 * trim) ** 2:
                continue
            stroke, k = paths[best_k[1]][2], best_k[2]
            pts = pth[2] if e == 0 else pth[2][::-1]
            pts = _trim_start(pts, min(trim, _length(pts) / 3.0))
            d = _outward(pts, reach)
            t_arr = (-d[0], -d[1])
            best = None
            for seg in (stroke[k:], stroke[:k + 1][::-1]):
                if len(seg) < 2:
                    continue
                seg = _trim_start(seg, min(trim, _length(seg) / 2.0))
                t = _outward(seg, reach)
                score = t[0] * t_arr[0] + t[1] * t_arr[1]
                if best is None or score > best[0]:
                    best = (score, seg[0], t)
            if best is None or best[0] < 0.7:
                continue                        # the branch leaves at a clear angle: keep its end
            _, q, tq = best
            if not _tangents_agree(pts[0], t_arr, q, tq):
                continue
            pts = [q] + _hermite(pts[0], t_arr, q, tq)[::-1] + pts
            pth[2] = pts if e == 0 else pts[::-1]
            pth[e] = None                       # now a free end lying on the stroke


def _hermite(p0, t0, p1, t1):
    """Inner points of a cubic Hermite curve p0 → p1 with unit tangents t0, t1 (scaled by the chord)."""
    (y0, x0), (y1, x1) = p0, p1
    D = math.hypot(y1 - y0, x1 - x0)
    if D < 1e-6:
        return []
    n = max(3, int(D))
    out = []
    for k in range(1, n):
        s = k / n
        h00, h10 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s
        h01, h11 = -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
        out.append((h00 * y0 + h10 * t0[0] * D + h01 * y1 + h11 * t1[0] * D,
                    h00 * x0 + h10 * t0[1] * D + h01 * x1 + h11 * t1[1] * D))
    return out


def resolve_bridges(nodes, paths, width_px: float):
    """Remark 11: short junction-to-junction edges («bridges»).

    Where two strokes cross at a shallow angle or run together for a while, the skeleton has two
    3-way junctions joined by a bridge — and the old chain joining produced a short spurious
    segment there.  For each bridge (shorter than ``8 × stroke width``) whose two branches on
    one side come in along the bridge and whose two branches on the other side leave along it
    (each within 60°),
    the strokes are continued through the bridge: each incoming branch is joined with the
    outgoing branch that keeps its direction best (the shared part is used by both strokes).
    Very short bridges that do not fit this pattern are collapsed into one junction.
    """
    bridge_max = 8.0 * width_px
    collapse_max = 1.5 * width_px
    reach = max(6.0, 2.0 * width_px)
    centres = {}

    def centre(n):
        if n not in centres:
            cl = nodes[n][1]
            centres[n] = (sum(p[0] for p in cl) / len(cl), sum(p[1] for p in cl) / len(cl))
        return centres[n]

    def ends_at(n):
        out = []
        for i, pth in enumerate(paths):
            if pth is None:
                continue
            if pth[0] == n:
                out.append((i, 0))
            if pth[1] == n:
                out.append((i, 1))
        return out

    def oriented_from(i, e):
        """Points of path i starting at its end e."""
        pts = paths[i][2]
        return pts if e == 0 else pts[::-1]

    def far_node(i, e):
        return paths[i][1] if e == 0 else paths[i][0]

    changed = True
    while changed:
        changed = False
        for bi, br in enumerate(paths):
            if br is None:
                continue
            a, b, bpts = br
            if a is None or b is None or a == b or nodes[a][0] != "junc" or nodes[b][0] != "junc":
                continue
            L = _length(bpts)
            if L > bridge_max:
                continue
            ea = [(i, e) for i, e in ends_at(a) if i != bi]
            eb = [(i, e) for i, e in ends_at(b) if i != bi]
            if len(ea) != 2 or len(eb) != 2 or len({i for i, _ in ea + eb}) != 4:   # loops: leave to join_chains
                if L <= collapse_max and len(ea) + len(eb) >= 2:
                    _collapse(nodes, paths, centres, bi, a, b, centre)
                    changed = True
                    break
                continue
            ay, ax = centre(a)
            by, bx = centre(b)
            u = _unit(by - ay, bx - ax)
            da = [_outward(oriented_from(i, e), reach) for i, e in ea]
            db = [_outward(oriented_from(i, e), reach) for i, e in eb]
            # crossing / merge at a shallow angle: both strokes arrive along the bridge (< 60°)
            # and leave along it — an «H» cross-bar or a «Ж» does not match
            fits = all(-(d[0] * u[0] + d[1] * u[1]) > 0.5 for d in da) and \
                all(d[0] * u[0] + d[1] * u[1] > 0.5 for d in db)
            # «rung»: two strokes merge at a shallow angle and the skeleton puts a short cross-bar
            # between them — each junction's own two branches form a straight stroke
            rung = -(da[0][0] * da[1][0] + da[0][1] * da[1][1]), -(db[0][0] * db[1][0] + db[0][1] * db[1][1])
            along = sum((-(d[0] * u[0] + d[1] * u[1])) for d in da) / 2 + sum((d[0] * u[0] + d[1] * u[1]) for d in db) / 2
            if min(rung) >= 0.5 and sum(rung) / 2 > along / 2:
                new = []
                for side in (ea, eb):
                    (i, ei), (j, ej) = side
                    pts = hermite_join(oriented_from(i, ei)[::-1], oriented_from(j, ej), 1.2 * width_px, reach)
                    new.append([far_node(i, ei), far_node(j, ej), pts])
                for i in {bi, ea[0][0], ea[1][0], eb[0][0], eb[1][0]}:
                    paths[i] = None
                paths.extend(new)
                changed = True
                break
            if not fits:
                if L <= collapse_max:
                    _collapse(nodes, paths, centres, bi, a, b, centre)
                    changed = True
                    break
                continue

            def straight(ia, ib):   # arriving direction of branch ia vs leaving direction of ib
                return -(da[ia][0] * db[ib][0] + da[ia][1] * db[ib][1])
            pairs = [(0, 0), (1, 1)] if straight(0, 0) + straight(1, 1) >= straight(0, 1) + straight(1, 0) \
                else [(0, 1), (1, 0)]
            new = []
            for ia, ib in pairs:
                (i, ei), (j, ej) = ea[ia], eb[ib]
                p_in = oriented_from(i, ei)[::-1]      # far end → a
                p_out = oriented_from(j, ej)           # b → far end
                pts = hermite_join(p_in, p_out, 1.2 * width_px, reach)
                new.append([far_node(i, ei), far_node(j, ej), pts])
            for i in {bi, ea[0][0], ea[1][0], eb[0][0], eb[1][0]}:
                paths[i] = None
            paths.extend(new)
            changed = True
            break
    return [p for p in paths if p is not None]


def _collapse(nodes, paths, centres, bi, a, b, centre):
    """Merge junction b into a (the bridge between them is dropped)."""
    ca, cb = centre(a), centre(b)
    na, nb = len(nodes[a][1]), len(nodes[b][1])
    nodes[a] = ("junc", nodes[a][1] + nodes[b][1])
    centres[a] = ((ca[0] * na + cb[0] * nb) / (na + nb), (ca[1] * na + cb[1] * nb) / (na + nb))
    paths[bi] = None
    for pth in paths:
        if pth is None:
            continue
        if pth[0] in (a, b):
            pth[0] = a
            pth[2][0] = centres[a]
        if pth[1] in (a, b):
            pth[1] = a
            pth[2][-1] = centres[a]


def join_chains(nodes, edges, width_px: float = 0.0) -> List[Tuple[List[Tuple[float, float]], bool]]:
    """Merge edges through nodes of degree 2; junction ends snap to the cluster centre."""
    def centre(n):
        cl = nodes[n][1]
        return (sum(p[0] for p in cl) / len(cl), sum(p[1] for p in cl) / len(cl))

    nodes = dict(nodes)
    paths = []
    for a, b, px in edges:
        pts = [(float(y), float(x)) for y, x in px]
        if a is not None and nodes[a][0] == "junc":
            pts[0] = centre(a)
        if b is not None and nodes[b][0] == "junc":
            pts[-1] = centre(b)
        paths.append([a, b, pts])
    if width_px > 0:
        paths = resolve_bridges(nodes, paths, width_px)
    def merge(i, ei, j, ej, node=None):
        pi, pj = paths[i], paths[j]
        a_pts = pi[2] if ei == 1 else pi[2][::-1]
        a_start = pi[0] if ei == 1 else pi[1]
        b_pts = pj[2] if ej == 0 else pj[2][::-1]
        b_end = pj[1] if ej == 0 else pj[0]
        paths[i] = None
        paths[j] = None
        if width_px > 0 and node is not None and nodes[node][0] == "junc":
            pts = hermite_join(a_pts, b_pts, 1.2 * width_px, max(6.0, 2.0 * width_px))
            smooth_nodes.add(node)
        else:
            pts = a_pts + b_pts[1:]
        paths.append([a_start, b_end, pts])

    def outward(i, e, reach=max(6.0, 2.0 * width_px)):
        """Unit direction from the node into branch ``i`` (end ``e``), measured ``reach`` px along."""
        pts = paths[i][2] if e == 0 else paths[i][2][::-1]
        y0, x0 = pts[0]
        for y, x in pts[1:]:
            if math.hypot(y - y0, x - x0) >= reach:
                break
        dy, dx = y - y0, x - x0
        n = math.hypot(dy, dx) or 1.0
        return dy / n, dx / n

    done = set()
    smooth_nodes = set()
    while True:
        inc: Dict[int, List[Tuple[int, int]]] = {}
        for i, pth in enumerate(paths):
            if pth is None:
                continue
            a, b, _ = pth
            if a is not None:
                inc.setdefault(a, []).append((i, 0))
            if b is not None:
                inc.setdefault(b, []).append((i, 1))
        # 1) pass-through nodes: exactly two branches
        target = next((n for n, lst in inc.items() if len(lst) == 2 and lst[0][0] != lst[1][0]), None)
        if target is not None:
            (i, ei), (j, ej) = inc[target]
            merge(i, ei, j, ej, target)
            continue
        # 2) junctions: continue the straightest pair of branches through the node (no notch at
        #    the joint, an «X» crossing becomes two long strokes)
        best = None
        for n, lst in inc.items():
            if n in done or len(lst) < 3:
                continue
            dirs = [outward(i, e) for i, e in lst]
            cand = None
            for u in range(len(lst)):
                for v in range(u + 1, len(lst)):
                    if lst[u][0] == lst[v][0]:
                        continue
                    dot = dirs[u][0] * dirs[v][0] + dirs[u][1] * dirs[v][1]
                    if dot < -0.6 and (cand is None or dot < cand[0]):
                        cand = (dot, u, v)
            if cand is None:
                done.add(n)
                continue
            best = (n, lst[cand[1]], lst[cand[2]])
            break
        if best is None:
            break
        n, (i, ei), (j, ej) = best
        merge(i, ei, j, ej, n)
    if width_px > 0:
        for n in smooth_nodes:
            _reattach(paths, n, 1.2 * width_px, max(6.0, 2.0 * width_px), centre(n))
    paths = [p for p in paths if p is not None]
    out = []
    for a, b, pts in paths:
        closed = (a is None and b is None and len(pts) > 2 and pts[0] == pts[-1]) or (a is not None and a == b)
        if closed and pts[0] == pts[-1]:
            pts = pts[:-1]
        out.append(([(x, y) for y, x in pts], closed))
    return out


# --------------------------------------------------------------------------- smoothing
def smooth_path(pts: List[Tuple[float, float]], closed: bool, radius: int = 2) -> List[Tuple[float, float]]:
    """Moving average over ±radius points (end points of open paths stay where they are)."""
    n = len(pts)
    if n < 3 or radius <= 0:
        return list(pts)
    arr = np.asarray(pts, dtype=float)
    out = arr.copy()
    for i in range(n):
        if not closed and (i == 0 or i == n - 1):
            continue
        r = radius if closed else min(radius, i, n - 1 - i)
        idx = [(i + k) % n for k in range(-r, r + 1)]
        out[i] = arr[idx].mean(axis=0)
    return [tuple(p) for p in out]


def simplify_path(pts: List[Tuple[float, float]], closed: bool, tol: float) -> List[Tuple[float, float]]:
    if len(pts) < 3 or cv2 is None:
        return list(pts)
    a = np.asarray(pts, dtype=np.float32).reshape(-1, 1, 2)
    s = cv2.approxPolyDP(a, float(tol), bool(closed)).reshape(-1, 2)
    return [(float(x), float(y)) for x, y in s]


# --------------------------------------------------------------------------- main entry
def centerline_paths(bm: np.ndarray, spur_px: Optional[float] = None) -> List[Path]:
    """Bitmap (bool, True = ink) → list of (points in pixel coordinates (x, y), closed)."""
    if not bm.any():
        return []
    sk = zhang_suen(bm)
    width_px = 3.0
    if cv2 is not None:
        dist = cv2.distanceTransform(bm.astype(np.uint8), cv2.DIST_L2, 3)
        vals = dist[sk]
        if vals.size:
            width_px = max(2.0, 2.0 * float(np.median(vals)))      # typical stroke width
    if spur_px is None:
        spur_px = max(3.0, 1.2 * width_px)
    nodes, edges = skeleton_graph(sk)
    edges = prune_spurs(nodes, stitch_edges(edges, nodes, max(3.0, width_px)), spur_px)
    out = []
    for pts, closed in join_chains(nodes, edges, width_px):
        # pixel centres
        pts = [(x + 0.5, y + 0.5) for x, y in pts]
        if len(pts) == 1:
            x, y = pts[0]
            pts = [(x - 0.5, y), (x + 0.5, y)]   # a dot (e.g. over «i») stays visible as a tiny dash
        pts = smooth_path(pts, closed, 3)
        pts = smooth_path(pts, closed, 3)
        pts = simplify_path(pts, closed, 0.25)
        if len(pts) >= 2:
            out.append((pts, closed))
    return out
