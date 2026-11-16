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
    accent_text: str
    ctl_stroke: str
    ctl_stroke2: str
    input_bottom: str
    dim: str
    toggle_off: str
    toggle_stroke: str
    toggle_knob: str
    primary_border: str
    primary_bottom: str
    chip_stroke: str
    scroll_thumb: str


LIGHT = Palette(
    bg="#F3F3F3",
    card="#FBFBFB",
    card_border="#E5E5E5",
    drop="#FBFBFB",
    drop_border="#8A8A8A",
    tips="#F6F6F6",
    tips_border="#E5E5E5",
    text="#1A1A1A",
    muted="#5F5F5F",
    accent="#005FB8",
    accent_hover="#004C93",
    on_accent="#FFFFFF",
    # 14% #60CDFF over the panel, not 14% of the light accent.
    accent_soft="#E5F5FC",
    secondary_bg="#FEFEFE",
    secondary_border="#E5E5E5",
    secondary_hover="#F6F6F6",
    stepper_bg="#F3F3F3",
    stepper_border="#E5E5E5",
    stepper_chip="#FFFFFF",
    input_bg="#FFFFFF",
    input_border="#E5E5E5",
    menu_bg="#FFFFFF",
    menu_border="#D0D0D0",
    menu_hover="#F3F3F3",
    divider="#EAEAEA",
    dialog_bg="#FFFFFF",
    dialog_foot="#F3F3F3",
    switch_off="#F6F6F6",
    number_off="#8B8B8B",
    accent_text="#003E92",
    ctl_stroke="#E5E5E5",
    ctl_stroke2="#D3D3D3",
    input_bottom="#8A8A8A",
    dim="#8B8B8B",
    toggle_off="#F6F6F6",
    toggle_stroke="#8A8A8A",
    toggle_knob="#5F5F5F",
    # color-mix(#005FB8 85%, white) / color-mix(#005FB8 80%, black)
    primary_border="#2677C3",
    primary_bottom="#004C93",
    chip_stroke="#D3D3D3",
    # rgba(0,0,0,.48) over #F3F3F3
    scroll_thumb="#7E7E7E",
)

DARK = Palette(
    bg="#202020",
    card="#2B2B2B",
    # white at 8% over the panel
    card_border="#3C3C3C",
    drop="#2B2B2B",
    # white at 28% over the panel (drop dash)
    drop_border="#666666",
    tips="#2B2B2B",
    tips_border="#3C3C3C",
    text="#FFFFFF",
    # white at 79%
    muted="#C9C9C9",
    accent="#60CDFF",
    accent_hover="#8AD8FF",
    on_accent="#000000",
    accent_soft="#33454D",
    secondary_bg="#323232",
    # white at 9% over the control fill
    secondary_border="#444444",
    secondary_hover="#3A3A3A",
    stepper_bg="#272727",
    stepper_border="#3B3B3B",
    stepper_chip="#3A3A3A",
    input_bg="#2E2E2E",
    input_border="#444444",
    menu_bg="#2B2B2B",
    # white at 10% over the dialog
    menu_border="#404040",
    menu_hover="#3A3A3A",
    divider="#3C3C3C",
    dialog_bg="#2B2B2B",
    dialog_foot="#202020",
    switch_off="#272727",
    # white at 60%
    number_off="#999999",
    accent_text="#60CDFF",
    ctl_stroke="#444444",
    # white at 14% over the control / the active step
    ctl_stroke2="#4F4F4F",
    input_bottom="#9A9A9A",
    dim="#999999",
    toggle_off="#272727",
    toggle_stroke="#9A9A9A",
    toggle_knob="#CECECE",
    # color-mix(#60CDFF 85%, white) / color-mix(#60CDFF 80%, black)
    primary_border="#78D4FF",
    primary_bottom="#4DA4CC",
    chip_stroke="#565656",
    # white at 44% over #202020
    scroll_thumb="#828282",
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
