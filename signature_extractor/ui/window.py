"""Main window: shell, pages, shortcuts."""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageTk

from signature_extractor import __version__
from signature_extractor.controller.state import AppController
from signature_extractor.paths import app_icon_path, license_path
from signature_extractor.ui.icons import icon_image, pil_icon
from signature_extractor.ui.popup import BorderlessPopup
from signature_extractor.ui.pages.help_page import HelpPage
from signature_extractor.ui.pages.import_page import ImportPage
from signature_extractor.ui.pages.settings_page import SettingsPage
from signature_extractor.ui.pages.stub_page import StubPage
from signature_extractor.ui.theme import (
    URL_GPL,
    URL_ISSUES,
    URL_RELEASE_NOTES,
    URL_SOURCE,
    WINDOW_HEIGHT,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_WIDTH,
    apply_appearance_mode,
    pair,
)
from signature_extractor.ui.tooltip import Tooltip
from signature_extractor.ui.widgets.dialogs import AboutDialog, RestartDialog
from signature_extractor.ui.widgets.menu import OverflowMenu
from signature_extractor.ui.widgets.stepper import Stepper

logger = logging.getLogger(__name__)

_IMAGE_FILTER = (
    ("JPG, PNG, BMP, TIFF, WebP, HEIC", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp *.heic *.heif"),
)


class MainWindow(ctk.CTk):
    def __init__(self, controller: AppController):
        apply_appearance_mode(controller.theme_mode())
        super().__init__(fg_color=pair("bg"))
        self.controller = controller
        self._modal = False
        self._menu_images: list[ImageTk.PhotoImage] = []
        self._seen_mode = (ctk.get_appearance_mode() or "Light").lower()

        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self._center()
        self._apply_icon()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.shell = ctk.CTkFrame(self, fg_color="transparent", height=64)
        self.shell.grid(row=0, column=0, sticky="ew")
        self.shell.grid_propagate(False)
        self.stepper = Stepper(self.shell, self._on_step)
        self.stepper.place(relx=0.5, rely=0.5, anchor="center")
        self.more = ctk.CTkButton(
            self.shell,
            text="",
            width=36,
            height=36,
            corner_radius=4,
            fg_color="transparent",
            hover_color=pair("menu_hover"),
            image=icon_image("dots", 20, "text"),
            command=self._toggle_menu,
        )
        self.more.place(relx=1.0, x=-12, rely=0.5, anchor="e")
        Tooltip(self.more, lambda: self.controller.text("shell.more"))
        self.menu = OverflowMenu(self)

        self.import_page = ImportPage(
            self,
            self.controller.text,
            self.open_file_dialog,
            self.open_folder_dialog,
            self.show_help,
        )
        self.process_page = StubPage(self)
        self.export_page = StubPage(self)
        self.settings_page = SettingsPage(
            self,
            controller,
            on_back=self.controller.close_overlay,
            on_change_folder=self._change_folder,
            on_open_folder=self._open_save_folder,
            on_open_url=self.open_url,
            on_check_updates=self.check_for_updates,
        )
        self.help_page = HelpPage(self, self.controller.text, self.controller.close_overlay)

        self.bind("<Control-o>", self._shortcut_open)
        self.bind("<Control-O>", self._shortcut_open)
        self.bind("<Escape>", self._shortcut_escape)

        controller.subscribe(self.apply_state)
        self.apply_state()
        self.after(200, self._watch_theme)

    def apply_state(self) -> None:
        apply_appearance_mode(self.controller.theme_mode())
        self.title(self.controller.text("app.name"))
        self._show_page(self.controller.page)
        self.import_page.retranslate()
        self.settings_page.retranslate()
        self.help_page.retranslate()
        self.stepper.set_labels(
            [
                self.controller.text("shell.step.import"),
                self.controller.text("shell.step.process"),
                self.controller.text("shell.step.export"),
            ]
        )
        self.stepper.set_state(
            self.controller.active_step(),
            {step: self.controller.step_enabled(step) for step in (1, 2, 3)},
        )
        self.menu.hide()
        self.import_page.refresh_chrome()

    def _show_page(self, page: str) -> None:
        for widget in (
            self.import_page,
            self.process_page,
            self.export_page,
            self.settings_page,
            self.help_page,
        ):
            widget.grid_remove()
        if page in ("import", "process", "export"):
            self.shell.grid(row=0, column=0, sticky="ew")
            target = {"import": self.import_page, "process": self.process_page, "export": self.export_page}[page]
            target.grid(row=1, column=0, sticky="nsew", padx=24, pady=24)
        else:
            self.shell.grid_remove()
            target = self.settings_page if page == "settings" else self.help_page
            target.grid(row=0, column=0, rowspan=2, sticky="nsew")

    def _on_step(self, step: int) -> None:
        self.controller.show_step(step)

    def _toggle_menu(self) -> None:
        if self.menu.is_open():
            self.menu.hide()
            return
        from signature_extractor.ui.theme import current_palette

        palette = current_palette()
        specs = (
            ("menu.open_file", "image", self.open_file_dialog),
            ("menu.add_folder", "folder", self.open_folder_dialog),
            ("menu.settings", "gear", self.controller.open_settings),
            ("menu.help", "help", self.show_help),
            ("menu.about", "info", self.show_about),
        )
        self._menu_images = []
        items = []
        for key, icon_name, command in specs:
            image = ImageTk.PhotoImage(pil_icon(icon_name, 16, "text", palette))
            self._menu_images.append(image)
            items.append((self.controller.text(key), image, command))
        self.menu.set_items(items)
        self.menu.show(self.more)

    def open_file_dialog(self) -> None:
        if not self.controller.confirm_discard():
            self._ask_restart(self._pick_file)
            return
        self._pick_file()

    def open_folder_dialog(self) -> None:
        if not self.controller.confirm_discard():
            self._ask_restart(self._pick_folder)
            return
        self._pick_folder()

    def _pick_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title=self.controller.text("menu.open_file"),
            filetypes=_IMAGE_FILTER,
        )
        if path:
            logger.info("selected file (processing starts in stage 2): %s", path)

    def _pick_folder(self) -> None:
        path = filedialog.askdirectory(
            parent=self,
            title=self.controller.text("import.batch_folder"),
            mustexist=True,
        )
        if path:
            logger.info("selected folder (batch processing starts in stage 2): %s", path)

    def _ask_restart(self, then) -> None:
        self._modal = True

        def finish() -> None:
            self._modal = False

        def confirm() -> None:
            finish()
            then()

        RestartDialog(self, self.controller.text, confirm, finish)

    def show_help(self) -> None:
        self.controller.open_help()

    def show_about(self) -> None:
        self._modal = True

        def close() -> None:
            self._modal = False

        def url(kind: str) -> None:
            if kind == "source":
                self.open_url(URL_SOURCE)
            elif kind == "notes":
                self.open_url(URL_RELEASE_NOTES)
            elif kind == "license":
                path = license_path()
                self.open_url(path.as_uri() if path is not None else URL_GPL)

        AboutDialog(self, self.controller.text, __version__, close, url, lambda: self.open_url(URL_ISSUES))

    def check_for_updates(self) -> None:
        """Stage 5 owns the update check. The button is visible and does not call the network."""
        logger.info("update check is not implemented in stage 1")

    def open_url(self, url: str) -> None:
        import webbrowser

        webbrowser.open(url)

    def _change_folder(self) -> None:
        path = filedialog.askdirectory(
            parent=self,
            title=self.controller.text("settings.folder"),
            mustexist=False,
        )
        if path:
            self.controller.update_setting("save_folder", path)

    def _open_save_folder(self) -> None:
        from pathlib import Path
        import os
        import subprocess

        folder = Path(self.controller.save_folder())
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.exception("could not create the save folder")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError:
            logger.exception("could not open the save folder")

    def _shortcut_open(self, _event=None):
        if self._modal:
            return "break"
        self.open_file_dialog()
        return "break"

    def _shortcut_escape(self, _event=None):
        if BorderlessPopup.close_all() or self.menu.is_open():
            self.menu.hide()
            return "break"
        if self._modal:
            return "break"
        if self.controller.page in ("settings", "help"):
            self.controller.close_overlay()
        return "break"

    def _watch_theme(self) -> None:
        mode = (ctk.get_appearance_mode() or "Light").lower()
        if mode != self._seen_mode:
            self._seen_mode = mode
            self.import_page.refresh_chrome()
        self.after(250, self._watch_theme)

    def _center(self) -> None:
        self.update_idletasks()
        width = WINDOW_WIDTH
        height = WINDOW_HEIGHT
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _apply_icon(self) -> None:
        try:
            image = Image.open(app_icon_path()).convert("RGBA")
            self._icon_photo = ImageTk.PhotoImage(image.resize((64, 64)))
            self.iconphoto(True, self._icon_photo)
        except (OSError, tk.TclError):
            logger.exception("could not set the window icon")
        if sys.platform.startswith("win"):
            try:
                self.iconbitmap(str(app_icon_path()))
            except tk.TclError:
                logger.exception("could not set the Windows title-bar icon")

