"""Main window (screens 1–3 + Settings); the state itself lives in ``core.state`` (remark 82)."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog
from typing import List, Sequence

import customtkinter as ctk

from core import processing as P
from core.i18n import I18n
from core.settings import SettingsManager
from core.state import AppState
from core.worker import BackgroundWorker
from ui import gfx, platform_win
from ui.theme import HEADER_H, Fonts, Scale, Theme
from ui.widgets.base import Registry, Tooltip
from ui.widgets.overlay import MenuItem, MenuPopup, Popup, TooltipLayer, widget_rect

log = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
# remark 84: Git tag v1.0 (not v1.0.0); RELEASE_TAG, REPO_URL, LICENSE_URL are used as A.* (about dialog, tests)
from core.version import LICENSE_URL, RELEASE_TAG, REPO_URL, VERSION   # noqa: E402, F401
CLIENT_W, CLIENT_H = 1280, 768      # 1280 × 800 together with the 32 px title bar (mockups)
MIN_W, MIN_H = 1024, 648            # 1024 × 680 window


try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    class _Root(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            try:
                self.TkdndVersion = TkinterDnD._require(self)
                self.dnd_ok = True
            except Exception:
                log.warning("tkdnd not available, drag and drop disabled", exc_info=True)
                self.dnd_ok = False
except Exception:  # pragma: no cover
    log.warning("module: Exception caught", exc_info=True)   # remark 81, 115
    DND_FILES = None

    class _Root(ctk.CTk):
        dnd_ok = False


# Job / EditState live in core.batch since stage 4 (one class for a single photo and a batch item)
from core.batch import LOADED_MAX, Batch, EditState, Job  # noqa: E402  (re-exported for tests)
from core import batch as B  # noqa: E402


def _state(name: str, doc: str = ""):
    """Remark 82: an App attribute kept in the state controller (core.state.AppState)."""
    return property(lambda self: getattr(self.state, name), lambda self, v: setattr(self.state, name, v), doc=doc)


class App:
    VERSION_STR = VERSION
    job = _state("job", "current photo")
    batch = _state("batch", "stage 4: folder / several files")
    page = _state("page", "import | busy | process | export")
    saving = _state("saving", "a batch is being written (17): navigation is locked")
    settings_open = _state("settings_open")
    help_open = _state("help_open", "remark 30: «Справка» page from the ⋯ menu")
    _recent = _state("recent", "batch photos kept loaded (current + recent)")
    _load_error_shown = _state("load_error_shown")
    _pending_params = _state("pending_params")
    _work_token = _state("saved_token", "remark 39: snapshot of the last successful save")

    def __init__(self, argv: Sequence[str]):
        platform_win.enable_per_monitor_dpi_v2()
        self.state = AppState(LOADED_MAX)      # remark 82: page, photo, batch, saving … (no UI)
        self.settings = SettingsManager(list(argv))
        self.i18n = I18n(ROOT_DIR / "i18n" / "strings_ru_en.csv", self.settings.effective_language())
        self.settings.fix_save_folder(self.t("export.default_folder"))      # remark 83
        self.root = _Root()
        from core.logs import tk_callback_error
        self.root.report_callback_exception = tk_callback_error      # remark 81: callback errors go to the log
        gfx.clear_cache()      # PhotoImages belong to one Tk interpreter (several apps in one test run)
        self.root.withdraw()
        Scale.factor = ctk.ScalingTracker.get_widget_scaling(self.root)
        Fonts.init(self.root)
        self.worker = BackgroundWorker()
        self._last_size = (0, 0)

        self._apply_theme(initial=True)
        self.root.title(self.t("app.name"))
        self._set_icon()
        self._apply_initial_geometry()      # remark 92: remembered size, centred, fitted to the screen

        from ui.shell import Header
        from ui.pages.import_page import ImportPage
        self.header = Header(self.root, self)
        self.import_page = ImportPage(self.root, self)
        self.process_page = None
        self.export_page = None
        self.settings_page = None
        self.help_page = None
        TooltipLayer(self)

        self.root.bind("<Configure>", self._on_configure)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        platform_win.acquire_instance_mutex()          # stage 6: the installer asks to close the running app
        self._bind_keys()
        self._setup_dnd()
        ctk.ScalingTracker.add_widget(self._on_scaling, self.root)
        self._worker_polling = False
        self.worker.on_submit = self._start_worker_poll     # remark 118 (audit B14): poll only while tasks run
        if self.worker.busy():
            self._start_worker_poll()
        self.root.after(1500, self._poll_system_theme)
        self._updates = None
        self.root.after(3000, lambda: self.updates.startup())     # stage 5: silent check, once a day
        self.root.deiconify()
        # CustomTkinter remembers a withdraw() made before the first mainloop() and, on Windows,
        # hides the window again when mainloop() starts (it applies the title-bar colour and then
        # skips deiconify). We have shown the window ourselves, so clear that flag.
        self.root._withdraw_called_before_window_exists = False
        self.root.update_idletasks()
        platform_win.set_caption_colors(self.root, Theme.c("bg"), Theme.c("text"), Theme.dark())
        if self._start_maximized:
            self.set_maximized(True)
        self.update_header()
        self.layout()

    # ------------------------------------------------------------------ basics
    def t(self, key: str, **kw) -> str:
        return self.i18n.t(key, **kw)

    def tn(self, key: str, n: int, **kw) -> str:
        return self.i18n.tn(key, n, **kw)

    def width(self) -> float:
        return max(1, self.root.winfo_width()) / Scale.factor

    def height(self) -> float:
        return max(1, self.root.winfo_height()) / Scale.factor

    def run(self):
        self.root.mainloop()

    def _set_icon(self):
        ico = ROOT_DIR / "assets" / "app.ico"
        try:
            if sys.platform.startswith("win"):
                platform_win.set_app_user_model_id("StanislauSalavei.SignatureExtractor")
                self.root.iconbitmap(default=str(ico))
            else:
                from PIL import Image, ImageTk
                im = Image.open(ico)
                self._icon_img = ImageTk.PhotoImage(im.resize((32, 32)))
                self.root.iconphoto(True, self._icon_img)
        except Exception:
            log.warning("cannot set window icon", exc_info=True)

    # ------------------------------------------------------------------ theme / language
    def _resolved_mode(self) -> str:
        pref = self.settings.get("theme", "system")
        if pref in ("light", "dark"):
            return pref
        return "dark" if platform_win.system_is_dark() else "light"

    def _apply_theme(self, initial=False):
        changed = Theme.set_mode(self._resolved_mode())
        if changed or initial:              # remark 118 (audit C7): not on every 1.5 s poll of the system theme
            ctk.set_appearance_mode(Theme.mode)
            self.root.configure(fg_color=Theme.c("bg"))
        if initial:
            return
        if changed:
            Popup.close_current()
            Tooltip.cancel(None)
            Registry.refresh_all()
            platform_win.set_caption_colors(self.root, Theme.c("bg"), Theme.c("text"), Theme.dark())

    def set_theme_pref(self, pref: str):
        self.settings.set("theme", pref)
        self._apply_theme()

    def reset_settings(self):
        """Remark 37: every setting back to its default (own size templates and colours stay, last_export is
        forgotten); theme and language apply at once; the work on screens 2–3 is not touched."""
        self.settings.reset_to_defaults()
        self._apply_theme()
        lang = self.settings.effective_language()
        if lang != self.i18n.lang:
            self.set_language_pref(self.settings.get("language", "system"))
        self.settings.fix_save_folder(self.t("export.default_folder"))      # remark 83: in the language after reset
        if self.settings_page is not None:
            self.settings_page.sync()

    def _poll_system_theme(self):
        try:
            if self.settings.get("theme") == "system":
                self._apply_theme()
        finally:
            self.root.after(1500, self._poll_system_theme)

    def set_language_pref(self, pref: str):
        self.settings.set("language", pref)
        lang = self.settings.effective_language()
        if lang != self.i18n.lang:
            self.i18n.set_language(lang)
            self.root.title(self.t("app.name"))
            Popup.close_current()
            Registry.refresh_all()
            self.update_header()
            self.layout()

    def _on_scaling(self, widget_scaling, _window_scaling):   # CustomTkinter ScalingTracker callback
        Scale.factor = widget_scaling
        Fonts.clear()
        gfx.clear_cache()
        Popup.close_current()
        Registry.refresh_all()
        self.layout()

    # ------------------------------------------------------------------ window size (remark 92)
    def _window_scale(self) -> float:
        try:
            return float(ctk.ScalingTracker.get_window_scaling(self.root)) or 1.0
        except Exception:
            log.warning("_window_scale: Exception caught", exc_info=True)   # remark 115
            return 1.0

    def _apply_initial_geometry(self):
        """Size and maximized state from the last launch; the position is not remembered — centred in the
        work area; a size larger than the current screen is reduced to fit."""
        from core import window_geom as WG
        scale = self._window_scale()
        w, h, x, y, maxi, mw, mh = WG.initial_geometry(
            self.settings.get("window"), platform_win.work_area(self.root), platform_win.frame_extra(self.root),
            scale, (CLIENT_W, CLIENT_H), (MIN_W, MIN_H))
        self.root.minsize(mw, mh)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self._normal_size = (w, h)
        self._start_maximized = maxi
        self._was_maximized = maxi

    def is_maximized(self) -> bool:
        try:
            if sys.platform.startswith("win"):
                return self.root.state() == "zoomed"
            # X11 (development only): without a window manager the attribute may not be applied
            return bool(int(self.root.attributes("-zoomed"))) or bool(getattr(self, "_x11_zoomed", False))
        except Exception:
            log.debug("is_maximized: Exception caught", exc_info=True)
            return False

    def set_maximized(self, on: bool):
        try:
            if sys.platform.startswith("win"):
                self.root.state("zoomed" if on else "normal")
            else:
                self._x11_zoomed = bool(on)
                self.root.attributes("-zoomed", bool(on))
        except Exception:
            log.warning("set_maximized: Exception caught", exc_info=True)
        self._was_maximized = bool(on)

    def _track_window(self, e):
        try:
            st = self.root.state()
        except Exception:
            log.debug("_track_window: Exception caught", exc_info=True)
            return
        if st not in ("normal", "zoomed"):           # minimized: keep what was known before
            return
        maxi = self.is_maximized()
        self._was_maximized = maxi
        if not maxi and e.width > 1 and e.height > 1:
            sc = self._window_scale()
            self._normal_size = (e.width / sc, e.height / sc)

    def save_window_state(self):
        """Remember the normal size and the maximized flag (logical px) in settings.json."""
        from core import window_geom as WG
        try:
            w, h = getattr(self, "_normal_size", (CLIENT_W, CLIENT_H))
            val = WG.to_saved(w, h, getattr(self, "_was_maximized", False))
            if self.settings.get("window") != val:
                self.settings.set("window", val)
        except Exception:
            log.warning("save_window_state: Exception caught", exc_info=True)

    def _on_close(self):
        self.save_window_state()
        try:
            self.worker.cancel("process")
        except Exception:
            log.warning("App._on_close: Exception caught", exc_info=True)
        self.root.destroy()

    # ------------------------------------------------------------------ layout
    def _on_configure(self, e):
        if e.widget is not self.root:
            return
        self._track_window(e)
        size = (e.width, e.height)
        if size != self._last_size:
            self._last_size = size
            Popup.close_current()
            self.layout()

    def layout(self):
        w, h = self.width(), self.height()
        if self.settings_open and self.settings_page:
            self.settings_page.layout(w, h)
            return
        if self.help_open and self.help_page:
            self.help_page.layout(w, h)
            return
        self.header.layout(w)
        body_h = h - HEADER_H
        pages = {"import": self.import_page, "busy": self.import_page,
                 "process": self.process_page, "export": self.export_page}
        for name, pg in (("import", self.import_page), ("process", self.process_page), ("export", self.export_page)):
            if pg is None:
                continue
            if pg is pages[self.page]:
                pg.layout(w, body_h)
            else:
                pg.hide()

    def update_header(self):
        labels = [self.t("shell.step.import"), self.t("shell.step.process"), self.t("shell.step.export")]
        can_export = self.can_export()
        if self.page in ("import",):
            active, done, enabled = 0, set(), {0}
        elif self.page == "busy":
            active, done, enabled = 1, {0}, {1}
        elif self.page == "process":
            active, done = 1, {0}
            enabled = {0, 1} | ({2} if can_export else set())
        else:
            active, done, enabled = 2, {0, 1}, {0, 1, 2}
        self.header.stepper.set_state(labels, active, done, enabled)
        self.header.layout(self.width())

    def show_page(self, name: str):
        self.state.set_page(name)
        Popup.close_current()
        if name == "process" and self.process_page is None:
            from ui.pages.process_page import ProcessPage
            self.process_page = ProcessPage(self.root, self)
        if name == "export" and self.export_page is None:
            from ui.pages.export_page import ExportPage
            self.export_page = ExportPage(self.root, self)
        self.import_page.drop.set_mode("busy" if name == "busy" else "idle")
        if name == "process":
            self.process_page.on_show()
        if name == "export":
            self.export_page.on_show()
        self.update_header()
        self.layout()

    def on_step_click(self, i: int):
        if self.saving:
            return
        if i == 0:
            self.confirm_restart(self.go_home)
        elif i == 1 and self.page == "export":
            self.show_page("process")
        elif i == 2 and self.page == "process":
            self.go_export()

    # ------------------------------------------------------------------ settings page
    def overlay_open(self) -> bool:
        """A full-window page (Параметры or Справка) covers the steps."""
        return self.state.overlay_open()

    def open_settings(self):
        if self.help_open:
            self._hide_help()
        if self.settings_page is None:
            from ui.pages.settings_page import SettingsPage
            self.settings_page = SettingsPage(self.root, self)
        self.settings_open = True
        Popup.close_current()
        for pg in (self.header, self.import_page, self.process_page, self.export_page):
            if pg is not None:
                pg.hide()
        self.settings_page.on_show()
        self.layout()

    def close_settings(self):
        if not self.settings_open:
            return
        self.settings_open = False
        Popup.close_current()
        self.settings_page.update_note = ""      # stage 5: the grey update line lasts until Settings close
        self.settings_page.hide()
        self.update_header()
        self.layout()
        if self.page == "export" and self.export_page:
            self.export_page.on_settings_changed()

    # ------------------------------------------------------------------ menu ⋯
    def open_more_menu(self):
        if self.saving:      # stage 4: ⋯ is inactive while a batch is written (17)
            return
        x, y, w, h = widget_rect(self.root, self.header.more)
        items = [MenuItem(self.t("menu.open_file"), self.open_file_dialog, "image_menu"),
                 MenuItem(self.t("menu.add_folder"), self.open_folder_dialog, "folder"),
                 MenuItem(self.t("menu.start_over"), self.start_over, "reset",          # remark 71
                          disabled=not self.has_photos()),
                 None,
                 MenuItem(self.t("menu.settings"), self.open_settings, "gear"),
                 MenuItem(self.t("menu.help"), self.open_help, "help"),
                 MenuItem(self.t("menu.about"), self.open_about, "about")]
        MenuPopup(self, items, x + w, y + h + 4, align_right=True)

    def has_photos(self) -> bool:
        """Remark 71: something is loaded (or loading) — «Начать заново» is grey on screen 1 without photos."""
        return self.state.has_photos()

    def start_over(self):
        """Remark 71: ⋯ › «Начать заново» always asks «Начать заново?», then goes to screen 1."""
        if self.saving or not self.has_photos():
            return
        from ui.dialogs.content import ContentDialog

        def go():
            if self.settings_open:
                self.settings_open = False
                self.settings_page.hide()
            if self.help_open:
                self._hide_help()
            self.go_home()
            self.update_header()
            self.layout()
        return ContentDialog(self, self.t("dialog.restart.title"), self.t("dialog.restart.body"),
                             [(self.t("dialog.restart.ok"), "primary", go), (self.t("common.cancel"), "secondary", None)],
                             esc_index=1)

    def open_help(self, topic: str = "start"):
        """⋯ › «Справка»: a page in the main window, like «Параметры» (remark 30)."""
        if self.settings_open:
            self.settings_open = False
            self.settings_page.hide()
        if self.help_page is None:
            from ui.pages.help_page import HelpPage
            self.help_page = HelpPage(self.root, self)
        self.help_open = True
        Popup.close_current()
        for pg in (self.header, self.import_page, self.process_page, self.export_page):
            if pg is not None:
                pg.hide()
        self.help_page.on_show(topic)
        self.layout()
        self.help_page.area.scroll_to(0)

    def _hide_help(self):
        self.help_open = False
        Popup.close_current()
        self.help_page.hide()

    def close_help(self):
        if not self.help_open:
            return
        self._hide_help()
        self.update_header()
        self.layout()
        cur = {"process": self.process_page, "export": self.export_page}.get(self.page)
        if cur is not None and hasattr(cur, "area"):
            cur.area.bind_wheel()      # hide() unbound the wheel of the page under the help page

    def open_help_prep(self):
        from ui.dialogs.formats_help import HelpWindow
        HelpWindow.open(self, "prep")

    def open_formats_help(self):
        from ui.dialogs.formats_help import HelpWindow
        HelpWindow.open(self, "formats")

    def open_about(self):
        from ui.dialogs.about import AboutDialog
        AboutDialog(self)

    def report_issue(self):
        """«Сообщить о проблеме» (stage 5): a new GitHub issue with the app version, Windows and the language
        already filled in (English body, no title — user decision; remark 88: no graphics card / DirectX 12)."""
        self.open_url(self.issue_url())

    def issue_url(self) -> str:
        import urllib.parse
        from ui import platform_win as pw
        body = self.t("issue.body", version=self.VERSION_STR, windows=pw.windows_version(),
                      lang=self.i18n.lang).replace("\\n", "\n")
        url = f"{REPO_URL}/issues/new?" + urllib.parse.urlencode({"body": body})
        return url[:2000]

    @property
    def updates(self):
        """Remark 118 (audit C9): core.updater (urllib, ssl) is imported when the check starts (3 s after the
        start or «Проверить сейчас»), not while the window opens."""
        if self._updates is None:
            from ui.updates import UpdateController
            self._updates = UpdateController(self)
        return self._updates

    def check_for_updates(self, manual: bool = True):
        self.updates.check(manual=manual)

    def quit(self):
        """Close the app (the update installer has started)."""
        self.save_window_state()
        try:
            self.worker.cancel("process")
        except Exception:
            log.warning("App.quit: Exception caught", exc_info=True)   # remark 81
        self.root.after(1, self.root.destroy)

    def open_url(self, url: str):
        try:
            webbrowser.open(url)
        except Exception:
            log.exception("cannot open %s", url)

    def open_folder(self, path: Path):
        try:
            path.mkdir(parents=True, exist_ok=True)
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception:
            log.exception("cannot open folder %s", path)

    # ------------------------------------------------------------------ keys
    def _bind_keys(self):
        r = self.root
        # remark 80: one handler for every Ctrl+letter, by the physical key (any keyboard layout, ui/keys.py)
        r.bind_all("<Control-KeyPress>", self._ctrl_key, add="+")
        r.bind_all("<Escape>", self._esc, add="+")
        # stage 4: ← / → switch photos of the batch (screens 2 and 3)
        r.bind_all("<Left>", lambda e: self._arrow_key(-1), add="+")
        r.bind_all("<Right>", lambda e: self._arrow_key(1), add="+")

    def _arrow_key(self, d):
        if self.batch is None or self.saving or self.overlay_open() or self.page not in ("process", "export"):
            return None
        if isinstance(self.root.focus_get(), tk.Entry) or Popup.current is not None:
            return None
        self.step_photo(d)
        return "break"

    def _ctrl_key(self, e):
        """Ctrl+O open, Ctrl+S export, Ctrl+Z undo, Ctrl+Y / Ctrl+Shift+Z redo, Ctrl+V paste — whatever the
        layout.  In a text field with a non-Latin layout the field's own Ctrl+A/C/V/X/Z/Y are sent as Tk
        virtual events (with a Latin layout Tk's class bindings already did it)."""
        from ui import keys as K
        try:
            ws = self.root.tk.call("tk", "windowingsystem")
        except tk.TclError:
            log.debug("windowingsystem unknown", exc_info=True)
            ws = ""
        letter = K.latin_letter(str(e.keysym), int(e.keycode or 0), ws)
        if letter is None:
            return None
        shift = bool(int(e.state or 0) & K.SHIFT)
        focus = self.root.focus_get()
        if isinstance(focus, tk.Entry) and not K.is_latin_keysym(str(e.keysym)) and letter in K.ENTRY_EVENTS:
            focus.event_generate(K.ENTRY_EVENTS[letter])
            return "break"
        if letter == "o":
            return self._key(self.open_file_dialog)
        if letter == "s":
            return self._key(self.go_export)
        if letter == "z":
            return self._key(self.redo if shift else self.undo, text_ok=False)
        if letter == "y":
            return self._key(self.redo, text_ok=False)
        if letter == "v":
            return self._key(self.paste_clipboard, text_ok=False)
        return None

    def _key(self, fn, text_ok=True):
        if self.saving:
            return "break"
        focus = self.root.focus_get()
        if not text_ok and isinstance(focus, tk.Entry):
            return None  # let the text field handle its own undo / paste
        if Popup.current is not None and not isinstance(Popup.current, MenuPopup):
            return "break"
        fn()
        return "break"

    def _esc(self, e=None):
        if Popup.current is not None:
            getattr(Popup.current, "escape", Popup.current.close)()
            return "break"
        if self.settings_open:
            self.close_settings()
            return "break"
        if self.help_open:
            self.close_help()
            return "break"
        return None

    # ------------------------------------------------------------------ drag and drop
    def _setup_dnd(self):
        if not getattr(self.root, "dnd_ok", False) or DND_FILES is None:
            return
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<DropEnter>>", self._dnd_enter)
            self.root.dnd_bind("<<DropPosition>>", lambda e: e.action)
            self.root.dnd_bind("<<DropLeave>>", self._dnd_leave)
            self.root.dnd_bind("<<Drop>>", self._dnd_drop)
        except Exception:
            log.warning("drop target registration failed", exc_info=True)

    def _dnd_enter(self, e):
        if self.page == "import" and not self.overlay_open():
            self.set_drag_over(True)
        return e.action

    def _dnd_leave(self, e):
        self.set_drag_over(False)
        return e.action

    def _dnd_drop(self, e):
        self.set_drag_over(False)
        try:
            paths = [Path(p) for p in self.root.tk.splitlist(e.data)]
        except Exception:
            log.debug("App._dnd_drop: Exception caught", exc_info=True)   # remark 81
            paths = []
        if paths and not self.saving:
            # decision 7: a drop on screens 2–3 is new work («Начать заново?» when there is unsaved work)
            self.root.after(1, lambda: self.confirm_restart(lambda: self.open_paths(paths)))
        return e.action

    def set_drag_over(self, on: bool):
        if self.page == "import":
            self.import_page.drop.set_mode("over" if on else "idle")

    # ------------------------------------------------------------------ opening files
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

    # remark 39: «Начать заново?» when the work is not saved OR anything changed after the last successful
    # save — edits, Ctrl+Z/Y, «Убрать»/«Добавить», «Применить настройки ко всем», export settings, a cancelled
    # or failed save.  A snapshot of (photo id, version) per photo + the export settings is taken on a
    # successful save; «Назад»/«Далее» change nothing.
    def _export_key(self):
        ep = self.export_page
        return ep.export_key() if ep is not None else None

    def work_token(self):
        return self.state.work_token(self._export_key())

    def mark_saved(self):
        self.state.mark_saved(self._export_key())

    def mark_save_failed(self):
        self.state.mark_save_failed()

    def has_unsaved(self) -> bool:
        return self.state.has_unsaved(self._export_key())

    def confirm_restart(self, then):
        if self.saving:
            return
        if self.has_unsaved():
            from ui.dialogs.content import ContentDialog
            ContentDialog(self, self.t("dialog.restart.title"), self.t("dialog.restart.body"),
                          [(self.t("dialog.restart.ok"), "primary", then), (self.t("common.cancel"), "secondary", None)])
        else:
            then()

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
        # remark 74: «no signature» is the yellow card under the image (process_page.layout), not dialog 30

    def _load_failed(self, exc):
        self.go_home()
        name = exc.args[0] if isinstance(exc, P.ImageLoadError) and exc.args else "?"
        self.show_error_dialog(self.t("errors.open.title"), self.t("errors.open.body", file=name), width=460)

    def show_error_dialog(self, title, body, width=420, retry=None, on_cancel=None):
        from ui.dialogs.content import ContentDialog
        if retry:
            buttons = [(self.t("errors.retry"), "primary", retry), (self.t("common.cancel"), "secondary", on_cancel)]
        else:
            buttons = [(self.t("common.ok"), "primary", None)]
        ContentDialog(self, title, body, buttons, width=width, esc_index=1 if (retry and on_cancel) else None)

    def go_home(self, keep_error=False):
        self.reset_batch()
        self.job = None
        if not keep_error:
            self.import_page.clear_error()
        self.show_page("import")

    # ------------------------------------------------------------------ batch (stage 4)
    def reset_batch(self):
        for j in self.state.clear_batch():
            self.worker.cancel(f"job:{j.id}")

    def start_batch(self, batch: Batch):
        """Screen 03 while the first photo is processed, then screen 2; the rest runs in the background."""
        self.reset_batch()
        self.batch = batch
        self.job = None
        self.show_page("busy")
        self._start_first()

    def _start_first(self):
        b = self.batch
        if b is None:
            return
        if not b.items:
            self.go_home()
            return
        first = b.items[0]
        b.index = 0
        self.process_job(first, on_first=True)

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

    def _touch(self, job: Job):
        for old in self.state.touch(job):
            old.unload()

    def step_photo(self, d: int):
        if self.batch is not None:
            self.select_photo(self.batch.index + d)

    def select_photo(self, i: int):
        b = self.batch
        if b is None or self.saving or not b.items:
            return
        i = max(0, min(i, len(b.items) - 1))
        if i == b.index and self.job is b.current:
            return
        b.select(i)
        self._switch_to(b.current)

    def _switch_to(self, job: Job):
        self.job = job
        self._touch(job)
        if not job.loaded or job.busy:
            self.process_job(job)
        if self.page == "process" and self.process_page:
            self.process_page.on_switch()
        elif self.page == "export" and self.export_page:
            self.export_page.on_switch()
        self.update_header()

    def on_batch_changed(self, result_for_current=False, coalesce=False):
        if coalesce:
            # background results arrive in bursts: one relayout per ~60 ms is enough for the strip and bars
            if getattr(self, "_bc_after", None) is None:
                self._bc_after = self.root.after(60, self._batch_changed_now)
            return
        if self.page == "process" and self.process_page:
            if result_for_current:
                self.process_page.on_result()
            else:
                self.process_page.on_batch_changed()
        elif self.page == "export" and self.export_page:
            self.export_page.on_batch_changed()
        self.update_header()

    def _batch_changed_now(self):
        self._bc_after = None
        if self.batch is not None:
            self.on_batch_changed()

    def show_next_attention(self):
        if self.batch is not None:
            i = self.batch.next_attention()
            if i is not None:
                self.select_photo(i)

    def ask_remove_photo(self):
        """«Убрать» → dialog 15."""
        if self.batch is None or self.job is None or self.saving:
            return
        from ui.dialogs.content import ContentDialog
        job = self.job
        ContentDialog(self, self.t("batch.remove_title"), self.t("batch.remove_body", file=job.name),
                      [(self.t("common.remove"), "primary", lambda: self.remove_photo(job)),
                       (self.t("common.cancel"), "secondary", None)], width=420)

    def remove_photo(self, job: Job):
        b = self.batch
        if b is None:
            return
        self.worker.cancel(f"job:{job.id}")
        self.state.forget(job)
        nxt = b.remove(job)
        job.unload()
        if nxt is None:            # decision 9: the last photo removed → clean screen 1
            self.go_home()
            return
        self._switch_to(nxt)
        self.on_batch_changed()

    def add_photos_dialog(self):
        """«Добавить» (screen 2 of a batch): multi-file picker, photos join the current batch."""
        if self.batch is None or self.saving:
            return
        exts = " ".join("*" + e for e in sorted(P.SUPPORTED_EXT))
        names = filedialog.askopenfilenames(parent=self.root, title=self.t("common.add"),
                                            filetypes=[(self.t("menu.open_file"), exts)])
        if isinstance(names, str):
            names = self.root.tk.splitlist(names)
        if names:
            self.add_photos([Path(n) for n in names])

    def add_photos(self, paths: List[Path]):
        b = self.batch
        if b is None:
            return
        scan = P.scan_inputs(paths)
        added = b.add(scan.photos)
        b.add_skipped(scan.too_large)
        for j in added:
            self.process_job(j, background=True)
        self.on_batch_changed()
        if scan.skipped_other:
            from ui.dialogs.content import ContentDialog
            ContentDialog(self, self.t("import.skipped_title"),
                          self.tn("import.skipped_body", len(scan.skipped_other), photos=len(added)),
                          [(self.t("common.got_it"), "primary", None)], width=440)

    def apply_to_all(self):
        """«Применить настройки ко всем» (remark 38): asks first (dialog like «О программе», blue «Применить» +
        «Отмена», Esc = Отмена), then the current photo's right-panel settings go to every other photo."""
        b, job = self.batch, self.job
        if b is None or job is None or self.saving:
            return
        from ui.dialogs.content import ContentDialog
        others = len(b) - 1
        ContentDialog(self, self.t("dialog.apply_all.title"), self.tn("dialog.apply_all.body", others),
                      [(self.t("dialog.apply_all.ok"), "primary", self._apply_to_all_now),
                       (self.t("common.cancel"), "secondary", None)], width=440, esc_index=1)

    def _apply_to_all_now(self):
        b, job = self.batch, self.job
        if b is None or job is None or self.saving:
            return
        for j in b.apply_params_to_all(job.state.params, source=job):
            self.process_job(j, background=True)
        self.on_batch_changed()

    def close_skipped_bar(self):
        if self.batch is not None:
            self.batch.skipped_closed = True
            self.on_batch_changed()

    def show_skipped_list(self):
        """«Подробнее» → 47."""
        if self.batch is None:
            return
        from ui.dialogs.content import ContentDialog
        files = self.batch.skipped_large
        rows = []
        for f in files:
            try:
                size = self.t("batch.file_size", size=self.fmt_num(P.file_size_mb(f), 0))
            except OSError:
                log.debug("App.show_skipped_list: OSError caught", exc_info=True)   # remark 81
                size = ""
            rows.append((f.name, size))
        ContentDialog(self, self.tn("batch.skipped_large_title", len(files)), self.t("batch.skipped_large_body"),
                      [(self.t("common.close"), "primary", None)], width=440, rows=rows)

    def can_export(self) -> bool:
        return self.state.can_export()

    # ------------------------------------------------------------------ editing (screen 2)
    def edit(self, **changes):
        """Apply a change to the current photo, push it to the history and reprocess."""
        if not self.job:
            return
        st = self.job.state
        params = st.params
        pchanges = {k: v for k, v in changes.items() if k in P.ProcessParams.__dataclass_fields__}
        if pchanges:
            params = replace(params, **pchanges)
        new = EditState(params, changes.get("frame", st.frame), changes.get("eraser", st.eraser))
        self.job.push(new)
        if self.batch is not None:
            self.batch.saved = False
        self.reprocess()

    def reprocess(self):
        if self.job:
            self.process_job(self.job)

    def undo(self):
        if self.page != "process" or not self.job:
            return
        st = self.job.history.undo()
        if st is not None:
            self.job.set_state(st)
            self.reprocess()
            self.process_page.sync_controls()

    def redo(self):
        if self.page != "process" or not self.job:
            return
        st = self.job.history.redo()
        if st is not None:
            self.job.set_state(st)
            self.reprocess()
            self.process_page.sync_controls()

    def go_export(self):
        if self.overlay_open() or self.saving:
            return
        if self.page == "process" and self.can_export():
            self.show_page("export")

    def back_to_process(self):
        if self.page == "export" and not self.saving:
            self.show_page("process")

    def done_after_save(self):
        """«Готово»: clean screen 1 (55); export settings are remembered by the export page."""
        self.reset_batch()
        self.job = None
        self.show_page("import")

    # ------------------------------------------------------------------ worker
    def _start_worker_poll(self):
        if not self._worker_polling:
            self._worker_polling = True
            self.root.after(30, self._poll_worker)

    def _poll_worker(self):
        try:
            self.worker.poll()
        except Exception:
            log.exception("worker callback failed")
        if self.worker.busy():
            self.root.after(30, self._poll_worker)
        else:
            self._worker_polling = False

    # ------------------------------------------------------------------ formatting
    def fmt_num(self, v: float, digits: int = 1) -> str:
        s = f"{v:.{digits}f}"
        return s.replace(".", ",") if self.i18n.lang == "ru" else s
