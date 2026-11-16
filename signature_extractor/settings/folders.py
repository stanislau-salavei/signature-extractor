"""Default save folder: the user's Documents plus the localized folder name."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def documents_dir() -> Path:
    """The real Documents folder, not a hard-coded English path."""
    if sys.platform.startswith("win"):
        windows = _windows_documents()
        if windows is not None:
            return windows
    xdg = os.environ.get("XDG_DOCUMENTS_DIR")
    if xdg:
        return Path(xdg)
    return Path.home() / "Documents"


def default_save_folder(folder_name: str) -> Path:
    """``Documents\\Подписи`` or ``Documents\\Signatures``.

    ``folder_name`` comes from the string ``export.default_folder``. An
    existing folder the user already chose is not renamed when the language
    changes; callers pass that stored path instead of this default.
    """
    return documents_dir() / folder_name


def _windows_documents() -> Path | None:
    try:
        import ctypes
        from ctypes import wintypes
        import uuid

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8),
            ]

        # FOLDERID_Documents
        parsed = uuid.UUID("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}")
        guid = GUID.from_buffer_copy(parsed.bytes_le)
        path_ptr = ctypes.c_wchar_p()
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid),
            0,
            None,
            ctypes.byref(path_ptr),
        )
        if result != 0 or not path_ptr.value:
            return None
        return Path(path_ptr.value)
    except (AttributeError, OSError, ValueError):
        logger.warning("could not resolve the Documents folder", exc_info=True)
        return None
