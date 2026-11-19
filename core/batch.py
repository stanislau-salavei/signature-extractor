"""Batch processing model (stage 4). No Tk imports.

* ``Job`` — one photo: its editable state with an unlimited per-photo history, the last
  processing result and a small summary that survives unloading the photo (export source,
  stroke count, size, thumbnail).  A single-photo run (stage 3) uses the same class.
* ``Batch`` — the ordered list of jobs shown in the strip (14, 16), the current photo, files
  skipped as larger than 50 MB (46/47) and the «needs attention» state (38–42).
* ``SaveSession`` — «Сохранить в папку…» (16–18, 44): file names by the template, numbering of
  duplicate names inside the batch, the «Если файл уже есть» mode with «Применить ко всем», and
  the counters of the progress line (files, not photos).
"""
from __future__ import annotations

import itertools
import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from PIL import Image

from core import export as ex
from core import processing as P
from core.history import HistoryStack

log = logging.getLogger(__name__)

THUMB_PX = 128          # stored thumbnail (2× the 62 px tile, sharp at 125–200 %)
LOADED_MAX = 3          # photos kept in memory with their full result (current + recent)

# right-panel settings copied by «Применить ко всем» (all ProcessParams; crop frame and eraser stay per photo)
FILTER_FIELDS = tuple(P.ProcessParams.__dataclass_fields__)


@dataclass
class EditState:
    """Undoable state of one photo on screen 2."""
    params: P.ProcessParams
    frame: Optional[tuple]
    eraser: tuple = ()


class Job:
    """One photo and its result."""

    _ids = itertools.count(1)

    def __init__(self, photo: Optional[P.Photo] = None, params: Optional[P.ProcessParams] = None,
                 path: Optional[Path] = None, name: Optional[str] = None):
        self.id = next(Job._ids)
        self.photo = photo
        self.path = Path(path) if path is not None else None
        self.name = name or (photo.name if photo is not None else (self.path.name if self.path else ""))
        self.state = EditState(params or P.ProcessParams(), None, ())
        self.history = HistoryStack()
        self.history.set_initial(self.state)
        self.result: Optional[P.ProcessResult] = None
        self.saved = False
        self.version = 0            # bumped by every state change
        self.done_version = -1      # version of the last finished processing (-1 = never processed)
        self.source: Optional[ex.ExportSource] = None
        self.stroke_count = 0
        self.doubts: Tuple[str, ...] = ()   # remark 48: why the result looks doubtful (export stays open)
        self.size_mm: Tuple[float, float] = (0.0, 0.0)
        self.has_dpi = True
        self.thumb: Optional[Image.Image] = None

    # ------------------------------------------------------------------ state
    @property
    def stem(self) -> str:
        return Path(self.name).stem

    def push(self, state: EditState) -> None:
        self.state = state
        self.history.push(state)
        self.saved = False
        self.version += 1

    def set_state(self, state: EditState) -> None:
        """Undo / redo moved to ``state`` (already in the history)."""
        self.state = state
        self.saved = False
        self.version += 1

    @property
    def processed(self) -> bool:
        return self.done_version >= 0

    @property
    def busy(self) -> bool:
        """Never processed, or the state changed since the last finished processing."""
        return self.done_version != self.version

    @property
    def status(self) -> str:
        """pending | attention | doubt | ready.

        «attention» = signature not found — export is blocked (stage 4 decision 1).  Remark 48: «doubt» =
        found, but the app is not sure (pale, busy background, cut by the frame, too few strokes, too dense,
        stamp colour, several signatures) — the same «Требует внимания» mark and yellow bar, export open."""
        if not self.processed:
            return "pending"
        if self.stroke_count == 0:
            return "attention"
        return "doubt" if self.doubts else "ready"

    @property
    def needs_attention(self) -> bool:
        return self.status in ("attention", "doubt")

    @property
    def loaded(self) -> bool:
        return self.photo is not None and self.result is not None

    def apply_result(self, photo: P.Photo, result: P.ProcessResult, version: int,
                     thumb: Optional[Image.Image] = None) -> None:
        self.photo = photo
        self.result = result
        self.done_version = version
        self.stroke_count = int(result.stroke_count)
        self.doubts = tuple(getattr(result, "doubts", ()) or ())
        self.size_mm = tuple(result.size_mm)
        self.has_dpi = photo.dpi is not None
        self.source = None
        if not result.empty:
            try:
                self.source = ex.source_from_result(result)
            except Exception:   # an empty / degenerate mask must not break the batch
                log.warning("no export source for %s", self.name, exc_info=True)
        if thumb is not None:
            self.thumb = thumb
        elif self.thumb is None:
            self.thumb = make_thumbnail(photo, result)

    def unload(self) -> None:
        """Free the working photo and the full-size masks (the summary stays)."""
        self.photo = None
        self.result = None


