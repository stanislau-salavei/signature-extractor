"""Map the Windows UI language onto the two languages this app ships."""

from __future__ import annotations

import locale
import logging
import os
import sys

logger = logging.getLogger(__name__)

# Win32 LANG_RUSSIAN primary language id.
_LANG_RUSSIAN = 0x19


def system_language() -> str:
    """``ru`` when the UI language is Russian, otherwise ``en``.

    The installer uses the same rule: Russian Windows selects Russian, every
    other language selects English, because those are the only two catalogs.
    """
    if sys.platform.startswith("win"):
        detected = _windows_ui_language()
        if detected:
            return detected
    for candidate in (
        _locale_name(),
        os.environ.get("LC_ALL", ""),
        os.environ.get("LC_MESSAGES", ""),
        os.environ.get("LANG", ""),
    ):
        if candidate.lower().replace("-", "_").startswith("ru"):
            return "ru"
    return "en"


def _windows_ui_language() -> str | None:
    try:
        import ctypes

        lang_id = int(ctypes.windll.kernel32.GetUserDefaultUILanguage())
    except (AttributeError, OSError, ValueError):
        logger.warning("could not read the Windows UI language", exc_info=True)
        return None
    if (lang_id & 0x3FF) == _LANG_RUSSIAN:
        return "ru"
    return "en"


def _locale_name() -> str:
    try:
        name = locale.getlocale()[0] or ""
    except (TypeError, ValueError):
        name = ""
    if name:
        return name
    try:
        return locale.getdefaultlocale()[0] or ""  # type: ignore[deprecated]
    except (TypeError, ValueError):
        return ""
