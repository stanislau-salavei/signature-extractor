"""Small hover tooltip. The text is read again on each show so language switches apply."""

from __future__ import annotations

from collections.abc import Callable

import tkinter as tk

from signature_extractor.ui.theme import current_palette


class Tooltip:
    def __init__(self, widget: tk.Widget, text_of: Callable[[], str]):
        self.widget = widget
        self.text_of = text_of
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, _event: tk.Event | None = None) -> None:
        text = self.text_of()
        if not text:
            return
        self._hide()
        palette = current_palette()
        tip = tk.Toplevel(self.widget)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        label = tk.Label(
            tip,
            text=text,
            bg=palette.menu_bg,
            fg=palette.text,
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=4,
            font=("Segoe UI", 9) if _font_exists("Segoe UI") else ("Inter", 9),
        )
        label.pack()
        tip.update_idletasks()
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        tip.geometry(f"+{x}+{y}")
        self._tip = tip

    def _hide(self, _event: tk.Event | None = None) -> None:
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None


def _font_exists(name: str) -> bool:
    try:
        import tkinter.font as tkfont

        return name in set(tkfont.families())
    except tk.TclError:
        return False
