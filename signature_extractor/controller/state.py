"""Application state that is not tied to widgets."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from signature_extractor.i18n.loader import Catalog
from signature_extractor.settings.folders import default_save_folder
from signature_extractor.settings.store import SettingsStore
from signature_extractor.settings.system_locale import system_language

logger = logging.getLogger(__name__)

SHELL_PAGES = ("import", "process", "export")
Listener = Callable[[], None]


class AppController:
    """Navigation and settings changes.

    Screens 2 and 3 stay closed until a later stage sets ``has_result``.
    There is no unsaved work in stage 1, so the restart dialog is not shown;
    ``confirm_discard`` is the hook those stages will call.
    """

    def __init__(self, settings: dict[str, Any], store: SettingsStore, catalog: Catalog):
        self.settings = settings
        self.store = store
        self.catalog = catalog
        self.page = "import"
        self.return_page = "import"
        self.has_result = False
        self.unsaved = False
        self._listeners: list[Listener] = []

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def language(self) -> str:
        mode = self.settings.get("language", "system")
        if mode == "system":
            return system_language()
        if mode in ("ru", "en"):
            return mode
        return "en"

    def text(self, key: str, **params: object) -> str:
        return self.catalog.text(key, self.language(), **params)

    def theme_mode(self) -> str:
        mode = self.settings.get("theme", "system")
        if mode in ("system", "light", "dark"):
            return mode
        return "system"

    def set_theme(self, mode: str) -> None:
        if mode not in ("system", "light", "dark"):
            return
        self.settings["theme"] = mode
        self._persist()

    def set_language_mode(self, mode: str) -> None:
        if mode not in ("system", "ru", "en"):
            return
        self.settings["language"] = mode
        self._persist()

    def update_setting(self, key: str, value: Any) -> None:
        self.settings[key] = value
        self._persist()

    def save_folder(self) -> str:
        stored = self.settings.get("save_folder")
        if isinstance(stored, str) and stored.strip():
            return stored
        return str(default_save_folder(self.text("export.default_folder")))

    def name_template(self) -> str:
        stored = self.settings.get("name_template")
        if isinstance(stored, str) and stored.strip():
            return stored
        return self.text("settings.name_template.value")

    def open_settings(self) -> None:
        if self.page != "settings":
            if self.page in SHELL_PAGES:
                self.return_page = self.page
        self.page = "settings"
        self._notify()

    def open_help(self) -> None:
        if self.page != "help":
            if self.page in SHELL_PAGES:
                self.return_page = self.page
        self.page = "help"
        self._notify()

    def close_overlay(self) -> None:
        target = self.return_page if self.return_page in SHELL_PAGES else "import"
        self.page = target
        self._notify()

    def show_step(self, step: int) -> None:
        """Step 1 is always the import screen. Steps 2 and 3 need a result."""
        if step == 1:
            self.page = "import"
            self._notify()
            return
        if not self.has_result:
            logger.debug("step %s is unavailable until a photo has been opened", step)
            return
        self.page = {2: "process", 3: "export"}.get(step, "import")
        self._notify()

    def step_enabled(self, step: int) -> bool:
        if step == 1:
            return True
        return self.has_result

    def active_step(self) -> int:
        return {"import": 1, "process": 2, "export": 3}.get(self.page, 1)

    def confirm_discard(self) -> bool:
        """Whether opening a new file may discard the current job.

        Stage 1 has nothing to discard, so this is always true. Stage 2 shows
        the "Start over?" dialog when ``unsaved`` is set and uses the result.
        """
        return not self.unsaved

    def _persist(self) -> None:
        try:
            self.store.save(self.settings)
        except OSError:
            logger.exception("could not save settings")
        self._notify()

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()
