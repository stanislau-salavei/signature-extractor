"""Signature extraction core (stage 2). No UI imports.

Pipeline (per photo):
  1. load (OpenCV for JPG/PNG/BMP/TIFF/WebP, pi-heif for HEIC/HEIF), EXIF orientation;
  2. working copy limited to WORK_MAX_SIDE px (physical size is kept through the DPI factor);
  3. «Выравнивание фона»: divide by a blurred background estimate (removes shadows, uneven light, yellow paper);
  4. ink darkness -> soft alpha (anti-aliased edges), threshold from «Чувствительность»;
  5. «Фильтр по цвету чернил»: Auto = Lab clustering of dark pixels, a clearly coloured group
     (blue / violet ink) is the signature, grey-black print and ruling are dropped;
     Manual = colour picked with the eyedropper;
  6. crop frame: automatic around the signature (largest ink cluster) or the user frame;
  7. «Удаление шума» (small specks), «Толщина» (dilate / erode), eraser strokes.
"""
from __future__ import annotations

import io
import logging
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageOps

try:
    import cv2
except ImportError:  # pragma: no cover - cv2 is a hard requirement of the app
    logging.getLogger(__name__).debug("module: ImportError caught", exc_info=True)   # remark 81
    cv2 = None

try:
    from pi_heif import register_heif_opener      # remark 99: decode-only build of pillow-heif (no x265 encoder)

    register_heif_opener()
    HAS_HEIF = True
except Exception:  # pragma: no cover
    logging.getLogger(__name__).debug("module: Exception caught", exc_info=True)   # remark 81
    HAS_HEIF = False

log = logging.getLogger(__name__)

OPENCV_EXT = {".jpg", ".jpeg", ".jpe", ".png", ".bmp", ".dib", ".tif", ".tiff", ".webp"}
HEIF_EXT = {".heic", ".heif"}
SUPPORTED_EXT = OPENCV_EXT | HEIF_EXT
MAX_FILE_BYTES = 50 * 1024 * 1024
WORK_MAX_SIDE = 3200
FALLBACK_DPI = 300.0

# Fine-tuning defaults (mockup 09): sensitivity 62, noise removal 35, thickness ±0.
DEFAULT_SENSITIVITY = 62
DEFAULT_DENOISE = 35
DEFAULT_THICKNESS = 0
THICKNESS_RANGE = (-3, 3)


class ImageLoadError(Exception):
    """File is damaged or is not a supported image (dialog 29)."""


# --------------------------------------------------------------------------- inputs
def is_supported_image(path: Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXT


def file_size_mb(path: Path) -> float:
    return Path(path).stat().st_size / (1024 * 1024)


def file_too_large(path: Path) -> bool:
    try:
        return Path(path).stat().st_size > MAX_FILE_BYTES
    except OSError:
        log.debug("file_too_large: OSError caught", exc_info=True)   # remark 81
        return False


@dataclass
class ScanResult:
    photos: List[Path] = field(default_factory=list)
    skipped_other: List[Path] = field(default_factory=list)   # not photos (dialog 04)
    too_large: List[Path] = field(default_factory=list)       # > 50 MB (panel 45 / 46)


def scan_inputs(paths: Sequence[Path]) -> ScanResult:
    """Sort dropped / opened paths into photos, non-photos and files over 50 MB.
    Folders are expanded (one level, sorted by name), hidden files are ignored."""
    res = ScanResult()
    for p in paths:
        p = Path(p)
        if p.is_dir():
            try:
                children = sorted((c for c in p.iterdir() if c.is_file() and not c.name.startswith(".")),
                                  key=lambda c: c.name.lower())
            except OSError:
                log.warning("cannot list folder %s", p, exc_info=True)
                continue
            items = children
        else:
            items = [p]
        for f in items:
            if not is_supported_image(f):
                res.skipped_other.append(f)
            elif file_too_large(f):
                res.too_large.append(f)
            else:
                res.photos.append(f)
    return res


def _normalize(img: Image.Image) -> Image.Image:
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:  # broken EXIF must not stop loading
        log.debug("exif_transpose failed", exc_info=True)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() or img.mode == "P" else "RGB")
    return img


# Remark 54 (2026-11-18): 72 DPI is what cameras, phones and screenshots write when they know nothing
# about the paper (p3.jpg gave 393 × 273 mm).  72 and lower count as «no DPI» (300 DPI fallback,
# «Как в исходнике» shows the no-DPI line); so do absurd values above 4800.
MIN_TRUSTED_DPI = 72.0
MAX_TRUSTED_DPI = 4800.0


def plausible_dpi(value) -> Optional[float]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        log.debug("plausible_dpi: (TypeError, ValueError) caught", exc_info=True)   # remark 81
        return None
    if not math.isfinite(v) or v <= MIN_TRUSTED_DPI + 0.5 or v > MAX_TRUSTED_DPI:
        return None
    return v


def read_dpi(img: Image.Image) -> Optional[float]:
    """DPI stored in the file, or None when the photo has no (believable) DPI data."""
    dpi = img.info.get("dpi")
    if isinstance(dpi, (tuple, list)):
        return plausible_dpi(dpi[0]) if dpi else None
    if isinstance(dpi, (int, float)):
        return plausible_dpi(dpi)
    return None


