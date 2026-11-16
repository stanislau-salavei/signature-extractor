"""Windows 11 colours used by the approved mockups.

Light window background ``#F3F3F3``, accent ``#005FB8``.
Dark window background ``#202020``, cards ``#2B2B2B``, accent ``#60CDFF``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    bg: str
    card: str
    card_border: str
    drop: str
    drop_border: str
    tips: str
    tips_border: str
    text: str
    muted: str
    accent: str
    accent_hover: str
    on_accent: str
    accent_soft: str
    secondary_bg: str
    secondary_border: str
    secondary_hover: str
    stepper_bg: str
    stepper_border: str
    stepper_chip: str
    input_bg: str
    input_border: str
    menu_bg: str
    menu_border: str
    menu_hover: str
    divider: str
    dialog_bg: str
    dialog_foot: str
    switch_off: str
    number_off: str


LIGHT = Palette(
    bg="#F3F3F3",
    card="#FBFBFB",
    card_border="#E5E5E5",
    drop="#FBFBFB",
    drop_border="#C4C4C4",
    tips="#F6F6F6",
    tips_border="#E5E5E5",
    text="#1A1A1A",
    muted="#616161",
    accent="#005FB8",
    accent_hover="#004C93",
    on_accent="#FFFFFF",
    accent_soft="#E5F4FB",
    secondary_bg="#FFFFFF",
    secondary_border="#D6D6D6",
    secondary_hover="#F5F5F5",
    stepper_bg="#F3F3F3",
    stepper_border="#E5E5E5",
    stepper_chip="#FFFFFF",
    input_bg="#FFFFFF",
    input_border="#D6D6D6",
    menu_bg="#FFFFFF",
    menu_border="#E5E5E5",
    menu_hover="#F3F3F3",
    divider="#E5E5E5",
    dialog_bg="#FFFFFF",
    dialog_foot="#F3F3F3",
    switch_off="#E5E5E5",
    number_off="#6B6B6B",
)

DARK = Palette(
    bg="#202020",
    card="#2B2B2B",
    card_border="#3D3D3D",
    drop="#2B2B2B",
    drop_border="#5A5A5A",
    tips="#2B2B2B",
    tips_border="#3D3D3D",
    text="#FFFFFF",
    muted="#ADADAD",
    accent="#60CDFF",
    accent_hover="#8AD8FF",
    on_accent="#1A1A1A",
    accent_soft="#33454D",
    secondary_bg="#323232",
    secondary_border="#4A4A4A",
    secondary_hover="#3A3A3A",
    stepper_bg="#272727",
    stepper_border="#3A3A3A",
    stepper_chip="#3A3A3A",
    input_bg="#2B2B2B",
    input_border="#4A4A4A",
    menu_bg="#2C2C2C",
    menu_border="#3F3F3F",
    menu_hover="#3A3A3A",
    divider="#3F3F3F",
    dialog_bg="#2B2B2B",
    dialog_foot="#202020",
    switch_off="#5A5A5A",
    number_off="#9A9A9A",
)


def pair(name: str) -> tuple[str, str]:
    """``(light, dark)`` colour pair for a CustomTkinter property."""
    return (getattr(LIGHT, name), getattr(DARK, name))


def current_palette() -> Palette:
    try:
        import customtkinter as ctk

        mode = (ctk.get_appearance_mode() or "Light").lower()
    except Exception:
        mode = "light"
    return DARK if mode == "dark" else LIGHT


def apply_appearance_mode(mode: str) -> None:
    import customtkinter as ctk

    if mode not in ("system", "light", "dark"):
        mode = "system"
    ctk.set_appearance_mode(mode)


# Column cap. At 1280 px with 56 px gutters the mockup content is 1168 px wide.
# The common spec's "about 1000 px" cap is applied from this width upward so a
# maximized window keeps the settings column centred instead of stretching.
CONTENT_MAX_WIDTH = 1168
CONTENT_SIDE_PADDING = 56

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800
WINDOW_MIN_WIDTH = 1024
WINDOW_MIN_HEIGHT = 680

HEADER_HEIGHT = 64
SETTINGS_HEADER_HEIGHT = 80

COPYRIGHT = "© 2026 Stanislau Salavei"
LICENSE_NAME = "GNU GPLv3"

URL_SOURCE = "https://github.com/stanislau-salavei/signature-extractor"
URL_RELEASES = "https://github.com/stanislau-salavei/signature-extractor/releases"
URL_RELEASE_NOTES = "https://github.com/stanislau-salavei/signature-extractor/releases/tag/v1.0.0"
URL_ISSUES = "https://github.com/stanislau-salavei/signature-extractor/issues/new"
URL_GPL = "https://www.gnu.org/licenses/gpl-3.0.html"

COLOR_SWATCHES = {
    "as_photo": None,
    "black": "#000000",
    "blue": "#1B2A8A",
    "ink_blue": "#0B1F5C",
    "bright_blue": "#1D3FBF",
}
