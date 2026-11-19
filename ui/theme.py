"""Theme tokens (mockups v3), fonts and the logical-pixel scale.

All sizes in the UI code are logical pixels at 100 %.  ``S(v)`` converts to device pixels
using the CustomTkinter window scaling (per-monitor DPI), so every custom-drawn element is
re-rendered sharp at 100 / 125 / 150 %.
"""
from __future__ import annotations

import logging
import sys
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable, Dict, List, Tuple

log = logging.getLogger(__name__)


def _hex(c: Tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in c[:3])


def rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def blend(fg: str, alpha: float, base: str) -> str:
    """Colour of ``fg`` with ``alpha`` painted over ``base`` (Tk has no alpha)."""
    f, b = rgb(fg), rgb(base)
    return _hex(tuple(b[i] + (f[i] - b[i]) * alpha for i in range(3)))


W, K = "#FFFFFF", "#000000"

# token: (light, dark)
TOKENS: Dict[str, Tuple[str, str]] = {
    "bg": ("#F3F3F3", "#202020"),
    "card": ("#FBFBFB", "#2B2B2B"),
    "card_stroke": ("#E5E5E5", "#1C1C1C"),
    "card_hover": ("#F6F6F6", "#323232"),
    "drop": ("#FFFFFF", "#2B2B2B"),
    "drop_dash": ("#767676", "#9A9A9A"),
    "tips": ("#F6F6F6", "#2B2B2B"),
    "divider": ("#EAEAEA", blend(W, 0.08, "#2B2B2B")),
    "divider_bg": ("#EAEAEA", blend(W, 0.08, "#202020")),
    "text": ("#1A1A1A", "#FFFFFF"),
    "text_card": ("#1B1B1B", "#FFFFFF"),
    "muted": ("#5F5F5F", "#CFCFCF"),
    "disabled": ("#A0A0A0", "#717171"),
    "accent": ("#005FB8", "#60CDFF"),
    "accent_hover": ("#1A6FC0", "#5BBDEA"),
    "accent_press": ("#3381C9", "#56ADD6"),
    "accent_text": ("#003E92", "#60CDFF"),     # links in tips / «Сбросить»
    "link": ("#005FB8", "#60CDFF"),             # links in «Сведения»
    "on_accent": ("#FFFFFF", "#000000"),
    # remark 37: destructive «Сбросить» button = Windows Terminal reset red #B22222, white text, both themes
    "danger": ("#B22222", "#B22222"),
    "danger_hover": ("#A31F1F", "#BF2E2E"),
    "danger_press": ("#8F1B1B", "#A31F1F"),
    "danger_stroke_top": ("#BD3A3A", "#C24444"),
    "danger_stroke_bottom": ("#8A1A1A", "#8F1B1B"),
    "on_danger": ("#FFFFFF", "#FFFFFF"),
    "accent_stroke_top": (_hex((38, 119, 195)), _hex((120, 212, 255))),
    "accent_stroke_bottom": (_hex((0, 76, 147)), _hex((77, 164, 204))),
    "accent_disabled": ("#BFBFBF", "#434343"),
    # controls (ComboBox, secondary buttons)
    "ctl": ("#FEFEFE", "#373737"),
    "ctl_hover": ("#F6F6F6", "#3C3C3C"),
    "ctl_press": ("#F5F5F5", "#333333"),
    "ctl_stroke": ("#E5E5E5", blend(W, 0.07, "#373737")),
    "ctl_stroke_top": ("#E5E5E5", blend(W, 0.09, "#373737")),
    "ctl_stroke_bottom": ("#D3D3D3", blend(W, 0.07, "#373737")),
    "combo_stroke_bottom": ("#D4D4D4", blend(W, 0.07, "#373737")),
    "ctl_disabled": ("#F5F5F5", "#2F2F2F"),
    # inputs
    "input": ("#FFFFFF", "#373737"),
    "input_hover": ("#F9F9F9", "#3C3C3C"),
    "input_focus": ("#FFFFFF", "#1F1F1F"),
    "input_bottom": ("#8A8A8A", "#9A9A9A"),
    # stepper / segmented
    "seg_track": ("#F3F3F3", "#272727"),
    "seg_track_stroke": ("#E5E5E5", blend(W, 0.09, "#272727")),
    "seg_on": ("#FFFFFF", "#3A3A3A"),
    "seg_on_stroke": ("#D3D3D3", blend(W, 0.14, "#3A3A3A")),
    "seg_hover": ("#EBEBEB", "#2F2F2F"),
    "step_ring": ("#8B8B8B", blend(W, 0.60, "#272727")),
    # menus / popups
    "menu": ("#F9F9F9", "#2C2C2C"),
    "menu_stroke": ("#E0E0E0", blend(W, 0.10, "#2C2C2C")),
    "menu_hover": ("#F0F0F0", blend(W, 0.06, "#2C2C2C")),
    "menu_sel": (blend(K, 0.055, "#F9F9F9"), blend(W, 0.06, "#2C2C2C")),
    "menu_sep": ("#E5E5E5", blend(W, 0.08, "#2C2C2C")),
    # radio / checkbox / toggle
    "check_off_stroke": ("#8A8A8A", "#9A9A9A"),
    "check_off_fill": ("#F5F5F5", "#272727"),
    "check_off_hover": ("#ECECEC", "#2F2F2F"),
    "toggle_off_fill": ("#F6F6F6", "#272727"),
    "toggle_off_stroke": ("#8A8A8A", "#9A9A9A"),
    "toggle_off_knob": ("#5F5F5F", "#CECECE"),
    # scrollbar
    "scroll_thumb": ("#8A8A8A", "#9A9A9A"),
    "scroll_track": ("#F9F9F9", "#2C2C2C"),
    # toolbar
    "tool_hover": ("#F0F0F0", "#323232"),
    "tool_on": ("#FFFFFF", "#3A3A3A"),
    "tool_on_stroke": ("#D3D3D3", blend(W, 0.14, "#3A3A3A")),
    "vsep": ("#E5E5E5", "#1C1C1C"),
    # slider
    "slider_rail": ("#8A8A8A", "#9A9A9A"),
    "slider_thumb": ("#FFFFFF", "#454545"),
    "slider_thumb_stroke": ("#E5E5E5", "#505050"),
    # dialogs
    "dialog": ("#FFFFFF", "#2B2B2B"),
    "dialog_foot": ("#F3F3F3", "#202020"),
    "dialog_stroke": ("#D0D0D0", "#404040"),
    "smoke": ("#000000", "#000000"),
    # misc
    "tooltip": ("#F9F9F9", "#2C2C2C"),
    "tooltip_stroke": ("#E0E0E0", blend(W, 0.10, "#2C2C2C")),
    "error_bg": ("#FDE7E9", "#442726"),
    "error_stroke": ("#D8ADA9", "#5A3A39"),
    "error_icon": ("#C42B1C", "#FF99A4"),
    "success": ("#0F7B0F", "#6CCB5F"),
    "accent_soft_drop": (blend("#60CDFF", 0.14, "#FFFFFF"), blend("#60CDFF", 0.14, "#2B2B2B")),
    "drop_over": (blend("#005FB8", 0.06, "#FFFFFF"), blend("#60CDFF", 0.06, "#2B2B2B")),
    "preview_border": ("#E5E5E5", "#1C1C1C"),
    "abar": ("#F3F3F3", "#202020"),
    "abar_line": ("#EAEAEA", blend(W, 0.08, "#202020")),
    "swatch_stroke": ("#E5E5E5", blend(W, 0.09, "#2B2B2B")),
    # stage 4 (batch): InfoBars 38–46, strip 14, progress 17 — values from the v3 mockups
    "warn_bg": ("#FFF4CE", "#433519"),
    "warn_stroke": ("#F0CD70", blend(W, 0.08, "#433519")),
    "ok_bg": ("#DFF6DD", "#393D1B"),
    "ok_stroke": ("#A6C4A6", blend(W, 0.08, "#393D1B")),
    "badge_ok": ("#0F7B0F", "#0F7B0F"),
    "badge_warn": ("#FFB900", "#FFB900"),
    "badge_warn_text": ("#4D3A00", "#4D3A00"),
    "dpi_dot": ("#8A8A8A", "#8A8A8A"),
    "thumb": ("#FEFEFE", "#2B2B2B"),
    "chip": ("#F3F3F3", blend(W, 0.08, "#2B2B2B")),
    "progress_track": ("#E5E5E5", blend(W, 0.09, "#202020")),
}


