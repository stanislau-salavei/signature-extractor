"""Settings page. Groups follow mockup 27. Size editing and update checks are stage 5."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from signature_extractor import __version__
from signature_extractor.controller.state import AppController
from signature_extractor.ui.fonts import ui_font
from signature_extractor.ui.icons import icon_image
from signature_extractor.ui.theme import (
    COLOR_SWATCHES,
    CONTENT_MAX_WIDTH,
    CONTENT_SIDE_PADDING,
    COPYRIGHT,
    LICENSE_NAME,
    SETTINGS_HEADER_HEIGHT,
    URL_GPL,
    URL_ISSUES,
    URL_RELEASE_NOTES,
    URL_RELEASES,
    URL_SOURCE,
    pair,
)
from signature_extractor.paths import license_path

_THEME_KEYS = {
    "system": "settings.theme.system",
    "light": "settings.theme.light",
    "dark": "settings.theme.dark",
}
_LANGUAGE_KEYS = {
    "system": "settings.language.system",
    "ru": "settings.language.ru",
    "en": "settings.language.en",
}
_SIZE_KEYS = {
    "original": "export.size.as_original",
    "15x5": "export.size.preset_15x5",
}
_COLOR_KEYS = {
    "as_photo": "color.as_photo",
    "black": "color.black",
    "blue": "color.blue",
    "ink_blue": "color.ink_blue",
    "bright_blue": "color.bright_blue",
}
_EXISTS_KEYS = {
    "add_number": "settings.if_exists.add_number",
    "replace": "common.replace",
    "ask": "settings.if_exists.ask",
}
_FORMAT_ORDER = ("png", "svg", "dxf")


class SettingsPage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        controller: AppController,
        on_back: Callable[[], None],
        on_change_folder: Callable[[], None],
        on_open_folder: Callable[[], None],
        on_open_url: Callable[[str], None],
        on_check_updates: Callable[[], None],
    ):
        super().__init__(master, fg_color="transparent")
        self.controller = controller
        self._on_open_url = on_open_url
        self._labels: list[tuple[ctk.CTkLabel, str]] = []
        self._popup: tk.Toplevel | None = None
        self._about_open = True
        self.folder_path: ctk.CTkLabel | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent", height=SETTINGS_HEADER_HEIGHT)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        back = ctk.CTkButton(
            header,
            text="",
            width=36,
            height=36,
            corner_radius=4,
            fg_color="transparent",
            hover_color=pair("menu_hover"),
            image=icon_image("back", 16, "text"),
            command=on_back,
        )
        back.place(x=8, rely=0.5, anchor="w")
        self.title = self._add_label(
            header,
            "menu.settings",
            font=ui_font(20, "bold"),
            text_color=pair("text"),
        )
        self.title.place(x=56, rely=0.5, anchor="w")

        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=pair("number_off"),
            scrollbar_button_hover_color=pair("muted"),
        )
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)
        self.column = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.column.grid(row=0, column=0, sticky="ew")
        self._layout_key: tuple[int, int] | None = None
        self.scroll.bind("<Configure>", self._center_column)

        self._build_appearance()
        self._build_processing()
        self._build_export()
        self._build_saving(on_change_folder, on_open_folder)
        self._build_about(on_check_updates)
        self._center_column()

    def retranslate(self) -> None:
        self._close_popup()
        text = self.controller.text
        for label, key in self._labels:
            value = text(key)
            label.configure(text=value)
            if isinstance(label, ctk.CTkButton):
                from signature_extractor.ui.fonts import text_width

                label.configure(width=text_width(13, value) + 32)
        self.theme_value.configure(text=text(_THEME_KEYS[self.controller.settings["theme"]]))
        self.language_value.configure(text=text(_LANGUAGE_KEYS[self.controller.settings["language"]]))
        self.formats_value.configure(text=self._formats_label())
        self.size_value.configure(text=self._size_label())
        self.color_value.configure(text=self._color_label())
        self._paint_swatch()
        self.dpi_value.configure(text=text("export.dpi_value", n=self.controller.settings["png_dpi"]))
        self.exists_value.configure(text=text(_EXISTS_KEYS[self.controller.settings["if_exists"]]))
        self.folder_path.configure(text=self.controller.save_folder())
        self._set_entry(self.margin_entry, text("export.size.mm_value", n=self.controller.settings["frame_margin_mm"]))
        self._set_entry(self.template_entry, self.controller.name_template())
        self.ai_caption.configure(text=text("common.on" if self.controller.settings["ai_default"] else "common.off"))
        self.gpu_caption.configure(text=text("common.on" if self.controller.settings["gpu_acceleration"] else "common.off"))
        self.updates_caption.configure(text=text("common.on" if self.controller.settings["check_updates"] else "common.off"))
        self.version_label.configure(text=__version__)
        self._sync_switch(self.ai_switch, self.controller.settings["ai_default"])
        self._sync_switch(self.gpu_switch, self.controller.settings["gpu_acceleration"])
        self._sync_switch(self.updates_switch, self.controller.settings["check_updates"])

    def _build_appearance(self) -> None:
        block = self._section("settings.appearance")
        self.theme_value = self._value_row(
            block,
            "theme",
            "settings.theme",
            "settings.theme.desc",
            boxed=False,
            command=self._open_theme,
        )
        self.language_value = self._value_row(
            block,
            "globe",
            "settings.language",
            "settings.language.desc",
            boxed=True,
            command=self._open_language,
        )

    def _build_processing(self) -> None:
        block = self._section("shell.step.process")
        self.ai_caption, self.ai_switch = self._switch_row(
            block,
            "sparkles",
            "settings.ai_default",
            "settings.ai_default.desc",
            self._toggle_ai,
        )
        self.gpu_caption, self.gpu_switch = self._switch_row(
            block,
            "monitor",
            "settings.gpu",
            "settings.gpu.desc",
            self._toggle_gpu,
        )

    def _build_export(self) -> None:
        block = self._section("shell.step.export")
        self.formats_value = self._value_row(
            block, "layers", "settings.formats", "settings.formats.desc", boxed=False, command=self._open_formats
        )
        self.size_value = self._value_row(
            block, "size", "settings.sizes", None, boxed=False, command=self._open_sizes
        )
        margin_controls, _title, _desc = self._card(
            block, "crop", "settings.margin", "settings.margin.desc"
        )
        self.margin_entry = ctk.CTkEntry(
            margin_controls,
            width=72,
            height=32,
            justify="center",
            corner_radius=4,
            border_width=1,
            font=ui_font(13),
            fg_color=pair("input_bg"),
            border_color=pair("input_border"),
            text_color=pair("text"),
        )
        self.margin_entry.pack(side="left")
        self.margin_entry.bind("<FocusOut>", self._commit_margin)
        self.margin_entry.bind("<Return>", self._commit_margin)
        self.color_value, self.color_swatch = self._color_row(block)
        self.dpi_value = self._value_row(
            block,
            "image",
            "settings.png_resolution",
            "settings.png_resolution.desc",
            boxed=True,
            command=self._open_dpi,
        )

    def _build_saving(self, on_change: Callable[[], None], on_open: Callable[[], None]) -> None:
        block = self._section("settings.save")
        folder_controls, _title, self.folder_path = self._card(
            block, "folder", "settings.folder", "", path_subtitle=True
        )
        self._button(folder_controls, "common.change_ellipsis", on_change)
        self._button(folder_controls, "common.open_folder", on_open)
        name_controls, _title, _desc = self._card(
            block, "type", "settings.name_template", "settings.name_template.desc"
        )
        self.template_entry = ctk.CTkEntry(
            name_controls,
            width=180,
            height=32,
            corner_radius=4,
            border_width=1,
            font=ui_font(13),
            fg_color=pair("input_bg"),
            border_color=pair("input_border"),
            text_color=pair("text"),
        )
        self.template_entry.pack(side="left")
        self.template_entry.bind("<FocusOut>", self._commit_template)
        self.template_entry.bind("<Return>", self._commit_template)
        self.exists_value = self._value_row(
            block,
            "files",
            "settings.if_exists",
            "settings.if_exists.desc",
            boxed=True,
            command=self._open_exists,
        )

    def _build_about(self, on_check: Callable[[], None]) -> None:
        block = self._section("settings.about")
        card = ctk.CTkFrame(
            block,
            fg_color=pair("card"),
            border_color=pair("card_border"),
            border_width=1,
            corner_radius=8,
        )
        card.pack(fill="x", pady=2)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=12)
        logo = self._app_logo()
        ctk.CTkLabel(row, text="", image=logo).pack(side="left", padx=(0, 14))
        words = ctk.CTkFrame(row, fg_color="transparent")
        words.pack(side="left", fill="x", expand=True)
        self._add_label(words, "app.name", font=ui_font(14), text_color=pair("text"), anchor="w").pack(anchor="w")
        self._add_label(
            words, "app.description", font=ui_font(12), text_color=pair("muted"), anchor="w"
        ).pack(anchor="w")
        side = ctk.CTkFrame(row, fg_color="transparent")
        side.pack(side="right")
        self.version_label = ctk.CTkLabel(side, text=__version__, font=ui_font(13), text_color=pair("muted"))
        self.version_label.pack(side="left", padx=(0, 6))
        self.about_chevron = ctk.CTkLabel(side, text="", image=icon_image("chevron_up", 16, "muted"))
        self.about_chevron.pack(side="left")
        for widget in (row, side, self.about_chevron, self.version_label):
            widget.bind("<Button-1>", lambda _event: self._toggle_about())
        self.about_body = ctk.CTkFrame(card, fg_color="transparent")
        self.about_body.pack(fill="x", padx=(62, 16), pady=(0, 8))
        self.copyright = ctk.CTkLabel(
            self.about_body, text=COPYRIGHT, font=ui_font(12), text_color=pair("muted"), anchor="w"
        )
        self.copyright.pack(anchor="w", pady=4)
        for key, url in (
            ("settings.release_notes", URL_RELEASE_NOTES),
            ("settings.all_releases", URL_RELEASES),
            ("settings.report_issue", URL_ISSUES),
            ("settings.source_code", URL_SOURCE),
        ):
            link = self._add_label(
                self.about_body, key, font=ui_font(14), text_color=pair("accent"), anchor="w", cursor="hand2"
            )
            link.pack(anchor="w", pady=6)
            link.bind("<Button-1>", lambda _event, target=url: self._on_open_url(target))
        license_row = ctk.CTkFrame(self.about_body, fg_color="transparent")
        license_row.pack(anchor="w", pady=6)
        self._add_label(
            license_row, "settings.license", font=ui_font(12), text_color=pair("muted")
        ).pack(side="left", padx=(0, 6))
        gpl = ctk.CTkLabel(
            license_row, text=LICENSE_NAME, font=ui_font(14), text_color=pair("accent"), cursor="hand2"
        )
        gpl.pack(side="left")
        gpl.bind("<Button-1>", lambda _event: self._open_license())

        updates = ctk.CTkFrame(
            block,
            fg_color=pair("card"),
            border_color=pair("card_border"),
            border_width=1,
            corner_radius=8,
        )
        updates.pack(fill="x", pady=2)
        inner = ctk.CTkFrame(updates, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(inner, text="", image=icon_image("refresh", 20, "muted")).pack(side="left", padx=(0, 14))
        self._add_label(
            inner, "settings.check_updates", font=ui_font(14), text_color=pair("text"), anchor="w"
        ).pack(side="left")
        self.updates_switch = self._switch(inner, self._toggle_updates)
        self.updates_switch.pack(side="right")
        self.updates_caption = ctk.CTkLabel(inner, text="", font=ui_font(13), text_color=pair("text"))
        self.updates_caption.pack(side="right", padx=(0, 8))
        self._button(inner, "settings.check_now", on_check).pack_configure(side="right", padx=(0, 8))

    def _section(self, key: str) -> ctk.CTkFrame:
        block = ctk.CTkFrame(self.column, fg_color="transparent")
        block.pack(fill="x", pady=(0, 20))
        self._add_label(block, key, font=ui_font(14), text_color=pair("text"), anchor="w").pack(
            anchor="w", pady=(8, 8)
        )
        return block

    def _card(self, parent, icon_name: str, title_key: str, desc_key: str | None, path_subtitle: bool = False):
        card = ctk.CTkFrame(
            parent,
            fg_color=pair("card"),
            border_color=pair("card_border"),
            border_width=1,
            corner_radius=8,
        )
        card.pack(fill="x", pady=2)
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(card, text="", image=icon_image(icon_name, 20, "muted")).grid(
            row=0, column=0, padx=(16, 14), pady=16
        )
        words = ctk.CTkFrame(card, fg_color="transparent")
        words.grid(row=0, column=1, sticky="ew", pady=12)
        title = self._add_label(words, title_key, font=ui_font(14), text_color=pair("text"), anchor="w")
        title.pack(anchor="w")
        if path_subtitle:
            desc = ctk.CTkLabel(words, text="", font=ui_font(12), text_color=pair("muted"), anchor="w", justify="left")
            desc.pack(anchor="w")
        elif desc_key:
            desc = self._add_label(
                words, desc_key, font=ui_font(12), text_color=pair("muted"), anchor="w", justify="left"
            )
            desc.pack(anchor="w")
        else:
            desc = None
        controls = ctk.CTkFrame(card, fg_color="transparent")
        controls.grid(row=0, column=2, padx=(8, 16), pady=12, sticky="e")
        return controls, title, desc

    def _value_row(self, parent, icon_name, title_key, desc_key, boxed: bool, command):
        controls, _title, _desc = self._card(parent, icon_name, title_key, desc_key)
        return self._value_control(controls, boxed, command)

    def _value_control(self, card, boxed: bool, command) -> ctk.CTkLabel:
        if boxed:
            host = ctk.CTkFrame(
                card,
                fg_color=pair("input_bg"),
                border_color=pair("input_border"),
                border_width=1,
                corner_radius=4,
            )
            text_color = pair("text")
        else:
            host = ctk.CTkFrame(card, fg_color="transparent")
            text_color = pair("muted")
        host.pack(side="left")
        label = ctk.CTkLabel(host, text="", font=ui_font(13), text_color=text_color)
        label.pack(side="left", padx=(10, 4), pady=4)
        chevron = ctk.CTkLabel(host, text="", image=icon_image("chevron_down", 14, "muted"))
        chevron.pack(side="left", padx=(0, 8))
        for widget in (host, label, chevron):
            widget.bind("<Button-1>", lambda _event, cb=command, anchor=host: cb(anchor))
            widget.configure(cursor="hand2")
        return label

    def _color_row(self, parent):
        controls, _title, _desc = self._card(parent, "drop", "settings.color_default", "settings.color_default.desc")
        host = ctk.CTkFrame(
            controls,
            fg_color=pair("input_bg"),
            border_color=pair("input_border"),
            border_width=1,
            corner_radius=4,
        )
        host.pack(side="left")
        swatch = ctk.CTkFrame(host, width=16, height=16, corner_radius=3)
        swatch.pack(side="left", padx=(10, 6), pady=8)
        swatch.pack_propagate(False)
        label = ctk.CTkLabel(host, text="", font=ui_font(13), text_color=pair("text"))
        label.pack(side="left", padx=(0, 4))
        chevron = ctk.CTkLabel(host, text="", image=icon_image("chevron_down", 14, "muted"))
        chevron.pack(side="left", padx=(0, 8))
        for widget in (host, label, chevron, swatch):
            widget.bind("<Button-1>", lambda _event, anchor=host: self._open_color(anchor))
            widget.configure(cursor="hand2")
        return label, swatch

    def _switch_row(self, parent, icon_name, title_key, desc_key, command):
        controls, _title, _desc = self._card(parent, icon_name, title_key, desc_key)
        caption = ctk.CTkLabel(controls, text="", font=ui_font(13), text_color=pair("text"))
        caption.pack(side="left", padx=(0, 8))
        switch = self._switch(controls, command)
        switch.pack(side="left")
        return caption, switch

    def _switch(self, master, command) -> ctk.CTkSwitch:
        return ctk.CTkSwitch(
            master,
            text="",
            width=46,
            switch_width=40,
            switch_height=20,
            progress_color=pair("accent"),
            fg_color=pair("switch_off"),
            button_color=("#FFFFFF", "#FFFFFF"),
            button_hover_color=("#F7F7F7", "#F7F7F7"),
            command=command,
        )

    def _button(self, master, key: str, command) -> ctk.CTkButton:
        button = ctk.CTkButton(
            master,
            text="",
            height=32,
            corner_radius=4,
            font=ui_font(13),
            fg_color=pair("secondary_bg"),
            hover_color=pair("secondary_hover"),
            border_color=pair("secondary_border"),
            border_width=1,
            text_color=pair("text"),
            command=command,
        )
        button.pack(side="left", padx=(0, 8))
        self._labels.append((button, key))
        return button

    def _add_label(self, master, key: str, **kwargs) -> ctk.CTkLabel:
        label = ctk.CTkLabel(master, text="", **kwargs)
        self._labels.append((label, key))
        return label

    def _toggle_about(self) -> None:
        self._about_open = not self._about_open
        if self._about_open:
            self.about_body.pack(fill="x", padx=(62, 16), pady=(0, 8))
            self.about_chevron.configure(image=icon_image("chevron_up", 16, "muted"))
        else:
            self.about_body.pack_forget()
            self.about_chevron.configure(image=icon_image("chevron_down", 16, "muted"))

    def _open_theme(self, anchor) -> None:
        self._choice_popup(anchor, list(_THEME_KEYS), self.controller.settings["theme"], self.controller.set_theme)

    def _open_language(self, anchor) -> None:
        self._choice_popup(
            anchor, list(_LANGUAGE_KEYS), self.controller.settings["language"], self.controller.set_language_mode
        )

    def _open_sizes(self, anchor) -> None:
        ids = ["original", "15x5"]
        ids.extend(item["id"] for item in self.controller.settings["custom_sizes"])

        def choose(size_id: str) -> None:
            self.controller.update_setting("default_size_id", size_id)

        self._choice_popup(anchor, ids, self.controller.settings["default_size_id"], choose, label_of=self._size_label_for)

    def _open_color(self, anchor) -> None:
        ids = list(_COLOR_KEYS)
        ids.extend(item["id"] for item in self.controller.settings["custom_colors"])

        def choose(color_id: str) -> None:
            self.controller.update_setting("default_color", color_id)

        self._choice_popup(anchor, ids, self.controller.settings["default_color"], choose, label_of=self._color_label_for)

    def _open_dpi(self, anchor) -> None:
        def choose(value: str) -> None:
            self.controller.update_setting("png_dpi", int(value))

        current = str(self.controller.settings["png_dpi"])
        self._choice_popup(
            anchor,
            ["150", "300", "600"],
            current,
            choose,
            label_of=lambda value: self.controller.text("export.dpi_value", n=int(value)),
        )

    def _open_exists(self, anchor) -> None:
        self._choice_popup(
            anchor,
            list(_EXISTS_KEYS),
            self.controller.settings["if_exists"],
            lambda value: self.controller.update_setting("if_exists", value),
            label_of=lambda value: self.controller.text(_EXISTS_KEYS[value]),
        )

    def _open_formats(self, anchor) -> None:
        self._close_popup()
        selected = set(self.controller.settings["formats"])
        popup, inner = self._popup_shell(anchor)
        for fmt in _FORMAT_ORDER:
            var = tk.BooleanVar(value=fmt in selected)

            def toggle(name=fmt, variable=var) -> None:
                current = [item for item in _FORMAT_ORDER if item in self.controller.settings["formats"]]
                if variable.get():
                    if name not in current:
                        current.append(name)
                else:
                    if len(current) == 1 and name in current:
                        variable.set(True)
                        return
                    current = [item for item in current if item != name]
                ordered = [item for item in _FORMAT_ORDER if item in current]
                # Save without rebuilding the page, so the menu stays open.
                self.controller.settings["formats"] = ordered
                self.controller.store.save(self.controller.settings)
                self.formats_value.configure(text=self._formats_label())

            row = tk.Checkbutton(
                inner,
                text=fmt.upper(),
                variable=var,
                command=toggle,
                bg=self._menu_bg(),
                fg=self._menu_fg(False),
                activebackground=self._menu_bg(),
                activeforeground=self._menu_fg(False),
                selectcolor=self._menu_bg(),
                font=_tk_font(),
                anchor="w",
            )
            row.pack(fill="x", padx=8, pady=2)
        self._place_popup(popup, anchor)

    def _choice_popup(self, anchor, ids, current, command, label_of=None) -> None:
        self._close_popup()
        popup, inner = self._popup_shell(anchor)
        for value in ids:
            label = label_of(value) if label_of else self._default_choice_label(value)
            button = tk.Label(
                inner,
                text=label,
                bg=self._menu_bg(),
                fg=self._menu_fg(value == current),
                font=_tk_font(),
                anchor="w",
                padx=12,
                pady=8,
            )
            button.pack(fill="x")
            button.bind("<Button-1>", lambda _event, chosen=value: self._choose(command, chosen))
        self._place_popup(popup, anchor)

    def _default_choice_label(self, value: str) -> str:
        if value in _THEME_KEYS:
            return self.controller.text(_THEME_KEYS[value])
        if value in _LANGUAGE_KEYS:
            return self.controller.text(_LANGUAGE_KEYS[value])
        return value

    def _choose(self, command, value) -> None:
        self._close_popup()
        command(value)

    def _popup_shell(self, anchor):
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.configure(bg=self._menu_border())
        inner = tk.Frame(popup, bg=self._menu_bg())
        inner.pack(padx=1, pady=1)
        self._popup = popup
        return popup, inner

    def _place_popup(self, popup, anchor) -> None:
        popup.update_idletasks()
        x = anchor.winfo_rootx() + anchor.winfo_width() - popup.winfo_reqwidth()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 4
        popup.geometry(f"+{max(x, 0)}+{y}")

    def _close_popup(self) -> None:
        if self._popup is not None:
            try:
                self._popup.destroy()
            except tk.TclError:
                pass
            self._popup = None

    def _menu_bg(self) -> str:
        from signature_extractor.ui.theme import current_palette

        return current_palette().menu_bg

    def _menu_border(self) -> str:
        from signature_extractor.ui.theme import current_palette

        return current_palette().menu_border

    def _menu_fg(self, selected: bool) -> str:
        from signature_extractor.ui.theme import current_palette

        palette = current_palette()
        return palette.accent if selected else palette.text

    def _formats_label(self) -> str:
        return ", ".join(fmt.upper() for fmt in _FORMAT_ORDER if fmt in self.controller.settings["formats"])

    def _size_label(self) -> str:
        return self._size_label_for(self.controller.settings["default_size_id"])

    def _size_label_for(self, size_id: str) -> str:
        if size_id in _SIZE_KEYS:
            return self.controller.text(_SIZE_KEYS[size_id])
        for item in self.controller.settings["custom_sizes"]:
            if item.get("id") == size_id:
                return str(item.get("name", size_id))
        return self.controller.text("export.size.preset_15x5")

    def _color_label(self) -> str:
        return self._color_label_for(self.controller.settings["default_color"])

    def _color_label_for(self, color_id: str) -> str:
        if color_id in _COLOR_KEYS:
            return self.controller.text(_COLOR_KEYS[color_id])
        for item in self.controller.settings["custom_colors"]:
            if item.get("id") == color_id:
                return str(item.get("name", color_id))
        return self.controller.text("color.blue")

    def _paint_swatch(self) -> None:
        color_id = self.controller.settings["default_color"]
        swatch = COLOR_SWATCHES.get(color_id)
        if swatch is None:
            for item in self.controller.settings["custom_colors"]:
                if item.get("id") == color_id:
                    swatch = item.get("hex")
        if color_id == "as_photo" or not swatch:
            self.color_swatch.configure(fg_color=pair("muted"))
        else:
            self.color_swatch.configure(fg_color=swatch)

    def _toggle_ai(self) -> None:
        self.controller.update_setting("ai_default", bool(self.ai_switch.get()))

    def _toggle_gpu(self) -> None:
        self.controller.update_setting("gpu_acceleration", bool(self.gpu_switch.get()))

    def _toggle_updates(self) -> None:
        self.controller.update_setting("check_updates", bool(self.updates_switch.get()))

    def _commit_margin(self, _event=None) -> None:
        raw = self.margin_entry.get().lower().replace("мм", "").replace("mm", "").replace(" ", "").replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            value = -1
        if value < 0 or value > 100:
            self._set_entry(
                self.margin_entry,
                self.controller.text("export.size.mm_value", n=self.controller.settings["frame_margin_mm"]),
            )
            return
        self.controller.update_setting("frame_margin_mm", value)

    def _commit_template(self, _event=None) -> None:
        value = self.template_entry.get().strip()
        localized = self.controller.text("settings.name_template.value")
        if not value or value == localized:
            self.controller.update_setting("name_template", None)
        else:
            self.controller.update_setting("name_template", value)

    def _set_entry(self, entry: ctk.CTkEntry, value: str) -> None:
        if entry.focus_get() is entry:
            return
        entry.delete(0, "end")
        entry.insert(0, value)

    def _sync_switch(self, switch: ctk.CTkSwitch, on: bool) -> None:
        # select/deselect can invoke the command; write the variable directly.
        if bool(switch.get()) != on:
            if on:
                switch.select()
            else:
                switch.deselect()

    def _open_license(self) -> None:
        path = license_path()
        if path is not None:
            self._on_open_url(path.as_uri())
        else:
            self._on_open_url(URL_GPL)

    def _app_logo(self):
        import customtkinter as ctk
        from PIL import Image

        from signature_extractor.paths import app_icon_path

        image = Image.open(app_icon_path()).convert("RGBA").resize((32, 32))
        self._logo = ctk.CTkImage(light_image=image, dark_image=image, size=(32, 32))
        return self._logo

    def _center_column(self, _event=None) -> None:
        width = self.scroll.winfo_width()
        if width <= 1:
            return
        content = min(CONTENT_MAX_WIDTH, max(280, width - CONTENT_SIDE_PADDING * 2))
        side = max(0, (width - content) // 2)
        # A side padding larger than the frame makes the canvas grow and the
        # scrollbar redraw forever. Keep the column inside the width we were given.
        if side * 2 >= width:
            side = 0
        key = (width, side)
        if key == self._layout_key:
            return
        self._layout_key = key
        self.column.grid_configure(padx=side, pady=(0, 24))
        if self.folder_path is not None:
            self.folder_path.configure(wraplength=max(180, content - 360))

def _tk_font():
    from signature_extractor.ui.fonts import family

    return (family(), 10)
