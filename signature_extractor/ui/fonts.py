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


def ui_font(size: int, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=family(), size=size, weight=weight)


def text_width(size: int, text: str, weight: str = "normal") -> int:
    try:
        measured = tkfont.Font(family=family(), size=size, weight=weight)
        return int(measured.measure(text))
    except tkinter.TclError:
        return max(80, len(text) * size)
