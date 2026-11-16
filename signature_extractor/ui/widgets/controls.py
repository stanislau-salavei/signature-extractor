"""Buttons, fields and toggles whose edges follow the measured spec.

CustomTkinter paints one border colour. The spec uses a darker bottom edge,
so these widgets draw that edge after the normal rounded border.
"""

from __future__ import annotations

import customtkinter as ctk

from signature_extractor.ui.theme import pair


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
        canvas.create_line(inset, height - 1, width - inset, height - 1, fill=color, width=2, tags="bottomedge")


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
        color = self._apply_appearance_mode(self._bottom_color)
        inset = max(3, int(self._apply_widget_scaling(self._corner_radius)))
        canvas.create_line(inset, height - 1, width - inset, height - 1, fill=color, width=2, tags="bottomedge")


class Toggle(ctk.CTkFrame):
    """40×20 switch. Knob is 12×12 at left 4 (off) or 22 (on), top 3."""

    def __init__(self, master, command=None):
        super().__init__(master, width=40, height=20, fg_color="transparent")
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._on = False
        self._command = command
        self.track = ctk.CTkFrame(
            self,
            width=40,
            height=20,
            corner_radius=10,
            border_width=1,
            fg_color=pair("toggle_off"),
            border_color=pair("toggle_stroke"),
        )
        self.track.place(x=0, y=0)
        self.track.pack_propagate(False)
        self.knob = ctk.CTkFrame(
            self,
            width=12,
            height=12,
            corner_radius=6,
            border_width=0,
            fg_color=pair("toggle_knob"),
        )
        self.knob.place(x=4, y=3)
        self.knob.pack_propagate(False)
        for widget in (self, self.track, self.knob):
            widget.bind("<Button-1>", self._click)
            widget.configure(cursor="hand2")
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
        if self._on:
            self.track.configure(fg_color=pair("accent"), border_color=pair("accent"))
            self.knob.configure(fg_color=pair("on_accent"))
            self.knob.place(x=22, y=3)
        else:
            self.track.configure(fg_color=pair("toggle_off"), border_color=pair("toggle_stroke"))
            self.knob.configure(fg_color=pair("toggle_knob"))
            self.knob.place(x=4, y=3)
