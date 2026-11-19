"""Remark 80: Ctrl shortcuts by the physical key, so they work with any keyboard layout.

Tk names the key by the character of the current layout: with the Russian layout Ctrl+O arrives as
``Cyrillic_shcha`` and a ``<Control-o>`` binding never fires.  The key code does not depend on the layout
(Windows: the virtual-key code, VK_A…VK_Z = 65…90; X11: the hardware code of the key), so the Latin
letter is taken from the key symbol when it is Latin and from the key code otherwise."""
from __future__ import annotations

import logging
import string
import tkinter as tk
from typing import Optional

from ui.widgets.overlay import MenuPopup, Popup

log = logging.getLogger(__name__)

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


class KeysMixin:
    """Remark 112 (audit B3): the keyboard of the main window (``ui.app.App``)."""

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
        try:
            ws = self.root.tk.call("tk", "windowingsystem")
        except tk.TclError:
            log.debug("windowingsystem unknown", exc_info=True)
            ws = ""
        letter = latin_letter(str(e.keysym), int(e.keycode or 0), ws)
        if letter is None:
            return None
        shift = bool(int(e.state or 0) & SHIFT)
        focus = self.root.focus_get()
        if isinstance(focus, tk.Entry) and not is_latin_keysym(str(e.keysym)) and letter in ENTRY_EVENTS:
            focus.event_generate(ENTRY_EVENTS[letter])
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
