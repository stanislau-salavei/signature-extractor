"""The ⋯ menu. Five items, in the approved order."""

from __future__ import annotations

from collections.abc import Callable

import tkinter as tk

from signature_extractor.ui.popup import BorderlessPopup
from signature_extractor.ui.theme import current_palette


class OverflowMenu:
    """Floating menu under the ⋯ button. Not a separate document window."""

    def __init__(self, master: tk.Misc):
        self.master = master
        self._popup: BorderlessPopup | None = None
        self._commands: list[tuple[str, object, Callable[[], None]]] = []
        self._swallow_reopen = False

    def set_items(self, items: list[tuple[str, object, Callable[[], None]]]) -> None:
        """``items`` is ``(label, image, command)`` in menu order, with a separator after the second."""
        self._commands = items
        if self.is_open():
            self.hide()

    def is_open(self) -> bool:
        return self._popup is not None and self._popup.is_open()

    def show(self, anchor: tk.Widget) -> None:
        # The opening click's ButtonRelease follows the Button-1 that closed
        # the menu. Swallow that release so the menu stays closed.
        if self._swallow_reopen:
            self._swallow_reopen = False
            return
        self.hide()
        palette = current_palette()
        popup = BorderlessPopup(self.master, on_anchor_press=self._note_anchor_press)
        popup.window.configure(bg=palette.menu_border)
        body = tk.Frame(popup.window, bg=palette.menu_bg, highlightthickness=0)
        body.pack(padx=1, pady=1)
        inner = tk.Frame(body, bg=palette.menu_bg)
        inner.pack(padx=6, pady=6)
        for index, (label, image, command) in enumerate(self._commands):
            if index == 2:
                sep = tk.Frame(inner, bg=palette.divider, height=1)
                sep.pack(fill="x", padx=8, pady=4)
            row = tk.Frame(inner, bg=palette.menu_bg, height=36, width=216)
            row.pack(fill="x")
            row.pack_propagate(False)
            if image is not None:
                icon = tk.Label(row, image=image, bg=palette.menu_bg, borderwidth=0)
                icon.image = image
                icon.pack(side="left", padx=(10, 0))
            text = tk.Label(
                row,
                text=label,
                bg=palette.menu_bg,
                fg=palette.text,
                font=_menu_font(),
                anchor="w",
            )
            text.pack(side="left", padx=(10, 12))

            def bind(widget: tk.Widget, cmd: Callable[[], None] = command) -> None:
                widget.bind("<Button-1>", lambda _event: self._activate(cmd))
                widget.bind("<Enter>", lambda _event, w=row: self._hover(w, True))
                widget.bind("<Leave>", lambda _event, w=row: self._hover(w, False))

            bind(row)
            for child in row.winfo_children():
                bind(child)
        self._popup = popup
        popup.reveal_under(anchor, min_width=228)

    def hide(self) -> None:
        popup = self._popup
        self._popup = None
        if popup is not None:
            popup.close()

    def _note_anchor_press(self) -> None:
        self._swallow_reopen = True

    def _activate(self, command: Callable[[], None]) -> None:
        self.hide()
        command()

    def _hover(self, row: tk.Frame, on: bool) -> None:
        palette = current_palette()
        color = palette.menu_hover if on else palette.menu_bg
        row.configure(bg=color)
        for child in row.winfo_children():
            try:
                child.configure(bg=color)
            except tk.TclError:
                pass


def _menu_font() -> tuple[str, int]:
    try:
        import tkinter.font as tkfont

        families = set(tkfont.families())
    except tk.TclError:
        families = set()
    if "Segoe UI" in families:
        return ("Segoe UI", 10)
    if "Inter" in families:
        return ("Inter", 10)
    return ("TkDefaultFont", 10)
