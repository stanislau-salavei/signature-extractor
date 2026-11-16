"""Buttons, fields and toggles whose edges follow the measured spec.

CustomTkinter paints one border colour. The spec uses a darker bottom edge,
so these widgets draw that edge after the normal rounded border.
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from signature_extractor.ui.fonts import ui_font, ui_scale
from signature_extractor.ui.theme import current_palette, pair


class EdgedButton(ctk.CTkButton):
    def __init__(self, *args, bottom_color=None, **kwargs):
        self._bottom_color = bottom_color
        super().__init__(*args, **kwargs)

    def _draw(self, no_color_updates: bool = False) -> None:
        super()._draw(no_color_updates=no_color_updates)
        self._paint_bottom()

    def _paint_bottom(self) -> None:
        if not self._bottom_color:
            return
        canvas = self._canvas
        canvas.delete("bottomedge")
        try:
            width = int(canvas.winfo_width())
            height = int(canvas.winfo_height())
        except Exception:
            return
        if width < 8:
            width = int(float(canvas.cget("width")))
        if height < 8:
            height = int(float(canvas.cget("height")))
        color = self._apply_appearance_mode(self._bottom_color)
        inset = max(3, int(self._apply_widget_scaling(self._corner_radius)))
        canvas.create_line(inset, height - 1, width - inset, height - 1, fill=color, width=1, tags="bottomedge")


class EdgedEntry(ctk.CTkEntry):
    def __init__(self, *args, bottom_color=None, **kwargs):
        self._bottom_color = bottom_color
        super().__init__(*args, **kwargs)

    def _draw(self, no_color_updates: bool = False) -> None:
        super()._draw(no_color_updates=no_color_updates)
        if not self._bottom_color:
            return
        canvas = self._canvas
        canvas.delete("bottomedge")
        try:
            width = int(float(canvas.cget("width")))
            height = int(float(canvas.cget("height")))
        except Exception:
            return
        focused = False
        try:
            focused = self.focus_get() is getattr(self, "_entry", None)
        except Exception:
            focused = False
        if focused:
            accent = self._apply_appearance_mode(pair("accent"))
            self._canvas.itemconfig("border_parts", outline=accent, fill=accent)
            color = accent
            stroke = 2
        else:
            color = self._apply_appearance_mode(self._bottom_color)
            stroke = 1
        inset = max(3, int(self._apply_widget_scaling(self._corner_radius)))
        canvas.create_line(inset, height - stroke, width - inset, height - stroke, fill=color, width=stroke, tags="bottomedge")
        entry = getattr(self, "_entry", None)
        if entry is not None and not getattr(self, "_focus_bound", False):
            entry.bind("<FocusIn>", lambda _event: self._draw(), add="+")
            entry.bind("<FocusOut>", lambda _event: self._draw(), add="+")
            self._focus_bound = True


class Toggle(tk.Canvas):
    """40×20 switch. The knob is a real oval, so it stays round."""

    def __init__(self, master, command=None):
        super().__init__(master, width=40, height=20, highlightthickness=0, bd=0)
        self._on = False
        self._command = command
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._click)
        self._paint()

    def get(self) -> int:
        return 1 if self._on else 0

    def select(self) -> None:
        self._on = True
        self._paint()

    def deselect(self) -> None:
        self._on = False
        self._paint()

    def _click(self, _event=None) -> None:
        self._on = not self._on
        self._paint()
        if self._command is not None:
            self._command()

    def _paint(self) -> None:
        palette = current_palette()
        scale = ui_scale(self)

        def px(value: float) -> int:
            return max(1, int(round(value * scale)))

        width, height = px(40), px(20)
        self.configure(width=width, height=height, bg=palette.card)
        self.delete("all")
        if self._on:
            fill, stroke, knob, left = palette.accent, palette.accent, palette.on_accent, px(22)
        else:
            fill, stroke, knob, left = palette.toggle_off, palette.toggle_stroke, palette.toggle_knob, px(4)
        _pill(self, 1, 1, width - 1, height - 1, fill, stroke)
        top = px(3)
        knob_size = px(12)
        self.create_oval(left, top, left + knob_size, top + knob_size, fill=knob, outline=knob, width=1)


def _pill(canvas, x1, y1, x2, y2, fill, stroke) -> None:
    radius = max(1, (y2 - y1) // 2)
    canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline=fill)
    canvas.create_oval(x1, y1, x1 + 2 * radius, y2, fill=fill, outline=stroke, width=1)
    canvas.create_oval(x2 - 2 * radius, y1, x2, y2, fill=fill, outline=stroke, width=1)
    canvas.create_line(x1 + radius, y1, x2 - radius, y1, fill=stroke)
    canvas.create_line(x1 + radius, y2, x2 - radius, y2, fill=stroke)


class Mark(tk.Canvas):
    """Radio dot or checkbox drawn as geometry, not a CTk rounded rect."""

    def __init__(self, master, kind: str = "radio"):
        super().__init__(master, width=16, height=16, highlightthickness=0, bd=0)
        self.kind = kind
        self._on = False
        self._paint()

    def set(self, on: bool) -> None:
        self._on = bool(on)
        self._paint()

    def _paint(self) -> None:
        palette = current_palette()
        self.configure(bg=palette.card)
        self.delete("all")
        color = palette.accent if self._on else palette.dim
        if self.kind == "radio":
            self.create_oval(1, 1, 15, 15, outline=color, width=1)
            if self._on:
                self.create_oval(4, 4, 12, 12, fill=palette.accent, outline=palette.accent)
            return
        self.create_rectangle(1, 1, 15, 15, outline=color, width=1)
        if self._on:
            self.create_line(3, 8, 6, 12, 12, 4, fill=palette.accent, width=2, smooth=False)


class SuffixedField(ctk.CTkFrame):
    """Number field with a unit the user cannot delete. Bottom edge is 1 px, 2 px accent when focused."""

    def __init__(self, master):
        super().__init__(
            master,
            width=72,
            height=32,
            corner_radius=4,
            fg_color=pair("input_bg"),
            border_color=pair("ctl_stroke"),
            border_width=1,
        )
        self.pack_propagate(False)
        self.entry = ctk.CTkEntry(
            self,
            width=36,
            height=26,
            border_width=0,
            fg_color=pair("input_bg"),
            font=ui_font(14),
            justify="right",
            text_color=pair("text"),
        )
        self.entry.pack(side="left", padx=(6, 0), pady=2)
        self.suffix = ctk.CTkLabel(self, text="", font=ui_font(14), text_color=pair("text"))
        self.suffix.pack(side="left", padx=(1, 6))
        self._edge = ctk.CTkFrame(self, height=1, fg_color=pair("input_bottom"), corner_radius=0)
        self._edge.place(relx=0, rely=1.0, relwidth=1, anchor="sw", y=-1)
        self.entry.bind("<FocusIn>", lambda _event: self._focus(True))
        self.entry.bind("<FocusOut>", lambda _event: self._focus(False))
        self.entry.bind("<KeyRelease>", self._keep_number)

    def _keep_number(self, _event=None) -> None:
        value = self.entry.get()
        cleaned = "".join(ch for ch in value if ch.isdigit() or ch in ",.")
        if cleaned != value:
            self.entry.delete(0, "end")
            self.entry.insert(0, cleaned)

    def _focus(self, on: bool) -> None:
        if on:
            self.configure(border_color=pair("accent"), border_width=2)
            self._edge.configure(fg_color=pair("accent"), height=2)
        else:
            self.configure(border_color=pair("ctl_stroke"), border_width=1)
            self._edge.configure(fg_color=pair("input_bottom"), height=1)
