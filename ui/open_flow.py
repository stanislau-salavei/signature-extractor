"""Opening photos in the main window: dialogs, clipboard, drop, the background load and processing of
one photo or of every photo of a batch (remark 112, audit B3; mixed into ``ui.app.App``)."""
from __future__ import annotations

import logging
from pathlib import Path
from tkinter import filedialog
from typing import List

from core import batch as B
from core import processing as P
from core.batch import Batch, Job
from ui.widgets.overlay import Popup

log = logging.getLogger(__name__)


class OpenFlowMixin:
    def open_file_dialog(self):
        def go():
            exts = " ".join("*" + e for e in sorted(P.SUPPORTED_EXT))
            # stage 4: several files chosen → a batch; one file → the single-photo flow
            names = filedialog.askopenfilenames(parent=self.root, title=self.t("menu.open_file"),
                                                filetypes=[(self.t("menu.open_file"), exts)])
            if isinstance(names, str):
                names = self.root.tk.splitlist(names)
            if names:
                self.open_paths([Path(n) for n in names])
        self.confirm_restart(go)

    def open_folder_dialog(self):
        def go():
            path = filedialog.askdirectory(parent=self.root, title=self.t("menu.add_folder"))
            if path:
                self.open_paths([Path(path)])
        self.confirm_restart(go)

    def paste_clipboard(self):
        if self.overlay_open():
            return
        try:
            from PIL import ImageGrab
            data = ImageGrab.grabclipboard()
        except Exception:
            log.debug("clipboard read failed", exc_info=True)
            data = None
        if isinstance(data, list):
            paths = [Path(p) for p in data if isinstance(p, str)]
            if paths:
                self.confirm_restart(lambda: self.open_paths(paths))
            return
        if data is None or not hasattr(data, "size"):
            # no image on the clipboard: clear error (errors.clipboard.*)
            self.show_error_dialog(self.t("errors.clipboard.title"), self.t("errors.clipboard.body"))
            return
        img = data

        def go():
            self.start_processing(lambda: (P._normalize(img), P.read_dpi(img), "clipboard.png"))
        self.confirm_restart(go)

    def open_paths(self, paths: List[Path]):
        """Open dropped / chosen paths.  A folder or several files make a batch (stage 4), even if only
        one photo is found; one file is the single-photo flow of stage 3."""
        if self.settings_open:
            self.close_settings()
        if self.help_open:
            self.close_help()
        paths = [Path(p) for p in paths]
        is_batch = len(paths) > 1 or any(p.is_dir() for p in paths)
        scan = P.scan_inputs(paths)
        self.import_page.clear_error()
        if not scan.photos:
            if scan.too_large:
                f = scan.too_large[0]
                self.go_home(keep_error=True)
                self.import_page.show_error(self.t("import.too_large", file=f.name,
                                                   size=self.fmt_num(P.file_size_mb(f), 0)))
                return
            if scan.skipped_other:
                f = scan.skipped_other[0]
                self.show_error_dialog(self.t("errors.open.title"), self.t("errors.open.body", file=f.name))
            return
        if is_batch:
            batch = Batch(scan.photos, scan.too_large, params=P.ProcessParams())
            go = lambda: self.start_batch(batch)   # noqa: E731
        else:
            photo_path = scan.photos[0]

            def load():
                img, dpi = P.load_image(photo_path)
                return img, dpi, photo_path.name
            go = lambda: self.start_processing(load)   # noqa: E731
        if scan.skipped_other:
            # 04: shown over screen 1 before processing; «Понятно» continues with the photos
            from ui.dialogs.content import ContentDialog
            self.go_home()
            ContentDialog(self, self.t("import.skipped_title"),
                          self.tn("import.skipped_body", len(scan.skipped_other), photos=len(scan.photos)),
                          [(self.t("common.got_it"), "primary", go)], width=440, esc_index=0)
            return
        go()

    def start_processing(self, loader):
        self.reset_batch()
        params = P.ProcessParams()
        self._pending_params = params
        self.job = None
        self.show_page("busy")

        def work():
            img, dpi, name = loader()
            photo = P.prepare_photo(img, dpi, name)
            res = P.process(photo, params)
            return photo, res

        self.worker.submit("process", work, self._loaded, self._load_failed)

    def _loaded(self, value):
        photo, res = value
        self.job = Job(photo, self._pending_params)
        self.job.apply_result(photo, res, self.job.version)
        self.show_page("process")

    def _load_failed(self, exc):
        self.go_home()
        name = exc.args[0] if isinstance(exc, P.ImageLoadError) and exc.args else "?"
        self.show_error_dialog(self.t("errors.open.title"), self.t("errors.open.body", file=name), width=460)

    def process_job(self, job: Job, background: bool = False, on_first: bool = False):
        """Run the pipeline for ``job``'s current state on the worker (latest request per photo wins)."""
        state, version, photo = job.state, job.version, job.photo

        def work():
            return B.process_job(job, state, photo)

        def done(res):
            self._job_done(job, version, res, on_first)

        def fail(exc):
            self._job_failed(job, exc, on_first)
        self.worker.submit(f"job:{job.id}", work, done, fail, priority=10 if background else 0)

    def _job_done(self, job: Job, version: int, res, on_first=False):
        photo, result, thumb = res
        b = self.batch
        if b is not None and b.index_of(job) < 0 and job is not self.job:
            return   # removed meanwhile
        if job.version != version:
            if job.photo is None and (job is self.job):
                job.photo = photo      # keep the loaded photo for the newer request
            return
        job.apply_result(photo, result, version, thumb)
        if b is None:
            if job is self.job and self.process_page:
                self.process_page.on_result()
            self.update_header()
            return
        if on_first:
            self.job = job
            self._touch(job)
            self.show_page("process")
            for other in b.items[1:]:
                if other.busy:
                    self.process_job(other, background=True)
        elif job is not self.job and not self.state.is_recent(job):
            job.unload()               # background result: keep only the summary
        b.note_attention()
        if job is self.job:
            self.on_batch_changed(result_for_current=True)
        else:
            self.on_batch_changed(coalesce=True)

    def _job_failed(self, job: Job, exc, on_first=False):
        b = self.batch
        if b is None:
            log.error("processing failed: %s", exc)
            return
        if not isinstance(exc, (P.ImageLoadError, OSError, ValueError)):
            log.error("processing failed for %s: %s", job.name, exc)
        # a damaged file inside a batch leaves the batch; dialog 29 names the first one
        was_current = job is self.job
        nxt = b.remove(job)
        if not self._load_error_shown and Popup.current is None:
            self._load_error_shown = True
            self.root.after(1, lambda: self.show_error_dialog(self.t("errors.open.title"),
                                                              self.t("errors.open.body", file=job.name), width=460))
        if on_first:
            self._start_first()
            return
        if nxt is None:
            self.go_home()
            return
        if was_current:
            self._switch_to(b.current)
        else:
            self.on_batch_changed()
