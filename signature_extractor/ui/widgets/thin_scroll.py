"""Settings scroller: thin thumb, wheel works over every child.

CustomTkinter's scrollable frame only hears the wheel on its own canvas, and
on Windows the wheel event is delivered to the widget under the pointer.
Binding every descendant, and reading ``delta`` in steps of 120, is what
makes the page move when the pointer is over a card.
"""

from __future__ import annotations

import sys
import tkinter as tk

import customtkinter as ctk

from signature_extractor.ui.theme import current_palette, pair


def wheel_steps(delta: int, number: int | None = None) -> int:
    """Pixels to scroll. Windows reports notches as multiples of 120."""
    if number == 4:
        return -48
    if number == 5:
        return 48
    if delta:
        return -int(delta / 120) * 48
    return 0


class ThinScroll(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=pair("bg"), bg_color=pair("bg"))
        palette = current_palette()
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=palette.bg, yscrollincrement=1)
        self.canvas.pack(fill="both", expand=True)
        # A transparent frame over a Tk canvas resolves to white. Paint the
        # window colour explicitly so dark mode stays #202020.
        self.content = ctk.CTkFrame(self.canvas, fg_color=pair("bg"), bg_color=pair("bg"))
        self._window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.bar = tk.Canvas(self, width=12, highlightthickness=0, bd=0, bg=palette.bg, cursor="arrow")
        self._thumb_px = 2
        self._thumb_target = 2
        self._anim: str | None = None
        self.bar.bind("<Enter>", lambda _event: self._aim(6))
        self.bar.bind("<Leave>", lambda _event: self._aim(2))
        self.bar.bind("<Button-1>", self._on_bar_click)
        self.content.bind("<Configure>", self._on_content)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind("<MouseWheel>", self._on_wheel, add="+")
        self.canvas.bind("<Button-4>", self._on_wheel, add="+")
        self.canvas.bind("<Button-5>", self._on_wheel, add="+")
        self._bound: set[int] = set()
        self._watch_job: str | None = None
        self._watch()

    def apply_colors(self) -> None:
        palette = current_palette()
        self.configure(fg_color=pair("bg"))
        self.canvas.configure(bg=palette.bg)
        self.bar.configure(bg=palette.bg)
        self.content.configure(fg_color=pair("bg"), bg_color=pair("bg"))
        self._place_thumb()

    def _watch(self) -> None:
        """New widgets (and the first build) need the wheel binding too."""
        self._bind_tree(self.content)
        self._place_thumb()
        try:
            self._watch_job = self.after(400, self._watch)
        except tk.TclError:
            self._watch_job = None

    def _bind_tree(self, widget: tk.Misc) -> None:
        ident = id(widget)
        if ident not in self._bound:
            self._bound.add(ident)
            widget.bind("<MouseWheel>", self._on_wheel, add="+")
            widget.bind("<Button-4>", self._on_wheel, add="+")
            widget.bind("<Button-5>", self._on_wheel, add="+")
        for child in widget.winfo_children():
            self._bind_tree(child)

    def _on_wheel(self, event: tk.Event) -> str | None:
        if not self._contains(event.widget):
            return None
        steps = wheel_steps(int(getattr(event, "delta", 0) or 0), getattr(event, "num", None))
        if steps:
            # yscrollincrement is 1, so a unit is one pixel.
            self.canvas.yview_scroll(steps, "units")
            self._place_thumb()
        return "break"

    def _contains(self, widget: tk.Misc | None) -> bool:
        current = widget
        while current is not None:
            if current is self or current is self.canvas or current is self.content or current is self.bar:
                return True
            current = getattr(current, "master", None)
        return False

    def _on_content(self, _event: tk.Event | None = None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all") or (0, 0, 0, 0))
        self._place_thumb()

    def _on_canvas(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)
        self._place_thumb()

    def _place_thumb(self) -> None:
        try:
            view_h = self.canvas.winfo_height()
            bbox = self.canvas.bbox(self._window)
        except tk.TclError:
            return
        if view_h <= 1 or not bbox:
            self.bar.place_forget()
            return
        content_h = max(bbox[3] - bbox[1], 1)
        if content_h <= view_h + 1:
            self.bar.place_forget()
            return
        first, last = self.canvas.yview()
        span = max(last - first, 0.05)
        inset = 8
        track_h = max(view_h - inset * 2, 1)
        thumb_h = max(28, int(track_h * span))
        thumb_h = min(thumb_h, max(track_h - 4, 8))
        travel = max(track_h - thumb_h, 1)
        thumb_y = int(first / max(1 - span, 0.001) * travel) if last < 0.999 else track_h - thumb_h
        thumb_y = max(0, min(thumb_y, track_h - thumb_h))
        palette = current_palette()
        self.bar.configure(bg=palette.bg)
        self.bar.place(relx=1.0, y=inset, anchor="ne", width=12, height=track_h)
        self.bar.delete("all")
        # Resting thumb is a 2 px line, 5 px from the window edge. Hover grows it to 6 px.
        color = "#8A8A8A" if palette.bg.upper() == "#F3F3F3" else "#9D9D9D"
        width = max(2, min(6, int(self._thumb_px)))
        x1 = 12 - 5
        x0 = x1 - width
        y0, y1 = thumb_y, thumb_y + thumb_h
        if width >= 5:
            self._arrow(6, 4, up=True, color=color)
            self._arrow(6, track_h - 4, up=False, color=color)
            y0 = max(y0, 14)
            y1 = min(y1, track_h - 14)
        radius = max(1, width // 2)
        if y1 - y0 <= radius * 2:
            self.bar.create_oval(x0, y0, x1, max(y1, y0 + 2), fill=color, outline=color)
            return
        self.bar.create_rectangle(x0, y0 + radius, x1, y1 - radius, fill=color, outline=color)
        self.bar.create_oval(x0, y0, x1, y0 + radius * 2, fill=color, outline=color)
        self.bar.create_oval(x0, y1 - radius * 2, x1, y1, fill=color, outline=color)

    def _arrow(self, x: int, y: int, up: bool, color: str) -> None:
        if up:
            self.bar.create_polygon(x - 3, y + 2, x + 3, y + 2, x, y - 2, fill=color, outline=color)
        else:
            self.bar.create_polygon(x - 3, y - 2, x + 3, y - 2, x, y + 2, fill=color, outline=color)

    def _aim(self, target: int) -> None:
        self._thumb_target = target
        if self._anim is not None:
            try:
                self.after_cancel(self._anim)
            except tk.TclError:
                pass
            self._anim = None
        self._step_thumb()

    def _step_thumb(self) -> None:
        self._anim = None
        if self._thumb_px == self._thumb_target:
            self._place_thumb()
            return
        self._thumb_px += 1 if self._thumb_target > self._thumb_px else -1
        self._place_thumb()
        try:
            self._anim = self.after(16, self._step_thumb)
        except tk.TclError:
            self._anim = None

    def _on_bar_click(self, event: tk.Event) -> None:
        if self._thumb_px < 5:
            return
        height = self.bar.winfo_height()
        if event.y < 16:
            self.canvas.yview_scroll(-48, "units")
        elif event.y > height - 16:
            self.canvas.yview_scroll(48, "units")
        self._place_thumb()