def make_thumbnail(photo: P.Photo, result: Optional[P.ProcessResult], px: int = THUMB_PX) -> Image.Image:
    """Square crop of the photo around the signature (whole sheet centre when nothing was found)."""
    img = photo.image
    W, H = img.size
    if result is not None and not result.empty:
        fx, fy, fw, fh = result.frame
        side = max(fw, fh) * 1.08
    else:
        fx, fy, fw, fh = 0, 0, W, H
        side = min(W, H)
    side = max(8.0, min(side, float(max(W, H))))
    cx, cy = fx + fw / 2, fy + fh / 2
    x0 = min(max(0.0, cx - side / 2), max(0.0, W - side))
    y0 = min(max(0.0, cy - side / 2), max(0.0, H - side))
    box = (int(x0), int(y0), int(min(W, x0 + side)), int(min(H, y0 + side)))
    crop = img.crop(box).convert("RGB")
    cw, ch = crop.size
    s = px / max(1, min(cw, ch))           # cover the square tile
    tw, th = max(px, round(cw * s)), max(px, round(ch * s))
    crop = crop.resize((tw, th), Image.Resampling.LANCZOS)
    x, y = (tw - px) // 2, (th - px) // 2
    return crop.crop((x, y, x + px, y + px))


def path_key(p: Path) -> str:
    """Same file → same key (case-insensitive on Windows)."""
    try:
        return os.path.normcase(os.path.abspath(str(p)))
    except Exception:
        log.debug("path_key: Exception caught", exc_info=True)   # remark 81
        return str(p)


