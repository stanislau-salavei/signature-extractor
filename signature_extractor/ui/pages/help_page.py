"""Help is a stub in stage 1: the section titles only. Articles arrive in stage 5."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from signature_extractor.ui.fonts import ui_font
from signature_extractor.ui.svg_icons import svg_image
from signature_extractor.ui.theme import SETTINGS_HEADER_HEIGHT, pair

_SECTIONS = (
    "help.nav.start",
    "help.nav.prep",
    "help.nav.process",
    "help.nav.batch",
    "help.nav.formats",
)


class HelpPage(ctk.CTkFrame):
    def __init__(self, master, text_of: Callable[..., str], on_back: Callable[[], None]):
        super().__init__(master, fg_color="transparent")
        self._text_of = text_of
        self._rows: list[tuple[ctk.CTkLabel, str]] = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent", height=SETTINGS_HEADER_HEIGHT)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkButton(
            header,
            text="",
            width=36,
            height=36,
            corner_radius=4,
            fg_color="transparent",
            hover_color=pair("menu_hover"),
            image=svg_image("settings_back", 16, "text"),
            command=on_back,
        ).place(x=8, rely=0.5, anchor="w")
        self.title = ctk.CTkLabel(header, text="", font=ui_font(20, "bold"), text_color=pair("text"))
        self.title.place(x=56, rely=0.5, anchor="w")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        self.list = ctk.CTkFrame(
            body,
            fg_color=pair("card"),
            border_color=pair("card_border"),
            border_width=1,
            corner_radius=8,
            bg_color=pair("bg"),
        )
        self.list.pack(anchor="n", pady=8, padx=56, fill="x")
        for key in _SECTIONS:
            label = ctk.CTkLabel(self.list, text="", anchor="w", font=ui_font(14), text_color=pair("text"))
            label.pack(fill="x", padx=16, pady=10)
            self._rows.append((label, key))

    def retranslate(self) -> None:
        self.title.configure(text=self._text_of("menu.help"))
        for label, key in self._rows:
            label.configure(text=self._text_of(key))
