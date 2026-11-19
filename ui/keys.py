"""Remark 80: Ctrl shortcuts by the physical key, so they work with any keyboard layout.

Tk names the key by the character of the current layout: with the Russian layout Ctrl+O arrives as
``Cyrillic_shcha`` and a ``<Control-o>`` binding never fires.  The key code does not depend on the layout
(Windows: the virtual-key code, VK_A…VK_Z = 65…90; X11: the hardware code of the key), so the Latin
letter is taken from the key symbol when it is Latin and from the key code otherwise."""
from __future__ import annotations

import string
from typing import Optional

_X11 = dict(zip("qwertyuiop", range(24, 34), strict=True))
_X11.update(zip("asdfghjkl", range(38, 47), strict=True))
_X11.update(zip("zxcvbnm", range(52, 59), strict=True))

KEYCODES = {
    "win32": {65 + i: c for i, c in enumerate(string.ascii_lowercase)},     # VK_A … VK_Z
    "x11": {code: c for c, code in _X11.items()},                          # evdev / xfree86 key codes
}

SHIFT = 0x0001


def latin_letter(keysym: str, keycode: int, windowing: str) -> Optional[str]:
    """The Latin letter of the pressed key (lower case) or None for other keys."""
    if len(keysym) == 1 and keysym.lower() in string.ascii_lowercase:
        return keysym.lower()
    return KEYCODES.get(windowing, {}).get(keycode)


def is_latin_keysym(keysym: str) -> bool:
    return len(keysym) == 1 and keysym.lower() in string.ascii_lowercase


# text fields: the standard editing shortcuts as Tk virtual events (Tk itself binds them to Latin keysyms only)
ENTRY_EVENTS = {"a": "<<SelectAll>>", "c": "<<Copy>>", "v": "<<Paste>>", "x": "<<Cut>>", "z": "<<Undo>>",
                "y": "<<Redo>>"}
