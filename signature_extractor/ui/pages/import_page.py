"""Empty screen 1: drop zone, open buttons, and the tips card."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from signature_extractor.ui.fonts import logical_text_width, ui_font
from signature_extractor.ui.icons import icon_image
from signature_extractor.ui.theme import pair
from signature_extractor.ui.tooltip import Tooltip
from signature_extractor.ui.widgets.drop_zone import DropZone


class ImportPage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        text_of: Callable[..., str],
        on_open_file: Callable[[], None],
        on_open_folder: Callable[[], None],
        on_how_to: Callable[[], None],
    ):
        super().__init__(master, fg_color="transparent")
        self._text_of = text_of
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.drop = DropZone(self)
        self.drop.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        tile = ctk.CTkFrame(
            self.drop.inner,
            width=84,
            height=84,
            corner_radius=8,
            fg_color=pair("accent_soft"),
            bg_color=pair("drop"),
        )
        tile.pack(pady=(0, 6))
        tile.pack_propagate(False)
        ctk.CTkLabel(tile, text="", image=icon_image("upload", 40, "accent")).place(relx=0.5, rely=0.5, anchor="center")

        self.title = ctk.CTkLabel(
            self.drop.inner,
            text="",
            font=ui_font(26, "bold"),
            height=34,
            text_color=pair("text"),
        )
        self.title.pack(pady=(16, 0))

        buttons = ctk.CTkFrame(self.drop.inner, fg_color="transparent")
        buttons.pack(pady=(16, 0))
        self.open_button = ctk.CTkButton(
            buttons,
            text="",
            height=44,
            corner_radius=6,
            font=ui_font(14),
            fg_color=pair("accent"),
            hover_color=pair("accent_hover"),
            text_color=pair("on_accent"),
            bg_color=pair("drop"),
            image=icon_image("image", 17, "on_accent"),
            compound="left",
            command=on_open_file,
        )
        self.open_button.pack(side="left", padx=(0, 10))
        self.folder_button = ctk.CTkButton(
            buttons,
            text="",
            height=44,
            corner_radius=6,
            font=ui_font(14),
            fg_color=pair("secondary_bg"),
            hover_color=pair("secondary_hover"),
            border_color=pair("secondary_border"),
            border_width=1,
            text_color=pair("text"),
            bg_color=pair("drop"),
            image=icon_image("folder", 17, "text"),
            compound="left",
            command=on_open_folder,
        )
        self.folder_button.pack(side="left")
        Tooltip(self.open_button, lambda: self._text_of("menu.open_file.tooltip"))

        tips = ctk.CTkFrame(
            self,
            fg_color=pair("tips"),
            border_color=pair("tips_border"),
            border_width=1,
            corner_radius=6,
            bg_color=pair("bg"),
        )
        tips.grid(row=1, column=0, sticky="ew")
        badge = ctk.CTkLabel(
            tips,
            text="i",
            width=18,
            height=18,
            corner_radius=9,
            fg_color=pair("accent"),
            text_color=pair("on_accent"),
            font=ui_font(12, "bold"),
        )
        badge.grid(row=0, column=0, padx=(16, 0), pady=(14, 0), sticky="n")
        body = ctk.CTkFrame(tips, fg_color="transparent")
        body.grid(row=0, column=1, sticky="ew", padx=(12, 16), pady=(10, 8))
        tips.grid_columnconfigure(1, weight=1)

        self.tips_title = ctk.CTkLabel(
            body,
            text="",
            anchor="w",
            font=ui_font(13, "bold"),
            text_color=pair("text"),
            height=18,
        )
        self.tips_title.pack(anchor="w", pady=(0, 1))
        self.tip_lines: list[ctk.CTkLabel] = []
        for key in ("import.tip_phone", "import.tip_closeup", "import.tip_background"):
            label = ctk.CTkLabel(
                body,
                text="",
                anchor="w",
                justify="left",
                font=ui_font(12),
                text_color=pair("muted"),
                height=16,
            )
            label._string_key = key  # type: ignore[attr-defined]
            label.pack(anchor="w", pady=0)
            self.tip_lines.append(label)
        self.supported = ctk.CTkLabel(
            body,
            text="",
            anchor="w",
            justify="left",
            font=ui_font(12),
            text_color=pair("muted"),
            height=16,
        )
        self.supported.pack(anchor="w", pady=(4, 0))
        self.how_to = ctk.CTkLabel(
            body,
            text="",
            anchor="w",
            font=ui_font(12, "bold"),
            text_color=pair("accent"),
            height=16,
            cursor="hand2",
        )
        self.how_to.pack(anchor="w", pady=(4, 0))
        self.how_to.bind("<Button-1>", lambda _event: on_how_to())
        tips.bind("<Configure>", self._wrap)

    def retranslate(self) -> None:
        text = self._text_of
        self.title.configure(text=text("import.drop_title"))
        open_label = text("menu.open_file")
        folder_label = text("import.batch_folder")
        # Icon 17, gap 8, 16 px of padding on each side. Width is logical so
        # Windows DPI does not apply the scale a second time.
        self.open_button.configure(text=open_label, width=logical_text_width(self, 14, open_label) + 57)
        self.folder_button.configure(text=folder_label, width=logical_text_width(self, 14, folder_label) + 57)
        self.tips_title.configure(text=text("import.tips_title"))
        for label in self.tip_lines:
            label.configure(text=text(label._string_key))  # type: ignore[attr-defined]
        self.supported.configure(text=text("import.supported"))
        self.how_to.configure(text=text("import.how_to_link"))
        self._wrap()

    def refresh_chrome(self) -> None:
        """Redraw the dashed border after a theme change."""
        self.drop._redraw()

    def _wrap(self, _event=None) -> None:
        width = max(self.winfo_width() - 90, 200)
        for label in (*self.tip_lines, self.supported, self.how_to, self.tips_title):
            label.configure(wraplength=width)
