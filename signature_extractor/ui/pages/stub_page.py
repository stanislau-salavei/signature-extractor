"""Placeholder bodies for the processing and export steps.

Stage 2 and stage 3 replace these. The shell (stepper, ⋯ menu) stays on
the window, so these frames only reserve the content area and the bottom bar.
"""

from __future__ import annotations

import customtkinter as ctk


class StubPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.bottom = ctk.CTkFrame(self, fg_color="transparent", height=64)
        self.bottom.grid(row=1, column=0, sticky="ew")
        self.bottom.grid_propagate(False)
