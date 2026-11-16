"""UI font. Segoe UI on Windows, Inter or Roboto elsewhere."""

from __future__ import annotations

import sys
import tkinter
import tkinter.font as tkfont

import customtkinter as ctk

_FAMILY: str | None = None


def family() -> str:
    global _FAMILY
    if _FAMILY is None:
        try:
            names = set(tkfont.families())
        except tkinter.TclError:
            names = set()
        if sys.platform.startswith("win"):
            preferred = ["Segoe UI", "Inter", "Roboto"]
        else:
            preferred = ["Inter", "Segoe UI", "Roboto", "Noto Sans"]
        _FAMILY = next((name for name in preferred if name in names), "Roboto")
    return _FAMILY


def _families() -> set[str]:
    try:
        return set(tkfont.families())
    except tkinter.TclError:
        return set()


def semibold(size: int) -> ctk.CTkFont:
    """Segoe UI Semibold (Windows) rather than the heavier Bold weight."""
    names = _families()
    for candidate in ("Segoe UI Semibold", "Segoe UI SemiBold", "Inter Semi Bold", "Inter Medium"):
        if candidate in names:
            return ctk.CTkFont(family=candidate, size=size, weight="normal")
    return ctk.CTkFont(family=family(), size=size, weight="normal")


def medium(size: int) -> ctk.CTkFont:
    """Weight 500. Tk has no 500, so this uses a Medium face when one is installed."""
    names = _families()
    for candidate in ("Inter Medium", "Segoe UI Variable Text", "Segoe UI Variable"):
        if candidate in names:
            return ctk.CTkFont(family=candidate, size=size, weight="normal")
    return ctk.CTkFont(family=family(), size=size, weight="normal")


def ui_font(size: int, weight: str = "normal") -> ctk.CTkFont:
    if weight == "bold":
        return semibold(size)
    if weight == "medium":
        return medium(size)
    return ctk.CTkFont(family=family(), size=size, weight="normal")


def ui_scale(widget) -> float:
    """Pixels per logical pixel. 1 at 100 %, about 1.25 or 1.5 when Windows scales."""
    try:
        return max(float(widget.winfo_fpixels("1i")) / 96.0, 1.0)
    except tkinter.TclError:
        return 1.0


def text_width(size: int, text: str, weight: str = "normal") -> int:
    try:
        measured = tkfont.Font(family=family(), size=size, weight=weight)
        return int(measured.measure(text))
    except tkinter.TclError:
        return max(80, len(text) * size)


def logical_text_width(widget, size: int, text: str, weight: str = "normal") -> int:
    """Text width in the same logical pixels CustomTkinter uses for widget width.

    On a DPI-aware Windows process, Tk measures fonts in physical pixels while
    CTk multiplies a logical width by the same scale. Dividing keeps a button
    from growing twice.
    """
    return max(1, int(round(text_width(size, text, weight) / ui_scale(widget))))
