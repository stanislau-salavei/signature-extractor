"""Update checks and installs through GitHub Releases (stage 5): the UI side of core/updater.

* ``startup()`` — the silent check: only with «Проверять обновления при запуске» on and at most once a day;
  no network → silence.  A new version shows dialog 32 only on screen 1 (waits there until the user is on it).
* ``check(manual=True)`` — «Проверить сейчас»: dialog 32, or a grey line under «Проверять обновления при
  запуске» («Установлена последняя версия (1.0)» / «Не удалось проверить обновления, нет подключения»).
* «Скачать» → temp folder with progress and «Отмена» → SHA-256 from the .sha256 asset (or the notes) →
  installer started, app closed; a wrong sum → «Файл обновления повреждён, попробуйте ещё раз» and the file is
  deleted; a broken connection → «Не удалось скачать обновление».

Network work runs on its own threads (not the processing worker); results come back through a queue polled
on the Tk thread.  ``fetcher`` / ``opener`` / ``launcher`` / ``quit`` are replaceable for tests."""
from __future__ import annotations

import logging
import os
import queue
import threading
from typing import Callable, Optional

from core import updater as U
from ui import platform_win
from ui.dialogs.content import ContentDialog
from ui.dialogs.update import UpdateDialog
from ui.widgets.overlay import Popup

log = logging.getLogger(__name__)


class UpdateController:
    POLL_MS = 80

    def __init__(self, app):
        self.app = app
        self.fetcher: Optional[Callable[[str], bytes]] = None
        self.opener = None
        self.api_url = U.api_url()          # stage 6: SE_UPDATE_API points a test build at a test repository
        log.info("update check address: %s%s", self.api_url,                        # remark 93
                 f" ({U.API_ENV})" if self.api_url != U.API_LATEST else "")
        self.dest_dir = None
        self.launcher: Callable = platform_win.launch_installer
        self.quit: Callable[[], None] = app.quit
        self._q: "queue.Queue" = queue.Queue()
        self._polling = False
        self.checking = False
        self.pending = None           # Release waiting for screen 1 (silent check)
        self.dialog = None
        self._cancel: Optional[threading.Event] = None

    # ------------------------------------------------------------------ threads → Tk
    def _run(self, fn, done):
        def work():
            try:
                res = fn()
                self._q.put((done, res, None))
            except BaseException as exc:   # noqa: BLE001
                log.debug("UpdateController._run.work: BaseException caught", exc_info=True)   # remark 81
                self._q.put((done, None, exc))
        threading.Thread(target=work, name="updater", daemon=True).start()
        if not self._polling:
            self._polling = True
            self.app.root.after(self.POLL_MS, self._poll)

    def _poll(self):
        try:
            while True:
                cb, res, exc = self._q.get_nowait()
                try:
                    cb(res, exc)
                except Exception:
                    log.exception("update callback failed")
        except queue.Empty:
            pass
        try:
            self.app.root.after(self.POLL_MS, self._poll)
        except Exception:
            log.debug("UpdateController._poll: Exception caught", exc_info=True)   # remark 81
            self._polling = False

    # ------------------------------------------------------------------ checks
    def startup(self):
        s = self.app.settings
        if os.environ.get("SE_NO_UPDATE_CHECK") == "1":
            return
        if not s.get("check_updates", True) or not U.due(s.get("last_update_check")):
            return
        self.check(manual=False)

    def check(self, manual: bool):
        if self.checking:
            return
        self.checking = True
        cur = self.app.VERSION_STR
        self._run(lambda: U.check_latest(cur, self.api_url, self.fetcher),
                  lambda res, exc: self._checked(res if exc is None else U.CheckResult("offline"), manual))

    def _checked(self, res: U.CheckResult, manual: bool):
        self.checking = False
        app = self.app
        if res.status != "offline":
            app.settings.set("last_update_check", U.now_iso())
        if manual:
            sp = app.settings_page
            note = ""
            if res.status == "latest":
                note = app.t("settings.update.latest", version=app.VERSION_STR)
            elif res.status == "offline":
                note = app.t("settings.update.offline")
            if sp is not None:
                sp.set_update_note(note)
            if res.status == "new":
                self.show(res.release)
            return
        if res.status == "new":          # silent: dialog 32 only on screen 1
            self.pending = res.release
            self._offer_when_home()

    def _home(self) -> bool:
        a = self.app
        return (a.page == "import" and not a.settings_open and not a.help_open and not a.saving
                and Popup.current is None)

    def _offer_when_home(self):
        if self.pending is None:
            return
        if self._home():
            rel, self.pending = self.pending, None
            self.show(rel)
        else:
            self.app.root.after(1000, self._offer_when_home)

    # ------------------------------------------------------------------ dialog 32 + download
    def show(self, rel: U.Release):
        self.release = rel
        self.dialog = UpdateDialog(self.app, rel.version, self._download, self._later, self._cancel_download)
        return self.dialog

    def _later(self):
        """«Позже»: nothing until the next day (the silent check is once a day)."""
        self.app.settings.set("last_update_check", U.now_iso())

    def _cancel_download(self):
        if self._cancel is not None:
            self._cancel.set()

    def _download(self):
        rel = self.release
        cancel = threading.Event()
        self._cancel = cancel
        dlg = self.dialog

        def progress(done, total):
            self._q.put((lambda _r, _e: dlg.set_progress(done, total), None, None))

        def work():
            path = U.download(rel, self.dest_dir, progress, cancel, self.opener)
            ok = U.verify(path, U.expected_sha256(rel, self.fetcher))
            return path, ok
        self._run(work, self._downloaded)

    def _downloaded(self, res, exc):
        app = self.app
        t = app.t
        dlg = self.dialog
        if isinstance(exc, U.DownloadCancelled) or (self._cancel is not None and self._cancel.is_set()):
            return
        if dlg is not None and not dlg.closed:
            dlg.close()
        if exc is not None:
            log.warning("update download failed: %s", exc)
            ContentDialog(app, t("update.download_failed"), "", [(t("common.ok"), "primary", None)], width=420)
            return
        path, ok = res
        if not ok:
            ContentDialog(app, t("update.damaged"), "", [(t("common.ok"), "primary", None)], width=420)
            return
        if self.launcher(path):
            self.quit()
        else:
            ContentDialog(app, t("update.download_failed"), "", [(t("common.ok"), "primary", None)], width=420)
