"""Rounded choice list for Settings. No grey frame around the items."""

from __future__ import annotations

from collections.abc import Callable

import tkinter as tk
import tkinter.font as tkfont

from signature_extractor.ui.fonts import family, ui_scale
from signature_extractor.ui.popup import BorderlessPopup, widget_screen_rect
from signature_extractor.ui.theme import current_palette
from signature_extractor.ui.widgets.menu import _menu_font, _paint_flyout, _round_rect

_TRANSPARENT = "#ff00ee"


class ChoiceMenu:
    def __init__(self, master: tk.Misc):
        self.master = master
        self._popup: BorderlessPopup | None = None
        self._canvas: tk.Canvas | None = None

    def is_open(self) -> bool:
        return self._popup is not None and self._popup.is_open()

    def close(self) -> None:
        popup = self._popup
        self._popup = None
        self._canvas = None
        if popup is not None:
            popup.close()

    def show(self, anchor: tk.Widget, rows: list[tuple[str, bool, Callable[[], None]]]) -> None:
        """``rows`` is ``(label, selected, command)``."""
        self.close()
        palette = current_palette()
        scale = ui_scale(anchor)

        def px(value: float) -> int:
            return max(1, int(round(value * scale)))

        popup = BorderlessPopup(self.master)
        window = popup.window
        try:
            window.attributes("-transparentcolor", _TRANSPARENT)
            outside = _TRANSPARENT
        except tk.TclError:
            outside = palette.menu_bg
        window.configure(bg=outside)

        row_h = px(32)
        edge = px(4)
        measure = tkfont.Font(family=family(), size=-px(14))
        text_w = max((measure.measure(label) for label, _selected, _command in rows), default=px(80))
        try:
            anchor_w = int(anchor.winfo_width())
        except tk.TclError:
            anchor_w = 0
        card_w = max(text_w + px(36), anchor_w, px(140))
        card_h = edge * 2 + len(rows) * row_h
        margin = px(6)
        radius = px(8)
        selected_index = next((index for index, (_label, selected, _command) in enumerate(rows) if selected), 0)
        self._selected_plates: set[str] = set()

        canvas = tk.Canvas(
            window,
            width=card_w + margin * 2,
            height=card_h + margin * 2,
            highlightthickness=0,
            bd=0,
            bg=outside,
        )
        canvas.pack()
        _paint_flyout(canvas, margin, margin, card_w, card_h, radius, palette.menu_bg, palette.menu_border, outside)

        light = palette.bg.upper() == "#F3F3F3"
        selected_fill = "#F3F3F3" if light else "#3A3A3A"
        y = margin + edge
        for index, (label, selected, command) in enumerate(rows):
            hit = f"item{index}"
            plate = f"plate{index}"
            if selected:
                self._selected_plates.add(plate)
            _round_rect(
                canvas,
                margin + edge,
                y + px(1),
                card_w - edge * 2,
                row_h - px(2),
                px(4),
                selected_fill if selected else palette.menu_bg,
                tags=(plate,),
            )
            if selected:
                canvas.create_rectangle(
                    margin + edge + px(2),
                    y + px(6),
                    margin + edge + px(5),
                    y + row_h - px(6),
                    fill=palette.accent,
                    outline=palette.accent,
                    tags=(hit,),
                )
            canvas.create_text(
                margin + px(16),
                y + row_h // 2,
                text=label,
                anchor="w",
                fill=palette.text,
                font=_menu_font(px(14)),
                tags=(hit,),
            )

            def bind(tag: str, plate_tag: str = plate, cmd: Callable[[], None] = command) -> None:
                canvas.tag_bind(tag, "<Enter>", lambda _event, p=plate_tag: self._hover(p, True))
                canvas.tag_bind(tag, "<Leave>", lambda _event, p=plate_tag: self._hover(p, False))
                canvas.tag_bind(tag, "<Button-1>", lambda _event, c=cmd: self._activate(c))

            bind(hit)
            bind(plate)
            y += row_h

        self._canvas = canvas
        self._popup = popup
        ax, ay, aw, ah = widget_screen_rect(anchor)
        # The selected row covers the closed field. The list grows up and down from there.
        row_top = edge + selected_index * row_h
        body_x = ax + aw - card_w
        body_y = ay + ah / 2 - (row_top + row_h / 2)
        popup.reveal_card(int(body_x), int(body_y), card_w, card_h, margin)

    def _activate(self, command: Callable[[], None]) -> None:
        self.close()
        command()

    def _hover(self, tag: str, on: bool) -> None:
        canvas = self._canvas
        if canvas is None:
            return
        palette = current_palette()
        light = palette.bg.upper() == "#F3F3F3"
        if tag in self._selected_plates:
            color = "#F3F3F3" if light else "#3A3A3A"
        else:
            color = palette.menu_hover if on else palette.menu_bg
        for item in canvas.find_withtag(tag):
            if canvas.type(item) in {"rectangle", "polygon", "arc"}:
                try:
                    canvas.itemconfigure(item, fill=color, outline=color)
                except tk.TclError:
                    pass
