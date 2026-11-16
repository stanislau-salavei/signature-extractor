"""The ⋯ menu. Five items, in the approved order."""

from __future__ import annotations

from collections.abc import Callable

import tkinter as tk

from signature_extractor.ui.fonts import family, ui_scale
from signature_extractor.ui.popup import BorderlessPopup
from signature_extractor.ui.theme import current_palette

_TRANSPARENT = "#ff00ee"


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

    def show(self, anchor: tk.Widget, align_right: tk.Widget | None = None) -> None:
        # The opening click's ButtonRelease follows the Button-1 that closed
        # the menu. Swallow that release so the menu stays closed.
        if self._swallow_reopen:
            self._swallow_reopen = False
            return
        self.hide()
        palette = current_palette()
        scale = ui_scale(anchor)

        def px(value: float) -> int:
            return max(1, int(round(value * scale)))

        popup = BorderlessPopup(self.master, on_anchor_press=self._note_anchor_press)
        window = popup.window
        try:
            window.attributes("-transparentcolor", _TRANSPARENT)
            outside = _TRANSPARENT
        except tk.TclError:
            outside = palette.menu_bg
        window.configure(bg=outside)
        radius = px(8)
        margin = px(16)
        row_h = px(36)
        body_w = px(248)
        canvas = tk.Canvas(window, highlightthickness=0, bd=0, bg=outside)
        inner = tk.Frame(canvas, bg=palette.menu_bg)
        for index, (label, image, command) in enumerate(self._commands):
            if index == 2:
                sep = tk.Frame(inner, bg=palette.divider, height=1)
                sep.pack(fill="x", padx=px(8), pady=px(4))
            row = tk.Frame(inner, bg=palette.menu_bg, height=row_h)
            row.pack(fill="x")
            row.pack_propagate(False)
            if image is not None:
                icon = tk.Label(row, image=image, bg=palette.menu_bg, borderwidth=0)
                icon.image = image
                icon.pack(side="left", padx=(px(10), 0))
            text = tk.Label(
                row,
                text=label,
                bg=palette.menu_bg,
                fg=palette.text,
                font=_menu_font(px(14)),
                anchor="w",
            )
            text.pack(side="left", padx=(px(10), px(12)))

            def bind(widget: tk.Widget, cmd: Callable[[], None] = command) -> None:
                widget.bind("<Button-1>", lambda _event: self._activate(cmd))
                widget.bind("<Enter>", lambda _event, w=row: self._hover(w, True))
                widget.bind("<Leave>", lambda _event, w=row: self._hover(w, False))

            bind(row)
            for child in row.winfo_children():
                bind(child)
        inner.update_idletasks()
        inner_h = max(inner.winfo_reqheight(), 1)
        inner_w = body_w - 2 * radius
        body_h = inner_h + 2 * radius
        canvas.configure(width=body_w + margin * 2, height=body_h + margin * 2)
        canvas.pack()
        _paint_flyout(canvas, margin, margin, body_w, body_h, radius, palette.menu_bg, palette.menu_border, outside)
        canvas.create_window(margin + radius, margin + radius, window=inner, anchor="nw", width=inner_w, height=inner_h)
        self._popup = popup
        # The card, not the shadow, lines up with the drop zone. 2 px under
        # the button: the old 4 px gap sat about 8 px too low once Windows scaled it.
        popup.reveal_body(
            anchor,
            body_width=body_w,
            body_height=body_h,
            align_right=align_right,
            gap=px(2),
            margin=margin,
        )

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


def _menu_font(pixel_size: int) -> tuple[str, int]:
    # Negative size is pixels, so it matches the scaled CTk UI instead of
    # a second DPI pass on point sizes.
    return (family(), -abs(pixel_size))


def _paint_flyout(canvas, x, y, width, height, radius, fill, border, outside) -> None:
    """Rounded menu. Stacked grey plates stand in for the Win11 blur; Tk has no alpha here."""
    light = fill.upper() not in {"#2C2C2C", "#2B2B2B", "#202020"}
    layers = (("#D5D5D5", 5), ("#E6E6E6", 3), ("#F2F2F2", 1)) if light else (("#101010", 5), ("#161616", 3), ("#1C1C1C", 1))
    for shade, drop in layers:
        _round_rect(canvas, x + 1, y + drop, width, height, radius, shade)
    _round_rect(canvas, x, y, width, height, radius, fill)
    _round_rect(canvas, x, y, width, height, radius, border, outline_only=True)
    canvas.configure(bg=outside)


def _round_rect(canvas, x, y, width, height, radius, color, outline_only: bool = False) -> None:
    x2, y2 = x + width, y + height
    if outline_only:
        canvas.create_arc(x, y, x + 2 * radius, y + 2 * radius, start=90, extent=90, style="arc", outline=color, width=1)
        canvas.create_arc(x2 - 2 * radius, y, x2, y + 2 * radius, start=0, extent=90, style="arc", outline=color, width=1)
        canvas.create_arc(x, y2 - 2 * radius, x + 2 * radius, y2, start=180, extent=90, style="arc", outline=color, width=1)
        canvas.create_arc(x2 - 2 * radius, y2 - 2 * radius, x2, y2, start=270, extent=90, style="arc", outline=color, width=1)
        canvas.create_line(x + radius, y, x2 - radius, y, fill=color)
        canvas.create_line(x + radius, y2, x2 - radius, y2, fill=color)
        canvas.create_line(x, y + radius, x, y2 - radius, fill=color)
        canvas.create_line(x2, y + radius, x2, y2 - radius, fill=color)
        return
    canvas.create_rectangle(x + radius, y, x2 - radius, y2, fill=color, outline=color)
    canvas.create_rectangle(x, y + radius, x2, y2 - radius, fill=color, outline=color)
    canvas.create_arc(x, y, x + 2 * radius, y + 2 * radius, start=90, extent=90, fill=color, outline=color)
    canvas.create_arc(x2 - 2 * radius, y, x2, y + 2 * radius, start=0, extent=90, fill=color, outline=color)
    canvas.create_arc(x, y2 - 2 * radius, x + 2 * radius, y2, start=180, extent=90, fill=color, outline=color)
    canvas.create_arc(x2 - 2 * radius, y2 - 2 * radius, x2, y2, start=270, extent=90, fill=color, outline=color)
