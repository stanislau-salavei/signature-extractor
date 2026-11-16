"""Application entry point."""

from __future__ import annotations

import logging
import sys

from signature_extractor.controller.state import AppController
from signature_extractor.i18n.loader import load_catalog
from signature_extractor.settings.install_language import read_installer_language
from signature_extractor.settings.store import SettingsStore
from signature_extractor.ui.window import MainWindow

logger = logging.getLogger(__name__)

# Windows 10 1809.
_MIN_BUILD = 17763


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = list(sys.argv[1:] if argv is None else argv)
    _log_platform()
    _set_windows_app_id()
    store = SettingsStore()
    first_launch = not store.exists()
    settings = store.load()
    if first_launch:
        installer_language = read_installer_language(args)
        if installer_language in ("ru", "en"):
            settings["language"] = installer_language
            store.save(settings)
            logger.info("first launch uses the installer language: %s", installer_language)
    catalog = load_catalog()
    controller = AppController(settings, store, catalog)
    window = MainWindow(controller)
    window.mainloop()


def _set_windows_app_id() -> None:
    """Keep the taskbar icon attached to this app instead of python.exe."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "StanislauSalavei.SignatureExtractor"
        )
    except (AttributeError, OSError):
        logger.warning("could not set the Windows AppUserModelID", exc_info=True)


def _log_platform() -> None:
    if not sys.platform.startswith("win"):
        logger.info("this build targets Windows 10 1809 x64; running on %s for development", sys.platform)
        return
    if sys.maxsize <= 2**32:
        logger.warning("32-bit Windows is not supported")
        return
    version = sys.getwindowsversion()
    if version.major < 10 or version.build < _MIN_BUILD:
        logger.warning("Windows 10 version 1809 (build %s) or newer is required", _MIN_BUILD)
