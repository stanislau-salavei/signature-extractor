"""Empty screen 1: drop zone, open buttons, and the tips card."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from signature_extractor.ui.fonts import logical_text_width, ui_font
from signature_extractor.ui.svg_icons import svg_image
from signature_extractor.ui.theme import pair
from signature_extractor.ui.tooltip import Tooltip
from signature_extractor.ui.widgets.controls import EdgedButton
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
        ctk.CTkLabel(tile, text="", image=svg_image("drop_upload", 40, "accent")).place(
            relx=0.5, rely=0.5, anchor="center"
        )

        self.title = ctk.CTkLabel(
            self.drop.inner,
            text="",
            font=ui_font(24, "bold"),
            height=29,
            text_color=pair("text"),
        )
        # Tile margin-bottom 6 plus the stack gap 16 is 22 px to the title.
        self.title.pack(pady=(16, 0))

        buttons = ctk.CTkFrame(self.drop.inner, fg_color="transparent")
        # Stack gap 16 plus the button row's own margin-top 4.
        buttons.pack(pady=(20, 0))
        self.open_button = EdgedButton(
            buttons,
            text="",
            height=36,
            corner_radius=4,
            border_spacing=0,
            border_width=1,
            font=ui_font(14),
            fg_color=pair("accent"),
            hover_color=pair("accent_hover"),
            border_color=pair("primary_border"),
            bottom_color=pair("primary_bottom"),
            text_color=pair("on_accent"),
            bg_color=pair("drop"),
            image=svg_image("btn_open_file", 17, "on_accent"),
            compound="left",
            command=on_open_file,
        )
        self.open_button._image_label_spacing = 8
        self.open_button.pack(side="left", padx=(0, 10))
        self.folder_button = EdgedButton(
            buttons,
            text="",
            height=36,
            corner_radius=4,
            border_spacing=0,
            border_width=1,
            font=ui_font(14),
            fg_color=pair("secondary_bg"),
            hover_color=pair("secondary_hover"),
            border_color=pair("ctl_stroke"),
            bottom_color=pair("ctl_stroke2"),
            text_color=pair("text"),
            bg_color=pair("drop"),
            image=svg_image("btn_batch_folder", 17, "text"),
            compound="left",
            command=on_open_folder,
        )
        self.folder_button._image_label_spacing = 8
        self.folder_button.pack(side="left")
        Tooltip(self.open_button, lambda: self._text_of("menu.open_file.tooltip"))

        tips = ctk.CTkFrame(
            self,
            fg_color=pair("tips"),
            border_color=pair("tips_border"),
            border_width=1,
            corner_radius=4,
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
        # Padding 14 18 14 16, and the glyph sits 1 px below the top padding.
        badge.grid(row=0, column=0, padx=(16, 0), pady=(15, 14), sticky="n")
        body = ctk.CTkFrame(tips, fg_color="transparent")
        body.grid(row=0, column=1, sticky="ew", padx=(14, 18), pady=(14, 14))
        tips.grid_columnconfigure(1, weight=1)

        self.tips_title = ctk.CTkLabel(
            body,
            text="",
            anchor="w",
            font=ui_font(13, "bold"),
            text_color=pair("text"),
            height=16,
        )
        # Column gap 3 plus the title's own margin-bottom 3.
        self.tips_title.pack(anchor="w", pady=(0, 6))
        self.tip_lines: list[ctk.CTkLabel] = []
        for key in ("import.tip_phone", "import.tip_closeup", "import.tip_background"):
            label = ctk.CTkLabel(
                body,
                text="",
                anchor="w",
                justify="left",
                font=ui_font(12),
                text_color=pair("muted"),
                height=18,
            )
            label._string_key = key  # type: ignore[attr-defined]
            label.pack(anchor="w", pady=(0, 3))
            self.tip_lines.append(label)
        self.supported = ctk.CTkLabel(
            body,
            text="",
            anchor="w",
            justify="left",
            font=ui_font(12),
            text_color=pair("muted"),
            height=18,
        )
        # Extra 6 px on top of the 3 px column gap (the previous tip's bottom pad).
        self.supported.pack(anchor="w", pady=(6, 3))
        self.how_to = ctk.CTkLabel(
            body,
            text="",
            anchor="w",
            font=ui_font(12, "medium"),
            text_color=pair("accent_text"),
            height=18,
            cursor="hand2",
        )
        # Column gap 3 (from the formats line) plus margin-top 7.
        self.how_to.pack(anchor="w", pady=(7, 0))
        self.how_to.bind("<Button-1>", lambda _event: on_how_to())
        tips.bind("<Configure>", self._wrap)

    def retranslate(self) -> None:
        text = self._text_of
        self.title.configure(text=text("import.drop_title"))
        open_label = text("menu.open_file")
        folder_label = text("import.batch_folder")
        # Icon 17, gap 8, padding 0 20. Width is logical so Windows DPI does
        # not apply the scale a second time. Segoe UI lands near 163 / 252.
        self.open_button.configure(text=open_label, width=logical_text_width(self, 14, open_label) + 65)
        self.folder_button.configure(text=folder_label, width=logical_text_width(self, 14, folder_label) + 65)
        self.open_button._image_label_spacing = 8
        self.folder_button._image_label_spacing = 8
        self.open_button._create_grid()
        self.folder_button._create_grid()
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