def load_image(path: Path) -> Tuple[Image.Image, Optional[float]]:
    """Load an approved format. Returns (RGB/RGBA image, DPI or None). Raises ImageLoadError."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXT:
        raise ImageLoadError(path.name)
    try:
        if suffix in HEIF_EXT:
            if not HAS_HEIF:
                raise ImageLoadError(path.name)
            pil = Image.open(path)
            pil.load()
            return _normalize(pil), read_dpi(pil)
        # DPI and EXIF orientation are read with Pillow (metadata only), pixels with OpenCV.
        dpi = None
        orientation = 1
        try:
            with Image.open(path) as meta:
                dpi = read_dpi(meta)
                orientation = meta.getexif().get(0x0112, 1)
        except Exception:
            log.debug("metadata read failed for %s", path, exc_info=True)
        data = np.fromfile(str(path), dtype=np.uint8)
        arr = cv2.imdecode(data, cv2.IMREAD_UNCHANGED) if data.size else None
        if arr is None:
            raise ImageLoadError(path.name)
        if arr.dtype != np.uint8:  # 16-bit PNG / TIFF
            arr = (arr / 257).astype(np.uint8) if arr.dtype == np.uint16 else cv2.convertScaleAbs(arr)
        if arr.ndim == 2:
            img = Image.fromarray(arr, "L").convert("RGB")
        elif arr.shape[2] == 4:
            img = Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGRA2RGBA), "RGBA")
        else:
            img = Image.fromarray(cv2.cvtColor(arr[:, :, :3], cv2.COLOR_BGR2RGB), "RGB")
        transpose = {2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180,
                     4: Image.Transpose.FLIP_TOP_BOTTOM, 5: Image.Transpose.TRANSPOSE,
                     6: Image.Transpose.ROTATE_270, 7: Image.Transpose.TRANSVERSE,
                     8: Image.Transpose.ROTATE_90}.get(orientation)
        if transpose is not None:
            img = img.transpose(transpose)
        return img, dpi
    except ImageLoadError:
        raise
    except Exception as exc:
        log.warning("cannot load %s", path, exc_info=True)
        raise ImageLoadError(path.name) from exc


def load_image_bytes(data: bytes) -> Tuple[Image.Image, Optional[float]]:
    try:
        pil = Image.open(io.BytesIO(data))
        pil.load()
    except Exception as exc:
        raise ImageLoadError("clipboard") from exc
    return _normalize(pil), read_dpi(pil)


# --------------------------------------------------------------------------- params / result
@dataclass(frozen=True)
class ProcessParams:
    flatten: bool = True
    ink_filter: bool = True
    ink_mode: str = "auto"                       # "auto" | "manual"
    ink_rgb: Optional[Tuple[int, int, int]] = None  # manual (eyedropper) colour
    exclude_rgb: Optional[Tuple[int, int, int]] = None  # remark 66: «Исключить цвет» (manual mode only)
    sensitivity: int = DEFAULT_SENSITIVITY       # 0..100
    denoise: int = DEFAULT_DENOISE               # 0..100
    thickness: int = DEFAULT_THICKNESS           # -3..+3, shown as ±0 without units


@dataclass
class Photo:
    """A loaded photo prepared for processing (working resolution)."""
    name: str                       # file name with extension
    stem: str
    image: Image.Image              # RGB working copy
    dpi: Optional[float]            # DPI from file (None = not stored)
    scale: float                    # working px / original px
    rgb: np.ndarray = field(repr=False, default=None)
    lab: np.ndarray = field(repr=False, default=None)

    @property
    def work_dpi(self) -> float:
        return (self.dpi or FALLBACK_DPI) * self.scale

    @property
    def size(self) -> Tuple[int, int]:
        return self.image.size


@dataclass
class ProcessResult:
    alpha: np.ndarray                         # uint8 HxW, soft mask of the signature (whole photo)
    mask: np.ndarray                          # bool HxW, alpha >= 50 %
    frame: Tuple[int, int, int, int]          # x, y, w, h in working px
    auto_frame: Tuple[int, int, int, int]
    stroke_count: int
    size_mm: Tuple[float, float]
    ink_rgb: Tuple[int, int, int]             # colour of the signature on the photo
    ink_state: str                            # "found" | "same" | "manual" | "off"
    frame_is_large: bool                      # frame covers more than half of the sheet
    source_dpi: Optional[float] = None        # DPI stored in the photo (None -> 300 fallback in export)
    source_name: str = ""
    work_dpi: float = FALLBACK_DPI
    doubts: Tuple[str, ...] = ()              # remark 48: reasons for «Требует внимания» (export stays open)

    @property
    def empty(self) -> bool:
        return self.stroke_count == 0

    @property
    def ink_color(self):  # compatibility with core.export.source_from_result
        return self.ink_rgb


def prepare_photo(img: Image.Image, dpi: Optional[float], name: str) -> Photo:
    rgb_img = img
    if img.mode == "RGBA":  # transparent areas -> white paper
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.getchannel("A"))
        rgb_img = bg
    elif img.mode != "RGB":
        rgb_img = img.convert("RGB")
    w, h = rgb_img.size
    scale = 1.0
    if max(w, h) > WORK_MAX_SIDE:
        scale = WORK_MAX_SIDE / max(w, h)
        rgb_img = rgb_img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS)
    rgb = np.asarray(rgb_img, dtype=np.uint8)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    return Photo(name=name, stem=Path(name).stem, image=rgb_img, dpi=dpi, scale=scale, rgb=rgb, lab=lab)


# --------------------------------------------------------------------------- steps
def _flatten(gray: np.ndarray) -> np.ndarray:
    """Background flattening: gray / estimated background (closing + blur)."""
    h, w = gray.shape
    k = max(15, (min(h, w) // 25) | 1)
    bg = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    bg = cv2.GaussianBlur(bg, (0, 0), k / 3)
    norm = np.clip(gray.astype(np.float32) / np.maximum(bg.astype(np.float32), 1.0) * 255.0, 0, 255)
    return norm


def _darkness(photo: Photo, flatten: bool) -> np.ndarray:
    gray = photo.lab[:, :, 0]
    if flatten:
        norm = _flatten(gray)
    else:
        norm = gray.astype(np.float32)
        paper = float(np.percentile(norm, 90))
        norm = np.clip(norm / max(paper, 1.0) * 255.0, 0, 255)
    return 255.0 - norm  # 0 = paper, 255 = darkest ink


def _soft_alpha(dark: np.ndarray, sensitivity: int) -> np.ndarray:
    """Soft (anti-aliased) alpha from ink darkness. Higher sensitivity keeps paler strokes."""
    s = max(0, min(100, sensitivity)) / 100.0
    t_mid = 120.0 - 80.0 * s          # 62 -> ~70
    t_lo, t_hi = t_mid - 22.0, t_mid + 22.0
    a = (dark - t_lo) / (t_hi - t_lo)
    return np.clip(a, 0.0, 1.0)


def _chroma(lab: np.ndarray) -> np.ndarray:
    a = lab[..., 1].astype(np.float32) - 128.0
    b = lab[..., 2].astype(np.float32) - 128.0
    return np.sqrt(a * a + b * b)


def detect_ink(photo: Photo, core_mask: np.ndarray) -> Tuple[Optional[Tuple[int, int, int]], bool]:
    """Auto ink colour: (rgb or None, separated?).  See detect_ink_ex."""
    rgb, separated, _stamp = detect_ink_ex(photo, core_mask)
    return rgb, separated


def detect_ink_ex(photo: Photo, core_mask: np.ndarray) -> Tuple[Optional[Tuple[int, int, int]], bool, bool]:
    """Like detect_ink, plus «the coloured group looked like a stamp» (remark 63: a clearly darker group of
    another colour was taken as the ink instead)."""
    rgb, separated = _detect_ink_raw(photo, core_mask)
    if rgb is None or not separated:
        return rgb, separated, False
    darker = _darker_other_group(photo, core_mask, rgb)
    if darker is not None:
        return darker, True, True
    return rgb, separated, False


DARKER_L_GAP = 20.0        # remark 63: the other group is ≥ 20 L* darker than the found ink …
DARKER_HUE_GAP = 40.0      # … and of another hue (or grey) …
DARKER_SHARE = 0.3         # … and holds ≥ 0.3 of the ink-coloured strokes → it is the signature
DARKER_PERCENTILE = 5.0    # its darkest 5 % give the ink colour (like the eyedropper)
BLUE_MAX_L = 48.0          # remark 64: blue / violet is preferred only when it is dark (stamps: L* 56–58)


def _lab_l(rgb: Sequence[int]) -> float:
    return float(cv2.cvtColor(np.uint8([[list(rgb)]]), cv2.COLOR_RGB2LAB)[0, 0][0]) / 2.55


def _darker_other_group(photo: Photo, core_mask: np.ndarray, ink_rgb: Sequence[int]):
    """Remark 63: a coloured stamp is usually the biggest coloured group and lighter than the pen.  When a
    group of strokes ≥ 20 L* darker and of another hue holds ≥ 0.3 of the ink-coloured strokes, the
    darkest 5 % of that group is the ink.  Returns the rgb or None."""
    hue_t, chroma_t = lab_hue_chroma(ink_rgb)
    if chroma_t < 10.0:
        return None
    t_l = _lab_l(ink_rgb)
    lab = photo.lab
    L = lab[..., 0].astype(np.float32)[core_mask] / 2.55
    a = lab[..., 1].astype(np.float32)[core_mask] - 128.0
    b = lab[..., 2].astype(np.float32)[core_mask] - 128.0
    ch = np.hypot(a, b)
    dh = np.abs((np.degrees(np.arctan2(b, a)) - hue_t + 180.0) % 360.0 - 180.0)
    other = (L < t_l - DARKER_L_GAP) & ((ch < 14.0) | (dh > DARKER_HUE_GAP))
    ink_like = (ch >= 14.0) & (dh <= DARKER_HUE_GAP)
    n_other = int(other.sum())
    if n_other < 60 or n_other < DARKER_SHARE * max(1, int(ink_like.sum())):
        return None
    lo = L[other]
    sel = lo <= np.percentile(lo, DARKER_PERCENTILE)
    rgb = photo.rgb[core_mask][other][sel]
    return tuple(int(v) for v in np.median(rgb, axis=0))


def _detect_ink_raw(photo: Photo, core_mask: np.ndarray) -> Tuple[Optional[Tuple[int, int, int]], bool]:
    """Auto ink colour (t21s): Lab clustering of dark pixels.
    Returns (rgb of the coloured ink group or None, separated?).  ``separated`` is False when
    the signature colour can't be told apart from grey-black print."""
    idx = np.flatnonzero(core_mask)
    if idx.size < 60:
        return None, False
    rng = np.random.default_rng(1)
    if idx.size > 40000:
        idx = rng.choice(idx, 40000, replace=False)
    lab = photo.lab.reshape(-1, 3)[idx].astype(np.float32)
    rgb = photo.rgb.reshape(-1, 3)[idx]
    chroma = np.sqrt((lab[:, 1] - 128) ** 2 + (lab[:, 2] - 128) ** 2)
    colored = chroma > 14.0
    share = float(colored.mean())
    if share < 0.06:  # practically everything is grey / black
        return tuple(int(v) for v in np.median(rgb, axis=0)), False
    # cluster the coloured pixels by hue (a, b) to find the dominant ink
    # remark 52: a stamp on the photo is usually the biggest coloured group — prefer blue / violet ink
    # (Lab hue −150…−30°) over red / orange when there is a fair amount of it
    hue = np.degrees(np.arctan2(lab[:, 2] - 128, lab[:, 1] - 128))
    blue = colored & (hue >= BLUE_HUE[0]) & (hue < BLUE_HUE[1])
    nb = int(blue.sum())
    if nb >= 60 and nb >= 0.08 * int(colored.sum()):
        blue_rgb = tuple(int(v) for v in np.median(rgb[blue], axis=0))
        if _lab_l(blue_rgb) <= BLUE_MAX_L:      # remark 64: a light blue group is a stamp, not a pen
            return blue_rgb, True
    ab = lab[colored][:, 1:3]
    k = 2 if ab.shape[0] > 50 else 1
    if k == 2:
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
        cv2.setRNGSeed(12345)      # remark 76: repeatable clustering
        _, labels, centers = cv2.kmeans(ab, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
        labels = labels.ravel()
        best = int(np.argmax(np.bincount(labels, minlength=k)))
        sel = labels == best
    else:
        sel = np.ones(ab.shape[0], dtype=bool)
    ink_rgb = np.median(rgb[colored][sel], axis=0)
    return tuple(int(v) for v in ink_rgb), True


BLUE_HUE = (-150.0, -30.0)       # Lab hue angle of blue / violet ink (remark 52)
STAMP_HUE = (-30.0, 60.0)        # red / orange — stamp colours (remark 48, criterion 6)


def lab_hue_chroma(rgb: Sequence[int]) -> Tuple[float, float]:
    """(hue angle in degrees, chroma) of an RGB colour in OpenCV Lab."""
    t = cv2.cvtColor(np.uint8([[list(rgb)]]), cv2.COLOR_RGB2LAB)[0, 0].astype(np.float32)
    a, b = float(t[1]) - 128.0, float(t[2]) - 128.0
    return math.degrees(math.atan2(b, a)), math.hypot(a, b)


def _hue_gate(photo: Photo, target_rgb: Sequence[int]) -> Optional[np.ndarray]:
    """Remarks 55 / 56: with a clearly coloured auto ink, keep only pixels whose colour leans towards the
    ink hue — grey-black print (chroma ≈ 0) and red stamp lines (opposite hue) are dropped even when they
    are close in the plain Lab distance.  Chroma is measured along the ink hue, lightly smoothed."""
    _h, tc = lab_hue_chroma(target_rgb)
    if tc < 12.0:
        return None
    t = cv2.cvtColor(np.uint8([[list(target_rgb)]]), cv2.COLOR_RGB2LAB)[0, 0].astype(np.float32)
    ta, tb = (float(t[1]) - 128.0) / tc, (float(t[2]) - 128.0) / tc
    lab = photo.lab.astype(np.float32)
    a = cv2.GaussianBlur(lab[..., 1] - 128.0, (0, 0), 1.0)
    b = cv2.GaussianBlur(lab[..., 2] - 128.0, (0, 0), 1.0)
    proj = a * ta + b * tb
    return np.clip((proj - 0.12 * tc) / (0.18 * tc), 0.0, 1.0)


EXCLUDE_SOFT = 6.0      # remark 66: soft edge (Lab units) between «ink» and «excluded colour»


def exclude_weight(photo: Photo, ink_rgb: Sequence[int], exclude_rgb: Sequence[int]) -> np.ndarray:
    """Remark 66 «Исключить цвет»: 0..1 — pixels closer (in Lab) to the excluded colour than to the ink go."""
    lab = photo.lab.astype(np.float32)
    ti = cv2.cvtColor(np.uint8([[list(ink_rgb)]]), cv2.COLOR_RGB2LAB)[0, 0].astype(np.float32)
    ts = cv2.cvtColor(np.uint8([[list(exclude_rgb)]]), cv2.COLOR_RGB2LAB)[0, 0].astype(np.float32)
    di = np.sqrt(((lab - ti) ** 2).sum(axis=-1))
    ds = np.sqrt(((lab - ts) ** 2).sum(axis=-1))
    return np.clip(0.5 + (ds - di) / (2.0 * EXCLUDE_SOFT), 0.0, 1.0)


def _color_weight(photo: Photo, target_rgb: Sequence[int], tolerance: float) -> np.ndarray:
    """0..1 weight of pixels close to the ink colour in Lab (a/b weighted more than lightness)."""
    t = cv2.cvtColor(np.uint8([[list(target_rgb)]]), cv2.COLOR_RGB2LAB)[0, 0].astype(np.float32)
    lab = photo.lab.astype(np.float32)
    da = lab[..., 1] - t[1]
    db = lab[..., 2] - t[2]
    dl = (lab[..., 0] - t[0]) * 0.35
    dist = np.sqrt(da * da + db * db + dl * dl)
    return np.clip(1.0 - (dist - tolerance) / (tolerance * 0.6), 0.0, 1.0)


def _components(mask: np.ndarray):
    return cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)


