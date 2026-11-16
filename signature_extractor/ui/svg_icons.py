"""Approved SVG icons, pre-rendered to PNG (see tools/render_icons.py).

CustomTkinter gets a light and a dark image and scales them to the logical
size, so a 125% or 150% display stays sharp.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageTk

PNG = Path(__file__).resolve().parents[1] / "assets" / "icons" / "png"

# role -> (light hex, dark hex) without '#'
ROLES = {
    "text": ("1A1A1A", "FFFFFF"),
    "muted": ("5F5F5F", "C9C9C9"),
    "accent": ("005FB8", "60CDFF"),
    "on_accent": ("FFFFFF", "000000"),
}


@lru_cache(maxsize=256)
def _open(name: str, colour: str | None) -> Image.Image:
    if colour is None:
        path = PNG / f"{name}.png"
    else:
        # #1B1B1B is one step from the rendered #1A1A1A plates.
        colour = {"1B1B1B": "1A1A1A"}.get(colour.upper(), colour.upper())
        path = PNG / f"{name}__{colour}.png"
    return Image.open(path).convert("RGBA")


def svg_image(name: str, size: int, role: str = "text") -> ctk.CTkImage:
    if name in {"app_icon_16", "app_icon_32"}:
        image = _open(name, None)
        return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
    light, dark = ROLES[role]
    return ctk.CTkImage(
        light_image=_open(name, light),
        dark_image=_open(name, dark),
        size=(size, size),
    )


def svg_photo(master, name: str, size: int, colour: str):
    """Tk PhotoImage for a canvas window, at ``size`` physical pixels."""
    image = _open(name, colour.lstrip("#").upper()).resize((size, size), Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(image, master=master)
    return photo
