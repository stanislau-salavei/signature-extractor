"""Screen 3 saving: the bottom bar and the save flow of one photo and of a batch (remark 112)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from tkinter import filedialog

from core import batch as B
from core import export as ex
from core.export_preview import geom_key
from ui.theme import ACTION_BAR_H, HEADER_H, S, Theme, elide
from ui.widgets.base import Box, Tooltip
from ui.widgets.controls import Button

log = logging.getLogger(__name__)


class ExportBar(Box):
    def __init__(self, master, page):
        super().__init__(master, bg="abar")
        self.page = page
        app = page.app
        # remark 31: secondary (filled) like «Назад» on screen 2, not ghost
        self.back = Button(self, "", kind="secondary", icon="arrow_left", bg="abar", command=app.back_to_process)
        self.save = Button(self, "", kind="primary", icon="save", icon_size=17, bg="abar", command=page.on_save_click)
        self.done = Button(self, "", kind="secondary", bg="abar", command=page.on_done)
        self.open = Button(self, "", kind="primary", icon="folder", bg="abar", command=page.open_saved_folder)
        self.cancel = Button(self, "", kind="secondary", bg="abar", command=page.cancel_batch_save)

    def layout(self, x, y, w):
        self.geom(x, y, w, ACTION_BAR_H)
        p = self.page
        t = p.app.t
        batch = p.app.batch is not None
        if batch and p._saving:
            # 17: «Сохранено N из M файлов» + progress bar, «Отмена»
            for wd in (self.back, self.save, self.done, self.open):
                wd.hide()
            self.cancel.set_text(t("common.cancel"))
            cw = self.cancel.natural_width()
            self.cancel.geom(w - 24 - cw, 16.5, cw, 32)
            self._prog_w = w - 24 - cw - 10 - 24 - 24
            self.redraw()
            return
        self.cancel.hide()
        if p.saved:
            self.back.hide()
            self.save.hide()
            self.done.set_text(t("common.done"))
            self.open.set_text(t("common.open_folder"))
            ow, dw = self.open.natural_width(), self.done.natural_width()
            self.open.geom(w - 24 - ow, 16.5, ow, 32)
            self.done.geom(w - 24 - ow - 10 - dw, 16.5, dw, 32)
        else:
            self.done.hide()
            self.open.hide()
            n = len(p.selected_formats())
            if batch:
                self.save.set_text(t("batch.save_to_folder"))
                self.save.icon_name, self.save.icon_px = "folder", 16
            else:
                self.save.set_text(p.app.tn("export.save_count", n))
                self.save.icon_name, self.save.icon_px = "save", 17
            self.save.set_disabled(n == 0 or p._saving)
            self.back.set_text(t("common.back"))
            sw, bw = self.save.natural_width(), self.back.natural_width()
            self.save.geom(w - 24 - sw, 16.5, sw, 32)
            self.back.geom(w - 24 - sw - 10 - bw, 16.5, bw, 32)
        self.redraw()

    def draw(self):
        self.create_rectangle(0, 0, S(self.lw), S(1), fill=Theme.c("abar_line"), width=0)
        p = self.page
        if p._saving and p.app.batch is not None and p._sess is not None:
            sess = p._sess
            room = getattr(self, "_prog_w", self.lw - 200)
            self.text(24, 19.5 + 8, elide(p.app.tn("batch.saving", sess.total, done=sess.done, total=sess.total),
                                         room, 13, "semibold"), 13, "semibold")
            self.rrect(24, 41.5, room, 4, 2, "progress_track")
            frac = sess.done / sess.total if sess.total else 0.0
            if frac > 0:
                self.rrect(24, 41.5, max(4.0, room * min(1.0, frac)), 4, 2, "accent")
            return
        if p.saved:
            n, folder = p.saved
            room = (self.done.lx - 24 - 10) if self.done.visible else self.lw - 48
            self.text(24, 32, elide(p.app.tn("export.saved_status", n, folder=folder.name), room, 13, "semibold"),
                      13, "semibold")


class SaveFlowMixin:
    """«Сохранить», «Готово», «Открыть папку»; batch saving with the «Файл уже существует» questions.
    Mixed into :class:`ui.pages.export_page.ExportPage`."""

    def on_done(self):
        self.remember()
        self.app.done_after_save()

    def open_saved_folder(self):
        if self.saved:
            self.app.open_folder(self.saved[1])

    # ------------------------------------------------------------------ save
    def on_save_click(self):
        fmts = self.selected_formats()
        if self.app.batch is not None:
            if fmts and not self._saving:
                self.batch_save_click(fmts)
            return
        if not fmts or not self.source or self._saving:
            return
        t = self.app.t
        folder = self.settings.save_folder(t("export.default_folder"))
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            log.warning("cannot create save folder %s", folder)
        template = self.settings.name_template(t("settings.name_template.value"))
        from datetime import datetime
        stem = self.source.name or datetime.now().strftime("%Y-%m-%d_%H%M%S")
        base = ex.sanitize_filename(ex.expand_template(template, stem))
        kwargs = dict(parent=self.app.root, initialdir=str(folder), initialfile=f"{base}.{fmts[0].lower()}",
                      defaultextension=f".{fmts[0].lower()}", filetypes=[(f, f"*.{f.lower()}") for f in fmts])
        if sys.platform == "win32":
            kwargs["confirmoverwrite"] = False  # «Если файл уже есть» decides, not the dialog
        path = filedialog.asksaveasfilename(**kwargs)
        if not path:
            return  # cancelled: stay on screen 3 without «Сохранено…»
        path = Path(path)
        self.save_to(path.parent, ex.sanitize_filename(ex.strip_known_ext(path.name)), fmts)

    def save_to(self, folder: Path, base: str, fmts):
        mode = self.settings.get("if_exists", "ask")
        base2, conflicts = ex.resolve_base(folder, base, fmts, mode)
        if conflicts:
            self.ask_file_exists(folder, base, conflicts[0].name, fmts)
            return
        self.start_write(folder, base2, fmts)

    def ask_file_exists(self, folder, base, filename, fmts):
        from ui.dialogs.content import ContentDialog
        t = self.app.t
        body = t("file_exists.body", folder="\x00F", file="\x00N").replace("\x00F", folder.name)
        a, _, b = body.partition("\x00N")
        runs = [(a, "normal"), (filename, "semibold")] + ([(b, "normal")] if b else [])
        ContentDialog(self.app, t("file_exists.title"), runs, [
            (t("file_exists.keep_both"), "primary",
             lambda: self.start_write(folder, ex.resolve_base(folder, base, fmts, "add_number")[0], fmts)),
            (t("common.replace"), "secondary", lambda: self.start_write(folder, base, fmts)),
            (t("common.cancel"), "secondary", None)], width=560)

    def start_write(self, folder, base, fmts):
        job = ex.ExportJob(self.source, self.size_choice(), self.margin_mm, self.current_rgb(), self.png_dpi, fmts,
                           self.dxf_line_mm, self.svg_mode, self.svg_line_mm)
        geom = self.geometry_safe()
        m = self.model
        same = bool(m.trace and m.trace[0] == geom_key(self.source, geom))
        cached = m.outline if same else None
        cached_cl = m.centerline if same else None
        png = m.png_bytes_for(self.source, geom, tuple(job.rgb), ex.effective_png_dpi(job.source, job.size, job.png_dpi)) \
            if geom is not None and "PNG" in fmts else None                                       # audit B10
        self._saving = True
        self.bar.layout(0, self.lh - ACTION_BAR_H, self.lw)

        def work():
            return ex.write_outputs(folder, base, ex.build_outputs(job, cached, cached_cl, png=png))

        def ok(res):
            self._saving = False
            self.saved = (len(res), Path(folder))
            if self.app.job:
                self.app.job.saved = True
            self.app.mark_saved()
            self.remember()
            self.bar.layout(0, self.lh - ACTION_BAR_H, self.lw)

        def fail(exc):
            self._saving = False
            self.app.mark_save_failed()
            log.error("save failed: %s", exc)
            self.bar.layout(0, self.lh - ACTION_BAR_H, self.lw)
            self.app.show_error_dialog(self.app.t("errors.save.title"), self.app.t("errors.save.body"),
                                       retry=lambda: self.start_write(folder, base, fmts))
        self.app.worker.submit("save", work, ok, fail)

    # ------------------------------------------------------------------ batch save (16–18, 44)
    def batch_save_click(self, fmts):
        t = self.app.t
        folder = self.settings.save_folder(t("export.default_folder"))
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            log.warning("cannot create save folder %s", folder)
        d = filedialog.askdirectory(parent=self.app.root, initialdir=str(folder), mustexist=False,
                                    title=t("batch.save_to_folder"))
        if d:
            self.start_batch_save(Path(d), fmts)

    def start_batch_save(self, folder: Path, fmts):
        b = self.app.batch
        if b is None or not b.items:
            return
        t = self.app.t
        template = self.settings.name_template(t("settings.name_template.value"))
        mode = self.settings.get("if_exists", "ask")
        self._sess = B.SaveSession(folder, fmts, mode, template, len(b.items))
        self._queue = list(b.items)
        self._save_cfg = (self.size_choice(), self.margin_mm, tuple(self.current_rgb()), self.png_dpi,
                          self.dxf_line_mm, self.svg_mode, self.svg_line_mm)
        self.saved = None
        self._saving = True
        self.app.saving = True
        Tooltip.cancel(None)
        self.bar.layout(0, self.lh - ACTION_BAR_H, self.lw)
        self.app.root.update_idletasks()
        self.dim.show(0, HEADER_H, self.lw, self.lh - ACTION_BAR_H)
        self.remember()
        self._save_next()

    def _save_next(self):
        sess = self._sess
        if sess is None or sess.cancelled:
            return
        if not self._queue:
            self._finish_batch_save()
            return
        plan = sess.plan(self._queue[0])
        if sess.needs_question(plan):
            self._ask_batch_exists(plan)
            return
        self._render_job(plan, sess.resolve(plan))

    def _ask_batch_exists(self, plan):
        """44: «Файл уже существует» with «Применить ко всем»."""
        from ui.dialogs.content import ContentDialog
        t = self.app.t
        sess = self._sess
        filename = plan.conflicts[0].name
        body = t("file_exists.body", folder="\x00F", file="\x00N").replace("\x00F", sess.folder.name)
        a, _, rest = body.partition("\x00N")
        runs = [(a, "normal"), (filename, "semibold")] + ([(rest, "normal")] if rest else [])

        def answer(choice):
            return lambda apply_all: self._render_job(plan, sess.resolve(plan, choice, apply_all))
        ContentDialog(self.app, t("file_exists.title"), runs, [
            (t("file_exists.keep_both"), "primary", answer("keep_both")),
            (t("common.replace"), "secondary", answer("replace")),
            (t("common.cancel"), "secondary", answer("skip"))], width=560, check=t("batch.apply_all"), esc_index=2)

    def _render_job(self, plan, pairs):
        sess = self._sess
        if sess is None or sess.cancelled:
            return
        if self._queue and self._queue[0] is plan.job:
            self._queue.pop(0)
        job = plan.job
        if not pairs or job.source is None:
            if job.source is None:        # nothing to export (should not happen: export needs all ready)
                sess.done += len(pairs)
            self.bar.redraw()
            self.after(1, self._save_next)
            return
        size, margin, rgb, dpi, dxf_line, svg_mode, svg_line = self._save_cfg
        ejob = ex.ExportJob(job.source, size, margin, rgb, dpi, tuple(f for f, _ in pairs), dxf_line, svg_mode, svg_line)

        def work():
            return ex.build_outputs(ejob)

        def ok(outputs):
            self._write_pairs(job, pairs, outputs)

        def fail(exc):
            log.error("batch render failed for %s: %s", job.name, exc)
            self._save_error(lambda: self._render_job(plan, pairs))
        self.app.worker.submit("batch_save", work, ok, fail)

    def _write_pairs(self, job, pairs, outputs):
        sess = self._sess
        if sess is None or sess.cancelled:
            return
        for k, (fmt, base) in enumerate(pairs):
            try:
                sess.write(fmt, base, outputs[fmt])
            except OSError as exc:
                log.error("cannot write %s: %s", base, exc)
                rest = pairs[k:]
                self.bar.redraw()
                self._save_error(lambda rest=rest: self._write_pairs(job, rest, outputs))   # retry from the failed file
                return
        self.bar.redraw()
        self.after(1, self._save_next)

    def _save_error(self, retry):
        t = self.app.t
        self.app.show_error_dialog(t("errors.save.title"), t("errors.save.body"), retry=retry,
                                   on_cancel=self.cancel_batch_save)

    def cancel_batch_save(self):
        """«Отмена» (17) or «Отмена» in 31: stop; «Готово» state with the files really written."""
        sess = self._sess
        if sess is None or not self._saving:
            return
        sess.cancelled = True
        self._finish_batch_save()

    def _finish_batch_save(self):
        sess = self._sess
        self._saving = False
        self.app.saving = False
        self.dim.hide()
        self._queue = []
        b = self.app.batch
        if sess is not None and sess.saved:
            self.saved = (sess.saved, sess.folder)
            if b is not None and not sess.cancelled:
                b.saved = True
        else:
            self.saved = None
        if sess is not None and sess.saved and not sess.cancelled and not getattr(sess, "failed", 0):
            self.app.mark_saved()
        else:
            self.app.mark_save_failed()
        self.layout_all()