def auto_frame_for(mask: np.ndarray, work_dpi: float, lines: Optional[np.ndarray] = None,
                   find_lines: bool = True, cells: Optional[np.ndarray] = None) -> Tuple[int, int, int, int]:
    """Frame around the signature: the best cluster of ink after merging nearby strokes
    (strokes closer than ~4 mm belong together), plus
    * remark 67: long straight lines (table borders, ruling > 15 mm) do not join strokes into one cluster,
    * remark 59: a cluster of many small pieces (a handwritten name or date) loses to a signature,
    * remark 53: a long separate flourish next to it (an underline more than 4 mm away), and
    * remark 57: every stroke the frame crosses, whole (a separate stroke used to lose its tip)."""
    h, w = mask.shape
    if not mask.any():
        return 0, 0, w, h
    ppm = work_dpi / 25.4
    if lines is None and find_lines:
        lines = long_lines(mask, ppm)
    group_mask = mask & ~lines if lines is not None else mask
    if not group_mask.any():
        group_mask = mask
    merge = max(3, int(round(ppm * 4.0)))
    merged = cv2.dilate(group_mask.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (merge, merge)))
    n, labels, stats, _ = _components(merged)
    if n <= 1:
        return 0, 0, w, h
    if cells is not None:
        lab2, st2, n = merge_by_cells(labels, group_mask, cells, n)
        if st2 is not None:
            labels, stats = lab2, st2
    ink_per = np.bincount(labels[group_mask], minlength=n)
    ink_per[0] = 0
    best = _best_group(group_mask, labels, ink_per, n)
    ys, xs = np.nonzero((labels == best) & group_mask)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    # table borders (remark 67) are neither flourishes nor crossed strokes
    x0, y0, x1, y1 = _add_flourishes(group_mask, labels, stats, ink_per, best, (x0, y0, x1, y1), ppm)
    pad = max(4, int(round(ppm * 1.5)))
    px0, py0, px1, py1 = max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)
    cx0, cy0, cx1, cy1 = _add_crossed_strokes(group_mask, (px0, py0, px1, py1))
    # a side that grew to take a crossed stroke whole gets the usual padding again
    x0 = px0 if cx0 == px0 else max(0, cx0 - pad)
    y0 = py0 if cy0 == py0 else max(0, cy0 - pad)
    x1 = px1 if cx1 == px1 else min(w, cx1 + pad)
    y1 = py1 if cy1 == py1 else min(h, cy1 + pad)
    return x0, y0, x1 - x0, y1 - y0


