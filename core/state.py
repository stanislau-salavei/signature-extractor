"""Remark 82: the state controller — which screen is open and what is loaded, without any UI.

The window (``ui/app.py``) keeps the widgets, dialogs and the worker and asks this object about the state.
Its old attributes (``app.job``, ``app.batch``, ``app.page`` …) are properties that read and write here, so
nothing changes for the pages and dialogs."""
from __future__ import annotations

from typing import Any, List

PAGES = ("import", "busy", "process", "export")


class AppState:
    def __init__(self, loaded_max: int = 3):
        self.page = "import"            # import | busy | process | export
        self.settings_open = False      # «Параметры» page over the steps
        self.help_open = False          # remark 30: «Справка» page from the ⋯ menu
        self.job = None                 # current photo (core.batch.Job)
        self.batch = None               # stage 4: folder / several files (core.batch.Batch)
        self.saving = False             # a batch is being written (17): navigation is locked
        self.recent: List[Any] = []     # batch photos kept loaded (current + recent)
        self.loaded_max = loaded_max
        self.load_error_shown = False   # dialog 29 is shown once per batch
        self.pending_params = None      # params of the single photo being loaded
        self.saved_token = None         # remark 39: work snapshot of the last successful save

    # ------------------------------------------------------------------ screens
    def set_page(self, name: str) -> None:
        if name not in PAGES:
            raise ValueError(name)
        self.page = name

    def overlay_open(self) -> bool:
        """A full-window page (Параметры or Справка) covers the steps."""
        return self.settings_open or self.help_open

    def has_photos(self) -> bool:
        """Remark 71: something is loaded (or loading) — «Начать заново» is grey on screen 1 without photos."""
        if self.page in ("busy", "process", "export"):
            return True
        return self.job is not None or (self.batch is not None and bool(self.batch.items))

    def can_export(self) -> bool:
        if self.batch is not None:
            return self.batch.ready_for_export()
        return self.job is not None and self.job.result is not None and not self.job.result.empty

    # ------------------------------------------------------------------ remark 39: unsaved work
    def jobs(self) -> list:
        if self.batch is not None:
            return list(self.batch.items)
        return [self.job] if self.job is not None else []

    def work_token(self, export_key=None):
        return tuple((j.id, j.version) for j in self.jobs()), export_key

    def mark_saved(self, export_key=None) -> None:
        self.saved_token = self.work_token(export_key)

    def mark_save_failed(self) -> None:
        self.saved_token = None

    def has_unsaved(self, export_key=None) -> bool:
        if self.page not in ("process", "export"):
            return False
        if self.batch is not None:
            if not self.batch.items:
                return False
        elif self.job is None or self.job.result is None:
            return False
        return self.saved_token != self.work_token(export_key)

    # ------------------------------------------------------------------ batch (stage 4)
    def clear_batch(self) -> list:
        """Forget the batch; returns its photos (the caller cancels their worker tasks)."""
        items = list(self.batch.items) if self.batch is not None else []
        self.batch = None
        self.recent = []
        self.load_error_shown = False
        return items

    def touch(self, job) -> list:
        """``job`` is the most recent photo; returns the photos that fall out of the loaded set (to unload)."""
        self.recent = [j for j in self.recent if j is not job] + [job]
        out = []
        while len(self.recent) > self.loaded_max:
            old = self.recent.pop(0)
            if old is not self.job:
                out.append(old)
        return out

    def forget(self, job) -> None:
        self.recent = [j for j in self.recent if j is not job]

    def is_recent(self, job) -> bool:
        return any(j is job for j in self.recent)
