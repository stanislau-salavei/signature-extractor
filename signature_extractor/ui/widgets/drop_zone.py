"""Dashed drop zone for screen 1. No file is opened from a drop in stage 1."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from signature_extractor.ui.theme import current_palette, pair


class DropZone(ctk.CTkFrame):
    """Large dashed target. Drag-and-drop is connected in stage 2."""

    def __init__(self, master):
        super().__init__(master, fg_color=pair("drop"), corner_radius=8)
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self._canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.inner = ctk.CTkFrame(self, fg_color="transparent")
        self.inner.place(relx=0.5, rely=0.5, anchor="center")
        self.bind("<Configure>", self._redraw)
        self._redraw()

    def _redraw(self, _event: tk.Event | None = None) -> None:
        palette = current_palette()
        canvas = self._canvas
        canvas.configure(bg=palette.drop)
        canvas.delete("all")
        width = max(self.winfo_width(), 2)
        height = max(self.winfo_height(), 2)
        inset = 2
        radius = 10
        color = palette.drop_border
        x1, y1 = inset, inset
        x2, y2 = width - inset, height - inset
        dash = (7, 5)
        canvas.create_line(x1 + radius, y1, x2 - radius, y1, fill=color, width=2, dash=dash)
        canvas.create_line(x2, y1 + radius, x2, y2 - radius, fill=color, width=2, dash=dash)
        canvas.create_line(x2 - radius, y2, x1 + radius, y2, fill=color, width=2, dash=dash)
        canvas.create_line(x1, y2 - radius, x1, y1 + radius, fill=color, width=2, dash=dash)
        canvas.create_arc(x2 - 2 * radius, y1, x2, y1 + 2 * radius, start=0, extent=90, style="arc", outline=color, width=2, dash=dash)
        canvas.create_arc(x1, y1, x1 + 2 * radius, y1 + 2 * radius, start=90, extent=90, style="arc", outline=color, width=2, dash=dash)
        canvas.create_arc(x1, y2 - 2 * radius, x1 + 2 * radius, y2, start=180, extent=90, style="arc", outline=color, width=2, dash=dash)
        canvas.create_arc(x2 - 2 * radius, y2 - 2 * radius, x2, y2, start=270, extent=90, style="arc", outline=color, width=2, dash=dash)