class Theme:
    """Current appearance; widgets register a refresh callback."""

    mode = "light"
    _subs: List[Callable[[], None]] = []

    @classmethod
    def dark(cls) -> bool:
        return cls.mode == "dark"

    @classmethod
    def c(cls, token: str) -> str:
        if token.startswith("#"):
            return token
        pair = TOKENS[token]
        return pair[1] if cls.mode == "dark" else pair[0]

    @classmethod
    def set_mode(cls, mode: str) -> bool:
        mode = "dark" if mode == "dark" else "light"
        if mode == cls.mode:
            return False
        cls.mode = mode
        return True


# --------------------------------------------------------------------------- scale
class Scale:
    factor = 1.0


def S(v: float) -> int:
    """Logical px -> device px (rounded)."""
    return int(round(v * Scale.factor))


def Sf(v: float) -> float:
    return v * Scale.factor


# --------------------------------------------------------------------------- fonts
class Fonts:
    regular_family = "Segoe UI"
    semibold_family = None      # separate Semibold family (Windows), else bold weight
    medium_family = None
    _cache: Dict[Tuple, tkfont.Font] = {}
    _root = None

    @classmethod
    def init(cls, root: tk.Misc) -> None:
        cls._root = root
        fams = set(tkfont.families(root))
        order = ["Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI"]
        if not sys.platform.startswith("win"):
            # Linux test runs: the mockups were rendered with Inter (Segoe UI is not installed)
            order = ["Segoe UI Variable Text", "Segoe UI", "Inter", "Selawik", "Noto Sans"]
        cls.regular_family = next((f for f in order if f in fams), "TkDefaultFont")
        semi = ["Segoe UI Variable Text Semibold", "Segoe UI Variable Semibold", "Segoe UI Semibold",
                "Inter SemiBold", "Inter Semibold", "Selawik Semibold"]
        cls.semibold_family = next((f for f in semi if f in fams), None)
        cls.medium_family = None
        import os
        if os.environ.get("SE_FONT_ALIASES") and cls.regular_family == "Inter":
            # dev/test on Linux: fontconfig aliases (tools/fonts.conf) give true 600 / 500 weights
            cls.semibold_family, cls.medium_family = "Inter SemiBold", "Inter Medium"
        elif sys.platform.startswith("win"):
            med = ["Segoe UI Variable Text Semibold"]  # Segoe has no Medium in GDI; 500 -> regular
            cls.medium_family = None
        log.info("fonts: %s / %s", cls.regular_family, cls.semibold_family or "bold")
        cls._cache.clear()

    @classmethod
    def get(cls, px: float, weight: str = "normal") -> tkfont.Font:
        size = max(1, int(px * Scale.factor + 0.5))
        key = (size, weight)
        f = cls._cache.get(key)
        if f is None:
            if weight in ("semibold", "bold"):
                if cls.semibold_family and weight == "semibold":
                    f = tkfont.Font(root=cls._root, family=cls.semibold_family, size=-size)
                else:
                    f = tkfont.Font(root=cls._root, family=cls.regular_family, size=-size, weight="bold")
            elif weight == "mono":
                f = tkfont.Font(root=cls._root, family=cls.mono_family(), size=-size)
            elif weight == "medium":
                fam = cls.medium_family or cls.regular_family
                f = tkfont.Font(root=cls._root, family=fam, size=-size)
            else:
                f = tkfont.Font(root=cls._root, family=cls.regular_family, size=-size)
            cls._cache[key] = f
        return f

    _mono = None

    @classmethod
    def mono_family(cls) -> str:
        """Template chip on 16 (mockup: Cascadia Mono, Segoe UI Mono, Consolas, monospace)."""
        if cls._mono is None:
            fams = set(tkfont.families(cls._root))
            cls._mono = next((f for f in ("Cascadia Mono", "Segoe UI Mono", "Consolas", "DejaVu Sans Mono",
                                          "Liberation Mono", "Noto Sans Mono") if f in fams), "TkFixedFont")
        return cls._mono

    @classmethod
    def clear(cls) -> None:
        cls._cache.clear()


def F(px: float, weight: str = "normal") -> tkfont.Font:
    return Fonts.get(px, weight)


def text_width(text: str, px: float, weight: str = "normal") -> float:
    """Logical width of a text run."""
    return F(px, weight).measure(text) / Scale.factor


def elide(text: str, width: float, px: float, weight: str = "normal") -> str:
    """Shorten ``text`` with «…» so it fits ``width`` (real font metrics)."""
    if text_width(text, px, weight) <= width:
        return text
    while text and text_width(text.rstrip(" ,·") + "…", px, weight) > width:
        text = text[:-1]
    return text.rstrip(" ,·") + "…"
