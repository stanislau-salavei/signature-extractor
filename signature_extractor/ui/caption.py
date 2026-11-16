"""Windows 11 caption colour. Matches the page background, like Windows Terminal.

``DWMWA_CAPTION_COLOR`` exists only on Windows 11. Windows 10 and other
systems skip this quietly.
"""

from __future__ import annotations

import sys


def apply_titlebar(widget) -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        if sys.getwindowsversion().build < 22000:
            return
    except Exception:
        return
    try:
        import ctypes

        from signature_extractor.ui.theme import current_palette

        user = ctypes.windll.user32
        hwnd = user.GetParent(int(widget.winfo_id())) or int(widget.winfo_id())
        palette = current_palette()
        dark = 1 if palette.bg == "#202020" else 0
        _set_dword(hwnd, 20, dark)
        _set_dword(hwnd, 35, _colorref(palette.bg))
        _set_dword(hwnd, 36, _colorref(palette.text))
    except Exception:
        return


def _colorref(hex_color: str) -> int:
    text = hex_color.lstrip("#")
    red = int(text[0:2], 16)
    green = int(text[2:4], 16)
    blue = int(text[4:6], 16)
    return red | (green << 8) | (blue << 16)


def _set_dword(hwnd: int, attribute: int, value: int) -> None:
    import ctypes

    packed = ctypes.c_uint(value)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(
        hwnd,
        attribute,
        ctypes.byref(packed),
        ctypes.sizeof(packed),
    )
