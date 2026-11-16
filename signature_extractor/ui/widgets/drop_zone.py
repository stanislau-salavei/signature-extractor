"""Dashed drop zone for screen 1. No file is opened from a drop in stage 1."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from signature_extractor.ui.theme import Palette, current_palette, pair

_RADIUS = 12


class DropZone(ctk.CTkFrame):
    """Large dashed target. Drag-and-drop is connected in stage 2.

    The dashed outline is a Tk canvas, which is always a rectangle. Its
    background is the window colour, and the card fill is a rounded
    rectangle, so the corners outside that shape match the window
    (``#F3F3F3`` / ``#202020``) instead of a white square.
    """

    def __init__(self, master):
        super().__init__(master, fg_color=pair("bg"), corner_radius=_RADIUS)
        palette = current_palette()
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=palette.bg)
        self._canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.inner = ctk.CTkFrame(self, fg_color=pair("drop"), bg_color=pair("drop"))
        self.inner.place(relx=0.5, rely=0.5, anchor="center")
        self._drawn: tuple | None = None
        self.bind("<Configure>", self._redraw)
        self._redraw()

    def _redraw(self, _event: tk.Event | None = None) -> None:
        palette = current_palette()
        width = max(self.winfo_width(), 2)
        height = max(self.winfo_height(), 2)
        key = (width, height, palette.bg, palette.drop, palette.drop_border)
        if key == self._drawn:
            return
        self._drawn = key
        canvas = self._canvas
        canvas.configure(bg=palette.bg)
        canvas.delete("all")
        inset = 2
        _fill_round_rect(
            canvas,
            inset,
            inset,
            width - inset,
            height - inset,
            _RADIUS,
            palette.drop,
        )
        _stroke_round_rect(
            canvas,
            inset,
            inset,
            width - inset,
            height - inset,
            _RADIUS,
            palette.drop_border,
        )


def _fill_round_rect(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    radius: int,
    color: str,
) -> None:
    radius = min(radius, max(0, (x2 - x1) // 2), max(0, (y2 - y1) // 2))
    canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=color, outline=color, width=0)
    canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=color, outline=color, width=0)
    _corner(canvas, x1, y1, radius, 90, color, filled=True)
    _corner(canvas, x2 - 2 * radius, y1, radius, 0, color, filled=True)
    _corner(canvas, x1, y2 - 2 * radius, radius, 180, color, filled=True)
    _corner(canvas, x2 - 2 * radius, y2 - 2 * radius, radius, 270, color, filled=True)


def _stroke_round_rect(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    radius: int,
    color: str,
) -> None:
    radius = min(radius, max(0, (x2 - x1) // 2), max(0, (y2 - y1) // 2))
    dash = (7, 5)
    canvas.create_line(x1 + radius, y1, x2 - radius, y1, fill=color, width=2, dash=dash)
    canvas.create_line(x2, y1 + radius, x2, y2 - radius, fill=color, width=2, dash=dash)
    canvas.create_line(x2 - radius, y2, x1 + radius, y2, fill=color, width=2, dash=dash)
    canvas.create_line(x1, y2 - radius, x1, y1 + radius, fill=color, width=2, dash=dash)
    _corner(canvas, x1, y1, radius, 90, color, filled=False)
    _corner(canvas, x2 - 2 * radius, y1, radius, 0, color, filled=False)
    _corner(canvas, x1, y2 - 2 * radius, radius, 180, color, filled=False)
    _corner(canvas, x2 - 2 * radius, y2 - 2 * radius, radius, 270, color, filled=False)


def _corner(
    canvas: tk.Canvas,
    x: int,
    y: int,
    radius: int,
    start: int,
    color: str,
    *,
    filled: bool,
) -> None:
    box = (x, y, x + 2 * radius, y + 2 * radius)
    if filled:
        canvas.create_arc(box, start=start, extent=90, fill=color, outline=color)
    else:
        canvas.create_arc(
            box,
            start=start,
            extent=90,
            style="arc",
            outline=color,
            width=2,
            dash=(7, 5),
        )


def canvas_colors(palette: Palette) -> tuple[str, str]:
    """Window colour outside the curve, card colour inside it."""
    return palette.bg, palette.drop