# --------------------------------------------------------------------------- batch
class Batch:
    def __init__(self, paths: Sequence[Path] = (), skipped_large: Sequence[Path] = (),
                 params: Optional[P.ProcessParams] = None):
        self.items: List[Job] = []
        self.index = 0
        self.skipped_large: List[Path] = []
        self.skipped_closed = False
        self.had_attention = False
        self.saved = False
        self.params = params or P.ProcessParams()
        self.add(paths)
        self.add_skipped(skipped_large)

    def __len__(self) -> int:
        return len(self.items)

    @property
    def current(self) -> Optional[Job]:
        return self.items[self.index] if self.items else None

    def add(self, paths: Iterable[Path]) -> List[Job]:
        """Append photos; the same file twice is skipped (decision 8)."""
        known = {path_key(j.path) for j in self.items if j.path is not None}
        added = []
        for p in paths:
            k = path_key(p)
            if k in known:
                continue
            known.add(k)
            job = Job(params=self.params, path=Path(p))
            self.items.append(job)
            added.append(job)
        if added:
            self.saved = False
        return added

    def add_skipped(self, paths: Iterable[Path]) -> None:
        known = {path_key(p) for p in self.skipped_large}
        new = False
        for p in paths:
            if path_key(p) not in known:
                self.skipped_large.append(Path(p))
                known.add(path_key(p))
                new = True
        if new:
            self.skipped_closed = False   # the bar comes back with the new count

    def select(self, i: int) -> bool:
        if not self.items:
            return False
        i = max(0, min(int(i), len(self.items) - 1))
        changed = i != self.index
        self.index = i
        return changed

    def index_of(self, job: Job) -> int:
        for i, j in enumerate(self.items):
            if j is job:
                return i
        return -1

    def remove(self, job: Job) -> Optional[Job]:
        """Remove ``job``; returns the photo to show next (None when the batch is empty)."""
        i = self.index_of(job)
        if i < 0:
            return self.current
        del self.items[i]
        if not self.items:
            self.index = 0
            return None
        if i < self.index:
            self.index -= 1
        self.index = min(self.index, len(self.items) - 1)
        return self.current

    # ------------------------------------------------------------------ attention
    def attention(self) -> List[Job]:
        """Photos with the «Требует внимания» mark: not found (blocking) and doubtful (remark 48)."""
        return [j for j in self.items if j.needs_attention]

    def blocking(self) -> List[Job]:
        """Photos that keep export closed: the signature was not found."""
        return [j for j in self.items if j.status == "attention"]

    def busy(self) -> List[Job]:
        return [j for j in self.items if j.busy]

    def note_attention(self) -> None:
        if self.attention():
            self.had_attention = True

    def bar_state(self) -> Optional[str]:
        """Bar above the strip: «warn» (38–41), «ok» (42, after problems were solved) or None (14)."""
        if self.attention():
            return "warn"
        if self.had_attention and not self.busy():
            return "ok"
        return None

    def ready_for_export(self) -> bool:
        return bool(self.items) and not self.busy() and not self.blocking()

    def next_attention(self) -> Optional[int]:
        """«Показать»: the next photo that needs attention after the current one, cyclically."""
        n = len(self.items)
        for k in range(1, n + 1):
            i = (self.index + k) % n
            if self.items[i].needs_attention:
                return i
        return None

    # ------------------------------------------------------------------ apply to all
    def apply_params_to_all(self, params: P.ProcessParams, source: Optional[Job] = None) -> List[Job]:
        """«Применить ко всем»: copy every right-panel setting (incl. the eyedropper colour) to the
        other photos; crop frame and eraser stay.  One history step per changed photo."""
        changed = []
        for j in self.items:
            if j is source:
                continue
            new = replace(j.state.params, **{f: getattr(params, f) for f in FILTER_FIELDS})
            if new == j.state.params:
                continue
            j.push(EditState(new, j.state.frame, j.state.eraser))
            changed.append(j)
        self.params = params
        if changed:
            self.saved = False
        return changed


def summary_text(i18n, photos: int, formats: int, files: int) -> str:
    """«50 фото × 2 формата = 100 файлов» — three plural forms in one row (batch.summary)."""
    import re
    key = "batch.summary"
    if i18n.lang == "ru":
        from core.i18n import ru_plural_category
        text = i18n.strings.get(key, {}).get("ru", key)
        note = i18n.notes.get(key, "")
        groups = re.findall(r"([А-Яа-яё]+)/([А-Яа-яё]+)/([А-Яа-яё]+)", note)
        cats = {"one": 0, "few": 1, "many": 2}
        # group 0 = «формат», group 1 = «файл»; replace the word that follows each placeholder
        for (ph, n), forms in zip((("{formats}", formats), ("{files}", files)), groups):
            m = re.search(re.escape(ph) + r" ([А-Яа-яё]+)", text)
            if m:
                text = text[:m.start(1)] + forms[cats[ru_plural_category(n)]] + text[m.end(1):]
        return text.format(photos=photos, formats=formats, files=files)
    text = i18n.strings.get(key, {}).get("en", key)
    for ph, n, word in (("{photos}", photos, "photos"), ("{formats}", formats, "formats"), ("{files}", files, "files")):
        if n == 1:
            text = text.replace(f"{ph} {word}", f"{ph} {word[:-1]}")
    return text.format(photos=photos, formats=formats, files=files)


