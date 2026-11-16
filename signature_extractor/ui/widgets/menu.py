"""The ⋯ menu. Five items, in the approved order."""

from __future__ import annotations

from collections.abc import Callable

import tkinter as tk

from signature_extractor.ui.theme import current_palette


class OverflowMenu:
    """Floating menu under the ⋯ button. Not a separate top-level document window."""

    def __init__(self, master: tk.Misc):
        self.master = master
        self._popup: tk.Toplevel | None = None
        self._commands: list[tuple[str, object, Callable[[], None]]] = []

    def set_items(self, items: list[tuple[str, object, Callable[[], None]]]) -> None:
        """``items`` is ``(label, image, command)`` in menu order, with a separator after the second."""
        self._commands = items
        if self.is_open():
            self.hide()

    def is_open(self) -> bool:
        return self._popup is not None and self._popup.winfo_exists()

    def toggle(self, anchor: tk.Widget) -> None:
        if self.is_open():
            self.hide()
        else:
            self.show(anchor)

    def show(self, anchor: tk.Widget) -> None:
        self.hide()
        palette = current_palette()
        popup = tk.Toplevel(self.master)
        popup.overrideredirect(True)
        popup.transient(self.master.winfo_toplevel())
        popup.configure(bg=palette.menu_border)
        body = tk.Frame(popup, bg=palette.menu_bg, highlightthickness=0)
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
        popup.update_idletasks()
        x = anchor.winfo_rootx() + anchor.winfo_width() - popup.winfo_reqwidth()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 4
        popup.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        popup.bind("<Escape>", lambda _event: self.hide())
        self._popup = popup
        # Close on the next click anywhere outside the menu.
        # bind (not bind_all) so CustomTkinter's own click handler stays in place.
        self._outside_bind = self.master.bind("<Button-1>", self._click_outside, add="+")

    def hide(self) -> None:
        bind_id = getattr(self, "_outside_bind", None)
        if bind_id is not None:
            try:
                self.master.unbind("<Button-1>", bind_id)
            except tk.TclError:
                pass
            self._outside_bind = None
        if self._popup is not None:
            try:
                self._popup.destroy()
            except tk.TclError:
                pass
            self._popup = None

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

    def _click_outside(self, event: tk.Event) -> None:
        if self._popup is None:
            return
        widget = event.widget
        while widget is not None:
            if widget is self._popup:
                return
            widget = getattr(widget, "master", None)
        self.hide()


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