CELL_MAJORITY = 0.6        # remark 73: a group belongs to a table cell holding ≥ 60 % of its ink


def table_cells(grid: Optional[np.ndarray], ppm: float) -> Optional[np.ndarray]:
    """Remark 73: closed cells of a table grid (label map, 0 = no cell).  Cells touching the photo
    edge or bigger than a quarter of it are not cells."""
    if grid is None or not grid.any():
        return None
    h, w = grid.shape
    wall = cv2.dilate(grid.astype(np.uint8), np.ones((5, 5), np.uint8))
    n, lab, st, _ = _components(wall == 0)
    keep = np.zeros(n, dtype=bool)
    for i in range(1, n):
        x, y, cw, ch, area = st[i]
        if x == 0 or y == 0 or x + cw >= w or y + ch >= h or area > 0.25 * w * h or area < 25 * ppm * ppm:
            continue
        keep[i] = True
    if not keep.any():
        return None
    return np.where(keep[lab], lab, 0).astype(np.int32)


def _same_column_only(per, gl, ink, inside, cells):
    """Remark 73, criterion 7 in a table: only groups in the column of the chosen signature count
    (a date or a name in another column is a field of the form, not a second signature)."""
    def cell_of(sel):
        c = cells[sel]; c = c[c > 0]
        return int(np.bincount(c).argmax()) if c.size and np.bincount(c).max() >= CELL_MAJORITY * int(sel.sum()) else 0
    me = cell_of(ink & inside)
    if not me:
        return per * 0
    xs = np.nonzero(cells == me)[1]; mx0, mx1 = xs.min(), xs.max()
    out = per.copy()
    for i in np.flatnonzero(per):
        c = cell_of(ink & (gl == i))
        if not c:
            out[i] = 0; continue
        cx = np.nonzero(cells == c)[1]; ov = min(mx1, cx.max()) - max(mx0, cx.min())
        if ov < 0.5 * min(mx1 - mx0, cx.max() - cx.min()):
            out[i] = 0
    return out


