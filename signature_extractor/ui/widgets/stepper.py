"""Top stepper: Import, Processing, Export."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from signature_extractor.ui.fonts import ui_font
from signature_extractor.ui.theme import pair

# Logical pixels. CustomTkinter scales width, height, padx and pady by the
# same DPI factor, so circles stay round and these gaps stay equal at
# 100 / 125 / 150 %.
BADGE_SIZE = 22
# Gap between the stepper border and the steps. Same on every side.
STEPPER_PAD = 4
# Padding inside each step. Left equals right, top equals bottom.
STEP_PAD_X = 10
STEP_PAD_Y = 6
# Space between steps. Applied only between items, not outside the row.
STEP_GAP = 4


class CircleBadge(ctk.CTkFrame):
    """A step number drawn in a circle.

    A ``CTkLabel`` grows to the text width (Segoe UI is wider than the
    requested 22 px), so the rounded rect becomes an oval. This frame is
    locked to equal width and height; the digit is placed in the centre
    and cannot resize the circle.
    """

    def __init__(self, master):
        super().__init__(
            master,
            width=BADGE_SIZE,
            height=BADGE_SIZE,
            corner_radius=BADGE_SIZE // 2,
            fg_color="transparent",
            border_width=1,
            border_color=pair("number_off"),
            bg_color="transparent",
        )
        self._lock()
        self.number = ctk.CTkLabel(
            self,
            text="",
            width=1,
            height=1,
            font=ui_font(12, "bold"),
            fg_color="transparent",
            text_color=pair("number_off"),
        )
        self.number.place(relx=0.5, rely=0.5, anchor="center")

    def set_number(self, number: int) -> None:
        self.number.configure(text=str(number))
        self._lock()

    def set_active(self, active: bool) -> None:
        if active:
            self.configure(fg_color=pair("accent"), border_width=0)
            self.number.configure(text_color=pair("on_accent"))
        else:
            self.configure(
                fg_color="transparent",
                border_width=1,
                border_color=pair("number_off"),
            )
            self.number.configure(text_color=pair("number_off"))
        self._lock()

    def _lock(self) -> None:
        self.configure(width=BADGE_SIZE, height=BADGE_SIZE)
        self.grid_propagate(False)
        self.pack_propagate(False)


class Stepper(ctk.CTkFrame):
    """Centered step control. Steps 2 and 3 stay inactive until a result exists."""

    def __init__(self, master, on_step: Callable[[int], None]):
        super().__init__(
            master,
            fg_color=pair("stepper_bg"),
            border_color=pair("stepper_border"),
            border_width=1,
            corner_radius=8,
            bg_color=pair("bg"),
        )
        self._on_step = on_step
        self._steps: list[dict] = []
        self._font = ui_font(14)
        self._font_active = ui_font(14, "bold")
        self._track = ctk.CTkFrame(self, fg_color="transparent")
        self._track.pack(padx=STEPPER_PAD, pady=STEPPER_PAD)
        for number in (1, 2, 3):
            self._steps.append(self._build_step(number))

    def _build_step(self, number: int) -> dict:
        gap = (STEP_GAP, 0) if number > 1 else 0
        chip = ctk.CTkFrame(self._track, fg_color="transparent", corner_radius=6, bg_color="transparent")
        chip.pack(side="left", padx=gap)
        body = ctk.CTkFrame(chip, fg_color="transparent")
        body.pack(padx=STEP_PAD_X, pady=STEP_PAD_Y)
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack()
        badge = CircleBadge(row)
        badge.set_number(number)
        badge.pack(side="left")
        text_col = ctk.CTkFrame(row, fg_color="transparent")
        text_col.pack(side="left", padx=(8, 0))
        label = ctk.CTkLabel(
            text_col,
            text="",
            font=self._font,
            text_color=pair("muted"),
            fg_color="transparent",
        )
        label.pack()
        underline = ctk.CTkFrame(
            text_col,
            height=2,
            width=BADGE_SIZE,
            corner_radius=1,
            fg_color=pair("accent"),
        )
        underline.pack_propagate(False)
        underline.grid_propagate(False)
        return {
            "number": number,
            "chip": chip,
            "badge": badge,
            "label": label,
            "underline": underline,
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
            badge: CircleBadge = step["badge"]
            label = step["label"]
            underline = step["underline"]
            badge.set_active(is_active)
            if is_active:
                chip.configure(
                    fg_color=pair("stepper_chip"),
                    border_width=1,
                    border_color=("#E4E4E4", "#4A4A4A"),
                )
                label.configure(font=self._font_active, text_color=pair("text"))
                underline.pack(pady=(3, 0))
            else:
                chip.configure(fg_color="transparent", border_width=0)
                label.configure(font=self._font, text_color=pair("muted"))
                underline.pack_forget()
            targets = (chip, label, badge, badge.number)
            for widget in targets:
                widget.unbind("<Button-1>")
            if is_enabled and not is_active:
                for widget in targets:
                    widget.bind("<Button-1>", lambda _event, n=number: self._on_step(n))
                    widget.configure(cursor="hand2")
            else:
                for widget in targets:
                    widget.configure(cursor="arrow")