# --------------------------------------------------------------------------- saving
@dataclass
class SavePlan:
    job: Job
    base: str                    # template result (before numbering)
    conflicts: List[Path]        # existing files that need «Если файл уже есть»
    forced_number: bool = False  # the same name was already used by another photo of this save


class SaveSession:
    """Names and counters of one «Сохранить в папку…» run."""

    def __init__(self, folder: Path, formats: Sequence[str], mode: str, template: str, total_photos: int):
        self.folder = Path(folder)
        self.formats = tuple(formats)
        self.mode = mode if mode in ("add_number", "replace", "ask") else "add_number"
        self.template = template
        self.total = total_photos * len(self.formats)
        self.done = 0           # files written or skipped
        self.saved = 0          # files written
        self.written: List[Path] = []
        self.decision: Optional[str] = None   # «Применить ко всем» answer: keep_both | replace | skip
        self.cancelled = False
        self._used: set = set()

    def base_for(self, job: Job) -> str:
        return ex.sanitize_filename(ex.expand_template(self.template, job.stem or "signature"))

    def _taken(self, base: str) -> bool:
        return base.lower() in self._used

    def numbered(self, base: str) -> str:
        """«name (2)», «name (3)» … free on disk and not used by another photo of this save."""
        if not self._taken(base) and not ex.existing_targets(self.folder, base, self.formats):
            return base
        n = 2
        while self._taken(f"{base} ({n})") or ex.existing_targets(self.folder, f"{base} ({n})", self.formats):
            n += 1
        return f"{base} ({n})"

    def plan(self, job: Job) -> SavePlan:
        base = self.base_for(job)
        if self._taken(base):   # decision 8: duplicate names inside the batch always get a number
            return SavePlan(job, base, [], forced_number=True)
        return SavePlan(job, base, ex.existing_targets(self.folder, base, self.formats))

    def needs_question(self, plan: SavePlan) -> bool:
        return bool(plan.conflicts) and self.mode == "ask" and self.decision is None

    def resolve(self, plan: SavePlan, choice: Optional[str] = None, apply_all: bool = False) -> List[Tuple[str, str]]:
        """Return [(format, base), ...] to write.  ``choice`` answers dialog 44:
        keep_both | replace | skip («Отмена» skips only the conflicting files of this photo)."""
        if apply_all and choice:
            self.decision = choice
        if plan.forced_number:
            base = self.numbered(plan.base)
            fmts = list(self.formats)
        elif not plan.conflicts:
            base, fmts = plan.base, list(self.formats)
        else:
            how = choice or self.decision or {"add_number": "keep_both", "replace": "replace"}.get(self.mode, "keep_both")
            if how == "replace":
                base, fmts = plan.base, list(self.formats)
            elif how == "skip":
                clash = {p.suffix.lower().lstrip(".") for p in plan.conflicts}
                base = plan.base
                fmts = [f for f in self.formats if f.lower() not in clash]
                self.done += len(self.formats) - len(fmts)
            else:
                base, fmts = self.numbered(plan.base), list(self.formats)
        self._used.add(base.lower())
        return [(f, base) for f in fmts]

    def write(self, fmt: str, base: str, data: bytes) -> Path:
        path = ex.write_outputs(self.folder, base, {fmt: data})[0]
        self.done += 1
        self.saved += 1
        self.written.append(path)
        return path

    @property
    def finished(self) -> bool:
        """Test hook (remark 108): every file of the session is written."""
        return self.done >= self.total


def process_job(job: Job, state: EditState, photo: Optional[P.Photo]):
    """Worker-thread body: load the photo when needed and run the pipeline for ``state``.
    Returns (photo, result, thumbnail or None)."""
    if photo is None:
        if job.path is None:
            raise P.ImageLoadError(job.name)
        img, dpi = P.load_image(job.path)
        photo = P.prepare_photo(img, dpi, job.path.name)
    res = P.process(photo, state.params, state.frame, state.eraser)
    thumb = make_thumbnail(photo, res)
    return photo, res, thumb