def merge_by_cells(labels, group_mask, cells, n):
    """Groups whose ink lies mostly in the same table cell are one group (a signature in its cell)."""
    parent = np.arange(n)
    owner = {}
    gl = labels[group_mask].astype(np.int64); cl = cells[group_mask].astype(np.int64)
    tot = np.bincount(gl, minlength=n)
    sel = cl > 0
    if sel.any():
        key = gl[sel] * (int(cl.max()) + 1) + cl[sel]
        uk, cnt = np.unique(key, return_counts=True)
        g_, c_ = uk // (int(cl.max()) + 1), uk % (int(cl.max()) + 1)
        best = {}
        for g, c, k in zip(g_.tolist(), c_.tolist(), cnt.tolist()):     # first max wins, like argmax
            if g not in best or k > best[g][1]:
                best[g] = (c, k)
        for i in range(1, n):
            if i not in best or tot[i] == 0:
                continue
            j, k = best[i]
            if k >= CELL_MAJORITY * tot[i]:
                if j in owner:
                    parent[i] = owner[j]
                else:
                    owner[j] = i
    if not owner:
        return labels, None, n
    lab2 = parent[labels]
    st = np.zeros((n, 5), np.int32)
    ys, xs = np.nonzero(lab2)
    if ys.size:
        l = lab2[ys, xs]; o = np.argsort(l, kind="stable"); l, ys, xs = l[o], ys[o], xs[o]
        u, start, cnt = np.unique(l, return_index=True, return_counts=True)
        x0 = np.minimum.reduceat(xs, start); x1 = np.maximum.reduceat(xs, start)
        y0 = np.minimum.reduceat(ys, start); y1 = np.maximum.reduceat(ys, start)
        st[u] = np.stack([x0, y0, x1 - x0 + 1, y1 - y0 + 1, cnt], 1)
    return lab2, st, n


LINE_MIN_MM = 15.0          # remark 67: straight lines longer than this are table borders / ruling
LINE_ANGLES = (-3.0, -1.5, 0.0, 1.5, 3.0)   # degrees around horizontal and vertical (a photo is never level)
TEXT_TOP3 = 0.8             # remark 59: a signature keeps ≥ 80 % of its ink in its 3 biggest pieces …
TEXT_MIN_FACTOR = 0.25      # … a cluster of many letters is scored down to (share / 0.8)², at least 0.25²


