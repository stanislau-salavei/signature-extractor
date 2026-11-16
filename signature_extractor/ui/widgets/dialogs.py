"""Modal dialogs used by the shell: restart (stub) and about."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from signature_extractor.ui.fonts import text_width, ui_font
from signature_extractor.ui.theme import COPYRIGHT, LICENSE_NAME, pair


class _Dialog(ctk.CTkToplevel):
    def __init__(self, master, title: str, width: int):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.configure(fg_color=pair("dialog_bg"))
        self.geometry(f"{width}x220")
        self.grid_columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _event: self._cancel())
        self._on_cancel: Callable[[], None] = lambda: None

    def place_near_parent(self) -> None:
        self.update_idletasks()
        parent = self.master
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        x = px + max(0, (pw - width) // 2)
        y = py + max(0, (ph - height) // 2)
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        self.focus_set()

    def _cancel(self) -> None:
        self._on_cancel()


class RestartDialog(_Dialog):
    """«Начать заново?» — wired for later stages. Stage 1 does not show it."""

    def __init__(self, master, text_of: Callable[..., str], on_confirm: Callable[[], None], on_cancel: Callable[[], None]):
        title = text_of("dialog.restart.title")
        super().__init__(master, title, 420)
        self._on_cancel = self._close_cancel
        self._confirm = on_confirm
        self._cancel_cb = on_cancel
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 16))
        ctk.CTkLabel(
            body, text=title, font=ui_font(20, "bold"), text_color=pair("text"), anchor="w"
        ).pack(anchor="w", pady=(0, 12))
        ctk.CTkLabel(
            body,
            text=text_of("dialog.restart.body"),
            font=ui_font(14),
            text_color=pair("text"),
            anchor="w",
            justify="left",
            wraplength=360,
        ).pack(anchor="w")
        foot = ctk.CTkFrame(self, fg_color=pair("dialog_foot"))
        foot.grid(row=1, column=0, sticky="ew")
        buttons = ctk.CTkFrame(foot, fg_color="transparent")
        buttons.pack(fill="x", padx=24, pady=24)
        buttons.grid_columnconfigure((0, 1), weight=1)
        primary = text_of("dialog.restart.ok")
        secondary = text_of("common.cancel")
        ctk.CTkButton(
            buttons,
            text=primary,
            height=32,
            corner_radius=4,
            font=ui_font(13),
            fg_color=pair("accent"),
            hover_color=pair("accent_hover"),
            text_color=pair("on_accent"),
            command=self._accept,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            buttons,
            text=secondary,
            height=32,
            corner_radius=4,
            font=ui_font(13),
            fg_color=pair("secondary_bg"),
            hover_color=pair("secondary_hover"),
            border_color=pair("secondary_border"),
            border_width=1,
            text_color=pair("text"),
            command=self._close_cancel,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.place_near_parent()

    def _accept(self) -> None:
        self.destroy()
        self._confirm()

    def _close_cancel(self) -> None:
        self.destroy()
        self._cancel_cb()


class AboutDialog(_Dialog):
    def __init__(self, master, text_of: Callable[..., str], version: str, on_close: Callable[[], None], on_url: Callable[[str], None], on_issue: Callable[[], None]):
        title = text_of("menu.about")
        super().__init__(master, title, 380)
        self._on_cancel = self._close
        self._close_cb = on_close
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 12))
        ctk.CTkLabel(body, text=title, font=ui_font(20, "bold"), text_color=pair("text"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(body, text=text_of("app.name"), font=ui_font(14), text_color=pair("text"), anchor="w").pack(
            anchor="w", pady=(16, 0)
        )
        ctk.CTkLabel(
            body,
            text=text_of("about.version", version=version),
            font=ui_font(14),
            text_color=pair("text"),
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(body, text=COPYRIGHT, font=ui_font(12), text_color=pair("muted"), anchor="w").pack(
            anchor="w", pady=(8, 0)
        )
        for key, url in (
            ("settings.source_code", "source"),
            ("settings.release_notes", "notes"),
        ):
            link = ctk.CTkLabel(
                body, text=text_of(key), font=ui_font(14), text_color=pair("accent"), anchor="w", cursor="hand2"
            )
            link.pack(anchor="w", pady=(12, 0))
            link.bind("<Button-1>", lambda _event, kind=url: on_url(kind))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(anchor="w", pady=(12, 0))
        ctk.CTkLabel(row, text=text_of("settings.license"), font=ui_font(12), text_color=pair("muted")).pack(
            side="left", padx=(0, 6)
        )
        gpl = ctk.CTkLabel(row, text=LICENSE_NAME, font=ui_font(14), text_color=pair("accent"), cursor="hand2")
        gpl.pack(side="left")
        gpl.bind("<Button-1>", lambda _event: on_url("license"))

        foot = ctk.CTkFrame(self, fg_color=pair("dialog_foot"))
        foot.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        buttons = ctk.CTkFrame(foot, fg_color="transparent")
        buttons.pack(fill="x", padx=24, pady=24)
        buttons.grid_columnconfigure((0, 1), weight=1)
        issue = text_of("settings.report_issue")
        ok = text_of("common.ok")
        ctk.CTkButton(
            buttons,
            text=issue,
            height=32,
            corner_radius=4,
            font=ui_font(13),
            fg_color=pair("secondary_bg"),
            hover_color=pair("secondary_hover"),
            border_color=pair("secondary_border"),
            border_width=1,
            text_color=pair("text"),
            command=on_issue,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            buttons,
            text=ok,
            height=32,
            width=text_width(13, ok) + 24,
            corner_radius=4,
            font=ui_font(13),
            fg_color=pair("accent"),
            hover_color=pair("accent_hover"),
            text_color=pair("on_accent"),
            command=self._close,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.place_near_parent()

    def _close(self) -> None:
        self.destroy()
        self._close_cb()
