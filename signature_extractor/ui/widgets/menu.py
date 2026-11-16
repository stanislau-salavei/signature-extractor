"""The ⋯ menu. Five items, drawn on the canvas so they are part of the window bitmap.

A child frame inside an overrideredirect window was captured as an empty card:
the rounded fill is canvas pixels, but the labels were separate windows.
"""

from __future__ import annotations

from collections.abc import Callable

import tkinter as tk
import tkinter.font as tkfont

from signature_extractor.ui.fonts import family, ui_scale
from signature_extractor.ui.popup import BorderlessPopup
from signature_extractor.ui.svg_icons import svg_photo
from signature_extractor.ui.theme import current_palette

_TRANSPARENT = "#ff00ee"


class OverflowMenu:
    """Floating menu under the ⋯ button. Not a separate document window."""

    def __init__(self, master: tk.Misc):
        self.master = master
        self._popup: BorderlessPopup | None = None
        self._commands: list[tuple[str, str | None, Callable[[], None]]] = []
        self._swallow_reopen = False
        self._photos: list[object] = []
        self._canvas: tk.Canvas | None = None
        self.card_size: tuple[int, int] = (228, 203)

    def set_items(self, items: list[tuple[str, str | None, Callable[[], None]]]) -> None:
        """``items`` is ``(label, svg name or None, command)``. Separator after the second."""
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
        row_h = px(40)
        # Hover fill sits 4 px in from the menu edges. Rows themselves are the 40 px step.
        edge = px(4)
        icon_px = px(16)
        icon_x = px(14)
        icon_gap = px(12)
        text_right = px(24)
        sep_margin_y = px(4)
        sep_margin_x = px(8)
        sep_h = max(1, px(1))
        has_sep = len(self._commands) > 2
        has_icon = any(icon for _label, icon, _command in self._commands)
        measure = tkfont.Font(family=family(), size=-px(14))
        text_w = max((measure.measure(label) for label, _icon, _command in self._commands), default=px(40))
        icon_block = icon_px + icon_gap if has_icon else 0
        card_w = icon_x + icon_block + text_w + text_right
        card_h = edge + len(self._commands) * row_h + edge
        if has_sep:
            card_h += sep_margin_y * 2 + sep_h
        self.card_size = (card_w, card_h)

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

        self._photos = []
        y = margin + edge
        for index, (label, icon_name, command) in enumerate(self._commands):
            if has_sep and index == 2:
                sep_y = y + sep_margin_y
                canvas.create_line(
                    margin + sep_margin_x,
                    sep_y,
                    margin + card_w - sep_margin_x,
                    sep_y,
                    fill=palette.divider,
                    width=sep_h,
                )
                y += sep_margin_y * 2 + sep_h
            hit = f"item{index}"
            plate = f"plate{index}"
            _round_rect(
                canvas,
                margin + edge,
                y + px(2),
                card_w - edge * 2,
                row_h - px(4),
                px(4),
                palette.menu_bg,
                tags=(plate,),
            )
            text_x = margin + icon_x
            if icon_name:
                photo = svg_photo(canvas, icon_name, icon_px, palette.text)
                self._photos.append(photo)
                canvas.create_image(
                    margin + icon_x + icon_px // 2,
                    y + row_h // 2,
                    image=photo,
                    tags=(hit,),
                )
                text_x = margin + icon_x + icon_px + icon_gap
            canvas.create_text(
                text_x,
                y + row_h // 2,
                text=label,
                anchor="w",
                fill=palette.text,
                font=_menu_font(px(14)),
                tags=(hit,),
            )
            canvas.tag_bind(hit, "<Enter>", lambda _event, p=plate: self._hover(p, True))
            canvas.tag_bind(hit, "<Leave>", lambda _event, p=plate: self._hover(p, False))
            canvas.tag_bind(hit, "<Button-1>", lambda _event, cmd=command: self._activate(cmd))
            canvas.tag_bind(plate, "<Enter>", lambda _event, p=plate: self._hover(p, True))
            canvas.tag_bind(plate, "<Leave>", lambda _event, p=plate: self._hover(p, False))
            canvas.tag_bind(plate, "<Button-1>", lambda _event, cmd=command: self._activate(cmd))
            y += row_h

        self._canvas = canvas
        self._popup = popup
        # The card (not the shadow) lines up with the drop zone. The mockup
        # DOM sits 4 px further right; the product keeps the card flush.
        popup.reveal_body(
            anchor,
            body_width=card_w,
            body_height=card_h,
            align_right=align_right,
            gap=px(4),
            margin=margin,
        )

    def hide(self) -> None:
        popup = self._popup
        self._popup = None
        self._canvas = None
        self._photos = []
        if popup is not None:
            popup.close()

    def _note_anchor_press(self) -> None:
        self._swallow_reopen = True

    def _activate(self, command: Callable[[], None]) -> None:
        self.hide()
        command()

    def _hover(self, tag: str, on: bool) -> None:
        canvas = self._canvas
        if canvas is None:
            return
        palette = current_palette()
        color = palette.menu_hover if on else palette.menu_bg
        for item in canvas.find_withtag(tag):
            if canvas.type(item) == "rectangle" or canvas.type(item) in {"polygon", "arc"}:
                try:
                    canvas.itemconfigure(item, fill=color, outline=color)
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


def _round_rect(canvas, x, y, width, height, radius, color, outline_only: bool = False, tags=()) -> None:
    x2, y2 = x + width, y + height
    radius = min(radius, width // 2, height // 2)
    if outline_only:
        canvas.create_arc(x, y, x + 2 * radius, y + 2 * radius, start=90, extent=90, style="arc", outline=color, width=1, tags=tags)
        canvas.create_arc(x2 - 2 * radius, y, x2, y + 2 * radius, start=0, extent=90, style="arc", outline=color, width=1, tags=tags)
        canvas.create_arc(x, y2 - 2 * radius, x + 2 * radius, y2, start=180, extent=90, style="arc", outline=color, width=1, tags=tags)
        canvas.create_arc(x2 - 2 * radius, y2 - 2 * radius, x2, y2, start=270, extent=90, style="arc", outline=color, width=1, tags=tags)
        canvas.create_line(x + radius, y, x2 - radius, y, fill=color, tags=tags)
        canvas.create_line(x + radius, y2, x2 - radius, y2, fill=color, tags=tags)
        canvas.create_line(x, y + radius, x, y2 - radius, fill=color, tags=tags)
        canvas.create_line(x2, y + radius, x2, y2 - radius, fill=color, tags=tags)
        return
    canvas.create_rectangle(x + radius, y, x2 - radius, y2, fill=color, outline=color, tags=tags)
    canvas.create_rectangle(x, y + radius, x2, y2 - radius, fill=color, outline=color, tags=tags)
    canvas.create_arc(x, y, x + 2 * radius, y + 2 * radius, start=90, extent=90, fill=color, outline=color, tags=tags)
    canvas.create_arc(x2 - 2 * radius, y, x2, y + 2 * radius, start=0, extent=90, fill=color, outline=color, tags=tags)
    canvas.create_arc(x, y2 - 2 * radius, x + 2 * radius, y2, start=180, extent=90, fill=color, outline=color, tags=tags)
    canvas.create_arc(x2 - 2 * radius, y2 - 2 * radius, x2, y2, start=270, extent=90, fill=color, outline=color, tags=tags)