def long_lines(mask: np.ndarray, ppm: float) -> Optional[np.ndarray]:
    """Remark 67: pixels of table borders — straight lines longer than 15 mm (opening with thin line kernels
    at a few angles near horizontal / vertical) that meet a line of the other direction (a table is a grid;
    a long straight pen stroke or an underline alone is not removed).  Slightly grown so the line goes whole.
    None when there are none."""
    L = int(round(LINE_MIN_MM * ppm))
    if L < 15 or min(mask.shape) < 3:
        return None
    m8 = mask.astype(np.uint8)
    found = []
    for vertical in (False, True):
        acc = np.zeros(mask.shape, dtype=np.uint8)
        for ang in LINE_ANGLES:
            r = math.radians(ang)
            dx, dy = math.cos(r) * (L - 1) / 2.0, math.sin(r) * (L - 1) / 2.0
            if vertical:
                dx, dy = dy, dx
            kw, kh = int(abs(dx)) * 2 + 1, int(abs(dy)) * 2 + 1
            k = np.zeros((kh, kw), dtype=np.uint8)
            cx, cy = kw // 2, kh // 2
            cv2.line(k, (int(round(cx - dx)), int(round(cy - dy))), (int(round(cx + dx)), int(round(cy + dy))), 1, 1)
            acc |= cv2.morphologyEx(m8, cv2.MORPH_OPEN, k)
        found.append(acc)
    hor, ver = found
    if not hor.any() or not ver.any():
        return None
    touch = max(3, int(round(ppm * 1.0)))
    kern = np.ones((touch, touch), np.uint8)
    keep = np.zeros(mask.shape, dtype=bool)
    for a_, b_ in ((hor, ver), (ver, hor)):
        n, lab, _st, _ = _components(a_)
        hit = np.unique(lab[(cv2.dilate(b_, kern) > 0) & (a_ > 0)])
        hit = hit[hit != 0]
        if hit.size:
            keep |= np.isin(lab, hit)
    if not keep.any():
        return None
    grown = cv2.dilate(keep.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    return grown & mask


def _best_group(group_mask, labels, ink_per, n_groups):
    """Remark 59: the biggest cluster, but a cluster of many small pieces (handwritten text: a name, a date)
    counts less — its ink × (share of the 3 biggest pieces / 0.8)²."""
    cand = [i for i in range(1, n_groups) if ink_per[i] > 0]
    if not cand:
        return int(np.argmax(ink_per))
    top = max(ink_per[i] for i in cand)
    cand = [i for i in cand if ink_per[i] >= 0.25 * top]
    if len(cand) == 1:
        return cand[0]
    pn, pl, _ps, _ = _components(group_mask)
    best, best_score = cand[0], -1.0
    for i in cand:
        pieces = np.bincount(pl[(labels == i) & group_mask], minlength=1)[1:]
        tot = float(pieces.sum())
        share = float(np.sort(pieces)[::-1][:3].sum()) / tot if tot else 1.0
        f = max(TEXT_MIN_FACTOR, min(1.0, share / TEXT_TOP3)) ** 2
        score = float(ink_per[i]) * f
        if score > best_score:
            best, best_score = i, score
    return best


def _add_flourishes(mask, labels, stats, ink_per, best, box, ppm):
    """Remark 53: a long thin stroke group (long side ≥ 4 × short side) that runs along the signature —
    overlapping it by ≥ 25 % of its own length, no farther than the signature height (at least 12 mm),
    not longer than 2 × the signature nor 90 % of the page (ruling runs across the sheet), not a speck (≥ 2 % of its ink) and one
    stroke (at most 3 pieces, the biggest ≥ 80 % of the ink — a printed text line is many letters)."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    main_ink = float(ink_per[best])
    for i in range(1, len(ink_per)):
        if i == best or ink_per[i] < 0.02 * main_ink:
            continue
        gx, gy, gw, gh = (int(v) for v in stats[i, :4])
        horiz = gw >= gh
        long_side, short_side = (gw, gh) if horiz else (gh, gw)
        if long_side < 4 * max(1, short_side):
            continue
        if horiz:
            overlap = min(x1, gx + gw) - max(x0, gx)
            gap = max(0, gy - y1, y0 - (gy + gh))
            ref_len, ref_thick = bw, bh
        else:
            overlap = min(y1, gy + gh) - max(y0, gy)
            gap = max(0, gx - x1, x0 - (gx + gw))
            ref_len, ref_thick = bh, bw
        page_len = mask.shape[1] if horiz else mask.shape[0]
        if overlap < 0.25 * long_side or gap > max(ref_thick, 12 * ppm) or long_side > 2.0 * ref_len \
                or long_side > 0.9 * page_len:
            continue
        grp = (labels == i) & mask
        # a pen flourish is one stroke (a printed line of text is many letters)
        cn, _cl, cst, _ = _components(grp[gy:gy + gh, gx:gx + gw])
        if cn - 1 > 3 or cst[1:, cv2.CC_STAT_AREA].max() < 0.8 * ink_per[i]:
            continue
        ys, xs = np.nonzero(grp)
        x0, y0 = min(x0, int(xs.min())), min(y0, int(ys.min()))
        x1, y1 = max(x1, int(xs.max()) + 1), max(y1, int(ys.max()) + 1)
    return x0, y0, x1, y1


def _add_crossed_strokes(mask, box, rounds: int = 3):
    """Remark 57: strokes (connected components) cut by the frame are taken whole, as long as that does
    not grow a side by more than a quarter of the frame (a ruling line or the sheet edge stays cut)."""
    x0, y0, x1, y1 = box
    n, labels, stats, _ = _components(mask)
    for _ in range(rounds):
        fw, fh = x1 - x0, y1 - y0
        inside = np.unique(labels[y0:y1, x0:x1])
        nx0, ny0, nx1, ny1 = x0, y0, x1, y1
        for i in inside:
            if i == 0:
                continue
            cx, cy, cw, ch = (int(v) for v in stats[i, :4])
            if cx >= x0 and cy >= y0 and cx + cw <= x1 and cy + ch <= y1:
                continue
            ux0, uy0, ux1, uy1 = min(nx0, cx), min(ny0, cy), max(nx1, cx + cw), max(ny1, cy + ch)
            if (x0 - ux0) > 0.25 * fw or (ux1 - x1) > 0.25 * fw or (y0 - uy0) > 0.25 * fh or (uy1 - y1) > 0.25 * fh:
                continue
            nx0, ny0, nx1, ny1 = ux0, uy0, ux1, uy1
        if (nx0, ny0, nx1, ny1) == (x0, y0, x1, y1):
            break
        x0, y0, x1, y1 = nx0, ny0, nx1, ny1
    return x0, y0, x1, y1


def clamp_frame(frame: Tuple[int, int, int, int], w: int, h: int) -> Tuple[int, int, int, int]:
    x, y, fw, fh = (int(round(v)) for v in frame)
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))
    fw = max(1, min(fw, w - x))
    fh = max(1, min(fh, h - y))
    return x, y, fw, fh


@dataclass(frozen=True)
class EraserStroke:
    points: Tuple[Tuple[float, float], ...]   # working px
    radius: float                             # working px


def eraser_mask(shape: Tuple[int, int], strokes: Sequence[EraserStroke]) -> Optional[np.ndarray]:
    if not strokes:
        return None
    m = np.zeros(shape, dtype=np.uint8)
    for st in strokes:
        r = max(1, int(round(st.radius)))
        pts = [(int(round(x)), int(round(y))) for x, y in st.points]
        if len(pts) == 1:
            cv2.circle(m, pts[0], r, 255, -1, cv2.LINE_AA)
        else:
            cv2.polylines(m, [np.array(pts, dtype=np.int32)], False, 255, r * 2, cv2.LINE_AA)
    return m


def count_strokes(mask: np.ndarray, min_area: int = 4) -> int:
    if not mask.any():
        return 0
    n, _, stats, _ = _components(mask)
    return int(np.count_nonzero(stats[1:, cv2.CC_STAT_AREA] >= min_area))


def process(photo: Photo, params: ProcessParams, frame: Optional[Tuple[int, int, int, int]] = None,
            eraser: Sequence[EraserStroke] = ()) -> ProcessResult:
    """Full pipeline. ``frame`` = user frame (None = automatic). Remark 78: no AI step in v1.0."""
    h, w = photo.rgb.shape[:2]
    dark = _darkness(photo, params.flatten)
    alpha = _soft_alpha(dark, params.sensitivity)
    core = alpha > 0.5

    # ink colour
    tw = None
    det_rgb, separated, stamp_like = detect_ink_ex(photo, core)
    ink_state = "off"
    ink_rgb = det_rgb or (27, 42, 138)
    if params.ink_filter:
        if params.ink_mode == "manual":
            ink_state = "manual"
            if params.ink_rgb is not None:
                ink_rgb = tuple(params.ink_rgb)
                alpha = alpha * _color_weight(photo, ink_rgb, 26.0)
                if params.exclude_rgb is not None:
                    alpha = alpha * exclude_weight(photo, ink_rgb, params.exclude_rgb)
        else:
            from core import tinted as _T          # remark 73: tinted (yellow) paper
            tw = _T.tinted_ink(photo.rgb, photo.lab, core, photo.work_dpi / 25.4)
            if tw is not None:
                ink_state = "found"; det_rgb = ink_rgb = tw["ink_rgb"]; stamp_like = False
                alpha_raw = alpha.copy()
                alpha = alpha * tw["weight"]
            elif separated and det_rgb is not None:
                ink_state = "found"
                # remark 63: a dark ink found next to a stamp is matched as tightly as the eyedropper colour
                alpha = alpha * _color_weight(photo, det_rgb, 26.0 if stamp_like else 30.0)
                gate = _hue_gate(photo, det_rgb)
                if gate is not None:
                    alpha = alpha * gate
            else:
                ink_state = "same"

    mask = alpha >= 0.5
    # noise removal: drop specks smaller than a size driven by the slider (in mm²)
    if params.denoise > 0 and mask.any():
        px_per_mm = photo.work_dpi / 25.4
        min_area = (params.denoise / 100.0) * 0.6 * px_per_mm * px_per_mm
        n, labels, stats, _ = _components(mask)
        small = np.flatnonzero(stats[:, cv2.CC_STAT_AREA] < max(2.0, min_area))
        small = small[small != 0]
        if small.size:
            kill = np.isin(labels, small)
            alpha[kill] = 0.0
            mask &= ~kill

    rl = None
    if mask.any():      # remark 72: plain ruling (+73: inside a table every straight line goes)
        from core import ruling as _R
        rl = _R.ruling(mask, photo.work_dpi / 25.4, table=tw is not None)
        if rl is not None:
            fringe = (cv2.dilate(rl.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0) & ~mask
            alpha[rl | fringe] = 0.0
            mask &= ~rl
    if tw is not None and mask.any():     # remark 73: rejoin cut strokes, drop dashes, dust and ticks
        lp = tw["lines"]
        if rl is not None:
            lp = rl if lp is None else (lp | rl)
        mask, alpha = _T.clean(mask, alpha, alpha_raw, lp, photo.work_dpi / 25.4, removed=rl)
    pre_frame = mask.copy()          # ink of the whole photo after the filters (remark 48: criteria 3 and 7)
    lines = long_lines(mask, photo.work_dpi / 25.4) if mask.any() else None   # remark 67
    cells = None
    if ink_state == "found" and tw is not None:
        cells = table_cells(tw["lines"], photo.work_dpi / 25.4)   # = long_lines(core), already found
    auto = auto_frame_for(mask, photo.work_dpi, lines=lines, find_lines=False, cells=cells)
    fr = clamp_frame(frame if frame is not None else auto, w, h)
    fx, fy, fw, fh = fr
    inside = np.zeros((h, w), dtype=bool)
    inside[fy:fy + fh, fx:fx + fw] = True
    alpha = np.where(inside, alpha, 0.0)

    if params.thickness:
        k = 1 + 2 * abs(int(params.thickness))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        a8 = (alpha * 255).astype(np.uint8)
        a8 = cv2.dilate(a8, kernel) if params.thickness > 0 else cv2.erode(a8, kernel)
        alpha = a8.astype(np.float32) / 255.0

    er = eraser_mask((h, w), eraser)
    if er is not None:
        alpha = alpha * (1.0 - er.astype(np.float32) / 255.0)

    alpha8 = np.clip(alpha * 255.0 + 0.5, 0, 255).astype(np.uint8)
    mask = alpha8 >= 128
    strokes = count_strokes(mask)
    if mask.any():
        ys, xs = np.nonzero(mask)
        bw, bh = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
        size_mm = (round(bw / photo.work_dpi * 25.4, 1), round(bh / photo.work_dpi * 25.4, 1))
    else:
        size_mm = (0.0, 0.0)
    large = (fw * fh) > 0.5 * (w * h)
    doubts: Tuple[str, ...] = ()
    if strokes:
        try:
            doubts = assess_doubts(photo, dark, mask, fr, pre_frame, ink_rgb if ink_state in ("found", "same") and tw is None else None,
                                   auto_frame=frame is None, core=core,
                                   stamp_like=stamp_like and ink_state == "found", lines=lines, cells=cells)
        except Exception:   # a check must never break processing
            log.warning("doubt check failed for %s", photo.name, exc_info=True)
    return ProcessResult(alpha=alpha8, mask=mask, frame=fr, auto_frame=auto, stroke_count=strokes,
                         size_mm=size_mm, ink_rgb=tuple(int(v) for v in ink_rgb), ink_state=ink_state,
                         frame_is_large=large, source_dpi=(photo.dpi * photo.scale) if photo.dpi else None,
                         source_name=photo.stem, work_dpi=photo.work_dpi, doubts=doubts)


# --------------------------------------------------------------------------- remark 48: doubts
# «Требует внимания» also when the app is not sure (help.batch.attention_text); export is not blocked.
# Thresholds were checked on p3 / p4 (stamp, three signatures) and 59 clean Photoshop PNGs
# (/workspace/rewrite/r48_try/zip3_out).  Everything is measured in pixels and shares, not in mm.
DOUBT_CONTRAST = 45.0        # 1 pale: median stroke darkness − paper darkness (0…255)
DOUBT_FRAGMENTS = 40         # 2 busy background: more than 40 separate fragments …
DOUBT_FRAGMENT_MM2 = 1.0     # … counting only fragments larger than 1 mm² (remark 68: microtext, guilloche)
DOUBT_STAMP_L = 48.0         # 8 the auto ink is light (L* > 48) and blue — a stamp colour (remark 65)
DOUBT_CUT = 0.01             # 3 the frame cuts strokes: > 1 % of the ink of crossed strokes lies outside
DOUBT_FEW_SHARE = 0.001      # 4 too few strokes: < 0.1 % of the photo, or 1–2 fragments under 2 mm²
DOUBT_DENSITY = 0.25         # 5 strokes cover > 25 % of the frame
DOUBT_STAMP_SHARE = 0.25     # 6 stamp under the signature: red / orange lines ≥ 25 % of the signature ink
DOUBT_OTHER_GROUP = 0.25     # 7 several signatures: a stroke group outside the frame ≥ 0.25 of the chosen one
DOUBT_CODES = ("pale", "busy", "cut", "few", "dense", "stamp_ink", "several", "ink_stamp")


def assess_doubts(photo: Photo, dark: np.ndarray, mask: np.ndarray, frame: Tuple[int, int, int, int],
                  pre_frame: np.ndarray, auto_ink: Optional[Sequence[int]], auto_frame: bool = True,
                  core: Optional[np.ndarray] = None, stamp_like: bool = False,
                  lines: Optional[np.ndarray] = None, cells=None) -> Tuple[str, ...]:
    """Remark 48: the reasons the result looks doubtful.  ``mask`` = final signature mask, ``pre_frame`` =
    the same filters on the whole photo, ``auto_ink`` = the automatically found ink colour (None when the
    colour was picked by hand or the filter is off).  Criteria 3 and 7 are about the automatic frame and are
    skipped for a frame the user drew."""
    h, w = mask.shape
    fx, fy, fw, fh = frame
    ink = int(mask.sum())
    out: List[str] = []
    if ink == 0:
        return ()
    inside = np.zeros((h, w), dtype=bool)
    inside[fy:fy + fh, fx:fx + fw] = True
    paper = inside & ~mask
    # 1 pale
    if paper.any():
        contrast = float(np.median(dark[mask])) - float(np.median(dark[paper]))
        if contrast < DOUBT_CONTRAST:
            out.append("pale")
    # 2 busy background
    n, _l, st, _ = _components(mask)
    ppm = photo.work_dpi / 25.4
    if int(np.count_nonzero(st[1:, cv2.CC_STAT_AREA] > DOUBT_FRAGMENT_MM2 * ppm * ppm)) > DOUBT_FRAGMENTS:
        out.append("busy")
    # table borders (remark 67) are not strokes for criteria 3 and 7
    if lines is not None:
        pre_frame = pre_frame & ~lines
    # 3 the frame cuts strokes (the photo edge does not count: nothing is cut there)
    if auto_frame:
        pn, pl, _pst, _ = _components(pre_frame)
        crossing = np.unique(pl[pre_frame & inside])
        crossing = crossing[crossing != 0]
        if crossing.size:
            g = np.isin(pl, crossing) & pre_frame
            if float((g & ~inside).sum()) / max(1, int(g.sum())) > DOUBT_CUT:
                out.append("cut")
    # 4 too few strokes
    if ink < DOUBT_FEW_SHARE * w * h or (n - 1 <= 2 and ink < 2.0 * ppm * ppm):
        out.append("few")
    # 5 dense
    if ink / max(1, fw * fh) > DOUBT_DENSITY:
        out.append("dense")
    # 6 stamp: the ink found automatically has a stamp colour (red / orange), or the signature lies on a
    # stamp — dark red / orange lines inside the frame of at least DOUBT_STAMP_SHARE of the signature ink
    # (the colours were separated, but that is exactly where it can go wrong)
    if auto_ink is not None:
        hue, chroma = lab_hue_chroma(auto_ink)
        if chroma >= 10.0 and STAMP_HUE[0] <= hue <= STAMP_HUE[1]:
            out.append("stamp_ink")
    if "stamp_ink" not in out and core is not None:
        sub = photo.lab[fy:fy + fh, fx:fx + fw].astype(np.float32)
        a, b = sub[..., 1] - 128.0, sub[..., 2] - 128.0
        hue_px = np.degrees(np.arctan2(b, a))
        red = core[fy:fy + fh, fx:fx + fw] & (np.hypot(a, b) >= 14.0) & (hue_px >= STAMP_HUE[0]) & (hue_px <= STAMP_HUE[1])
        if float(red.sum()) >= DOUBT_STAMP_SHARE * ink:
            out.append("stamp_ink")
    # 7 several signatures
    if auto_frame:
        k = max(3, int(round(ppm * 4.0)))
        mg = cv2.dilate(pre_frame.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        gn, gl, _gst, _ = _components(mg)
        per = np.bincount(gl[pre_frame], minlength=gn)
        per[0] = 0
        touching = np.unique(gl[pre_frame & inside])
        per[touching] = 0
        if cells is not None and per.max(initial=0) > 0:
            per = _same_column_only(per, gl, pre_frame, inside, cells)
        if per.max(initial=0) >= DOUBT_OTHER_GROUP * ink:
            out.append("several")
    # 8 the ink looks like a stamp (remark 65): a darker group was taken instead of a stamp-coloured one
    # (remark 63), or the auto ink is light blue.  Criterion 6 stays red / orange only.
    if auto_ink is not None:
        hue, chroma = lab_hue_chroma(auto_ink)
        if stamp_like or (chroma >= 10.0 and BLUE_HUE[0] <= hue <= BLUE_HUE[1] and _lab_l(auto_ink) > DOUBT_STAMP_L):
            out.append("ink_stamp")
    return tuple(out)


def sample_color(photo: Photo, x: float, y: float, radius: int = 3) -> Tuple[int, int, int]:
    """Eyedropper: darkest-quartile median colour around (x, y) in working px."""
    h, w = photo.rgb.shape[:2]
    xi, yi = int(round(x)), int(round(y))
    x0, x1 = max(0, xi - radius), min(w, xi + radius + 1)
    y0, y1 = max(0, yi - radius), min(h, yi + radius + 1)
    patch = photo.rgb[y0:y1, x0:x1].reshape(-1, 3)
    if patch.size == 0:
        return (0, 0, 0)
    lum = patch.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    keep = patch[lum <= np.percentile(lum, 35)]
    return tuple(int(v) for v in np.median(keep, axis=0))


def result_rgba(result: ProcessResult, color: Optional[Sequence[int]] = None) -> Image.Image:
    """Full-size RGBA of the extracted signature (preview «После»)."""
    h, w = result.alpha.shape
    rgb = color or result.ink_rgb
    arr = np.empty((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb[0], rgb[1], rgb[2]
    arr[..., 3] = result.alpha
    return Image.fromarray(arr, "RGBA")
