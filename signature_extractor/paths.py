"""Filesystem locations for resources, settings, and the future installer."""

from __future__ import annotations

import sys
from pathlib import Path

APP_DIR_NAME = "Signature Extractor"
SETTINGS_FILE_NAME = "settings.json"
INSTALLER_LANGUAGE_FILE_NAME = "installer_language.txt"


def package_dir() -> Path:
    """Directory that contains this package (or the PyInstaller bundle)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def install_dir() -> Path:
    """Directory the installer owns.

    A PyInstaller build uses the folder that contains the executable
    (``%LOCALAPPDATA%\\Programs\\Signature Extractor`` in stage 6).
    A source checkout uses the repository root, so ``installer_language.txt``
    and ``LICENSE`` can sit beside the project during development.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    return package_dir().joinpath(*parts)


def strings_csv_path() -> Path:
    return resource_path("i18n", "strings_ru_en.csv")


def app_icon_path() -> Path:
    return resource_path("assets", "app.ico")


def license_path() -> Path | None:
    """GPL text shipped with the app, if it can be found."""
    candidates = (
        install_dir() / "LICENSE",
        package_dir().parent / "LICENSE",
        Path.cwd() / "LICENSE",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def settings_directory() -> Path:
    """``%APPDATA%\\Signature Extractor``.

    On Windows ``APPDATA`` is set by the system. Tests and the Linux
    verification run set ``APPDATA`` themselves. If it is missing, the same
    folder name is created under the user's home directory so a settings
    file still has a stable path.
    """
    appdata = _appdata_root()
    return appdata / APP_DIR_NAME


def settings_path() -> Path:
    return settings_directory() / SETTINGS_FILE_NAME


def _appdata_root() -> Path:
    import os

    raw = os.environ.get("APPDATA")
    if raw:
        return Path(raw)
    return Path.home() / "AppData" / "Roaming"
