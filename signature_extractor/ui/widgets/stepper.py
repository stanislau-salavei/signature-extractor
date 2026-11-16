"""Top stepper: Import, Processing, Export."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from signature_extractor.ui.fonts import ui_font
from signature_extractor.ui.theme import pair


class Stepper(ctk.CTkFrame):
    """Centered step control. Steps 2 and 3 stay inactive until a result exists."""

    def __init__(self, master, on_step: Callable[[int], None]):
        super().__init__(
            master,
            fg_color=pair("stepper_bg"),
            border_color=pair("stepper_border"),
            border_width=1,
            corner_radius=8,
        )
        self._on_step = on_step
        self._steps: list[dict] = []
        self._font = ui_font(14)
        self._font_active = ui_font(14, "bold")
        self._number_font = ui_font(12, "bold")
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(padx=4, pady=4)
        for number in (1, 2, 3):
            self._steps.append(self._build_step(inner, number))

    def _build_step(self, master, number: int) -> dict:
        chip = ctk.CTkFrame(master, fg_color="transparent", corner_radius=6)
        chip.pack(side="left", padx=2)
        row = ctk.CTkFrame(chip, fg_color="transparent")
        row.pack(padx=10, pady=(6, 2))
        badge = ctk.CTkLabel(
            row,
            text=str(number),
            width=22,
            height=22,
            corner_radius=11,
            font=self._number_font,
            fg_color="transparent",
            text_color=pair("number_off"),
            border_width=1,
            border_color=pair("number_off"),
        )
        badge.pack(side="left")
        label = ctk.CTkLabel(
            row,
            text="",
            font=self._font,
            text_color=pair("muted"),
            fg_color="transparent",
        )
        label.pack(side="left", padx=(8, 0))
        underline = ctk.CTkFrame(chip, height=2, width=18, corner_radius=1, fg_color=pair("accent"))
        # Packed only while this step is the active one.
        return {
            "number": number,
            "chip": chip,
            "badge": badge,
            "label": label,
            "underline": underline,
            "key": "",
        }

    def set_labels(self, labels: list[str]) -> None:
        for step, text in zip(self._steps, labels):
            step["label"].configure(text=text)

    def set_state(self, active: int, enabled: dict[int, bool]) -> None:
        for step in self._steps:
            number = step["number"]
            is_active = number == active
            is_enabled = enabled.get(number, False)
            chip = step["chip"]
            badge = step["badge"]
            label = step["label"]
            underline = step["underline"]
            if is_active:
                chip.configure(fg_color=pair("stepper_chip"))
                badge.configure(
                    fg_color=pair("accent"),
                    text_color=pair("on_accent"),
                    border_width=0,
                )
                label.configure(font=self._font_active, text_color=pair("text"))
                underline.pack(pady=(0, 5))
            else:
                chip.configure(fg_color="transparent")
                badge.configure(
                    fg_color="transparent",
                    text_color=pair("number_off"),
                    border_width=1,
                    border_color=pair("number_off"),
                )
                label.configure(font=self._font, text_color=pair("muted"))
                underline.pack_forget()
            chip.unbind("<Button-1>")
            label.unbind("<Button-1>")
            badge.unbind("<Button-1>")
            if is_enabled and not is_active:
                for widget in (chip, label, badge):
                    widget.bind("<Button-1>", lambda _event, n=number: self._on_step(n))
                    widget.configure(cursor="hand2")
            else:
                for widget in (chip, label, badge):
                    widget.configure(cursor="arrow")
