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
    """40×20 switch. One capsule track and one knob. The canvas matches the card."""

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
        mid = height / 2
        inset = max(1, px(1))
        # A round-capped line is one capsule. Separate end circles read as a second knob.
        self.create_line(
            height / 2,
            mid,
            width - height / 2,
            mid,
            width=height - inset,
            capstyle="round",
            fill=stroke,
        )
        self.create_line(
            height / 2,
            mid,
            width - height / 2,
            mid,
            width=max(1, height - inset * 3),
            capstyle="round",
            fill=fill,
        )
        top = px(3)
        knob_size = px(12)
        self.create_oval(left, top, left + knob_size, top + knob_size, fill=knob, outline=knob)


class Mark(tk.Canvas):
    """Win11 radio (20 px ring) or checkbox (20 px rounded square)."""

    def __init__(self, master, kind: str = "radio"):
        super().__init__(master, width=20, height=20, highlightthickness=0, bd=0)
        self.kind = kind
        self._on = False
        self._hover = False
        self.configure(cursor="hand2")
        self.bind("<Enter>", lambda _event: self._set_hover(True))
        self.bind("<Leave>", lambda _event: self._set_hover(False))
        self._paint()

    def set(self, on: bool) -> None:
        self._on = bool(on)
        self._paint()

    def _set_hover(self, on: bool) -> None:
        self._hover = on
        self._paint()

    def _paint(self) -> None:
        palette = current_palette()
        light = palette.bg.upper() == "#F3F3F3"
        self.configure(width=20, height=20, bg=palette.card)
        self.delete("all")
        if self.kind == "radio":
            self._paint_radio(palette, light)
        else:
            self._paint_check(palette, light)

    def _paint_radio(self, palette, light: bool) -> None:
        centre = "#FFFFFF" if light else palette.card
        if self._on:
            self.create_oval(1, 1, 19, 19, fill=palette.accent, outline=palette.accent)
            # 5 px accent ring, centre matches the card (white on a light card).
            self.create_oval(6, 6, 14, 14, fill=centre, outline=centre)
            return
        ring = palette.text if self._hover else ("#8A8A8A" if light else "#9A9A9A")
        fill = "#FFFFFF" if light else "#2E2E2E"
        self.create_oval(1, 1, 19, 19, fill=fill, outline=ring, width=1)

    def _paint_check(self, palette, light: bool) -> None:
        if self._on:
            _round_box(self, 1, 1, 19, 19, 4, palette.accent, palette.accent)
            self.create_line(
                4, 10, 8, 15, 16, 5,
                fill="#FFFFFF",
                width=2,
                capstyle="round",
                joinstyle="round",
            )
            return
        ring = palette.text if self._hover else ("#8A8A8A" if light else "#9A9A9A")
        fill = "#FFFFFF" if light else "#2E2E2E"
        _round_box(self, 1, 1, 19, 19, 4, fill, ring)


def _round_box(canvas, x1, y1, x2, y2, radius, fill, outline) -> None:
    canvas.create_arc(x1, y1, x1 + 2 * radius, y1 + 2 * radius, start=90, extent=90, fill=fill, outline=outline)
    canvas.create_arc(x2 - 2 * radius, y1, x2, y1 + 2 * radius, start=0, extent=90, fill=fill, outline=outline)
    canvas.create_arc(x1, y2 - 2 * radius, x1 + 2 * radius, y2, start=180, extent=90, fill=fill, outline=outline)
    canvas.create_arc(x2 - 2 * radius, y2 - 2 * radius, x2, y2, start=270, extent=90, fill=fill, outline=outline)
    canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline=fill)
    canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline=fill)
    canvas.create_line(x1 + radius, y1, x2 - radius, y1, fill=outline)
    canvas.create_line(x1 + radius, y2, x2 - radius, y2, fill=outline)
    canvas.create_line(x1, y1 + radius, x1, y2 - radius, fill=outline)
    canvas.create_line(x2, y1 + radius, x2, y2 - radius, fill=outline)


class WinField(ctk.CTkFrame):
    """Win11 text box: grey border, accent only on the bottom while focused, × to clear, ✓ to apply."""

    def __init__(self, master, width: int = 180, numeric: bool = False, on_apply=None):
        super().__init__(master, fg_color="transparent")
        self._numeric = numeric
        self._on_apply = on_apply
        self._focused = False
        self.box = ctk.CTkFrame(
            self,
            width=width,
            height=32,
            corner_radius=4,
            fg_color=pair("input_bg"),
            border_color=pair("ctl_stroke"),
            border_width=1,
        )
        self.box.pack(side="left")
        self.box.pack_propagate(False)
        self.entry = ctk.CTkEntry(
            self.box,
            height=26,
            border_width=0,
            fg_color=pair("input_bg"),
            font=ui_font(14),
            text_color=pair("text"),
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=2)
        self.clear = ctk.CTkLabel(
            self.box,
            text="×",
            width=16,
            font=ui_font(14),
            text_color=pair("muted"),
            cursor="hand2",
        )
        self.clear.bind("<Button-1>", lambda _event: self._clear())
        self._line = ctk.CTkFrame(self.box, height=2, fg_color=pair("accent"), corner_radius=0)
        self.apply = ctk.CTkButton(
            self,
            text="✓",
            width=36,
            height=32,
            corner_radius=4,
            fg_color=pair("secondary_bg"),
            hover_color=pair("secondary_hover"),
            border_color=pair("ctl_stroke"),
            border_width=1,
            text_color=pair("text"),
            font=ui_font(14),
            command=self._apply,
        )
        self.apply.pack(side="left", padx=(6, 0))
        self.entry.bind("<FocusIn>", lambda _event: self._focus(True))
        self.entry.bind("<FocusOut>", lambda _event: self.after(150, self._maybe_blur))
        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Return>", lambda _event: self._apply())

    def _inner(self):
        return getattr(self.entry, "_entry", self.entry)

    def _focus(self, on: bool) -> None:
        self._focused = on
        if on:
            self._line.place(relx=0, rely=1.0, relwidth=1, anchor="sw", y=-1)
        else:
            self._line.place_forget()
        self._sync_clear()

    def _maybe_blur(self) -> None:
        try:
            focus = self.focus_get()
        except Exception:
            focus = None
        if focus in (self.entry, self._inner(), self.clear, self.apply):
            return
        self._focus(False)

    def _sync_clear(self) -> None:
        show = self._focused and bool(self.entry.get())
        mapped = bool(self.clear.winfo_manager())
        if show and not mapped:
            # Pack the clear control before the entry so the entry does not take its space.
            self.entry.pack_forget()
            self.clear.pack(side="right", padx=(0, 6))
            self.entry.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=2)
        elif not show and mapped:
            self.clear.pack_forget()

    def _clear(self) -> None:
        self.entry.delete(0, "end")
        self.entry.focus()
        self._focus(True)

    def _on_key(self, _event=None) -> None:
        if self._numeric:
            value = self.entry.get()
            cleaned = "".join(ch for ch in value if ch.isdigit() or ch in ",.")
            if cleaned != value:
                self.entry.delete(0, "end")
                self.entry.insert(0, cleaned)
        self._sync_clear()

    def _apply(self) -> None:
        if self._on_apply is not None:
            self._on_apply()
