"""Line icons drawn to match the mockup strokes. Both theme colours are kept."""

from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw

from signature_extractor.ui.theme import DARK, LIGHT

_NAMES = (
    "upload",
    "image",
    "folder",
    "dots",
    "gear",
    "help",
    "info",
    "back",
    "chevron_down",
    "chevron_up",
    "theme",
    "globe",
    "sparkles",
    "monitor",
    "layers",
    "size",
    "crop",
    "drop",
    "type",
    "files",
    "refresh",
)


def pil_icon(name: str, size: int, role: str, palette) -> Image.Image:
    """A single-theme PIL image, for Tk widgets that cannot take a CTkImage."""
    return _render(name, size, _role_color(palette, role)).copy()


def icon_image(name: str, size: int, role: str = "text"):
    """CustomTkinter image that follows the light and dark theme."""
    import customtkinter as ctk

    light = _render(name, size, _role_color(LIGHT, role))
    dark = _render(name, size, _role_color(DARK, role))
    return ctk.CTkImage(light_image=light, dark_image=dark, size=(size, size))


def _role_color(palette, role: str) -> str:
    return {
        "text": palette.text,
        "muted": palette.muted,
        "accent": palette.accent,
        "on_accent": palette.on_accent,
    }[role]


@lru_cache(maxsize=256)
def _render(name: str, size: int, color: str) -> Image.Image:
    scale = 4
    canvas = 24 * scale
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pen = max(2, int(round(1.7 * scale)))
    _draw(name, draw, scale, pen, color)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def _gear(draw: ImageDraw.ImageDraw, scale: int, pen: int, color: str) -> None:
    """Eight-tooth cog. The old tick marks read as a dotted sun at 16 px."""
    import math

    center = 12 * scale
    teeth = 8
    points: list[tuple[float, float]] = []
    for index in range(teeth):
        base = math.radians(index * (360 / teeth) - 90)
        for delta, radius in ((-0.22, 6.4), (-0.11, 9.4), (0.11, 9.4), (0.22, 6.4)):
            angle = base + delta
            points.append((center + radius * scale * math.cos(angle), center + radius * scale * math.sin(angle)))
    draw.line(points + [points[0]], fill=color, width=pen, joint="curve")
    hole = 2.6 * scale
    draw.ellipse((center - hole, center - hole, center + hole, center + hole), outline=color, width=pen)


def _draw(name: str, draw: ImageDraw.ImageDraw, scale: int, pen: int, color: str) -> None:
    def xy(*points: tuple[float, float]) -> list[tuple[float, float]]:
        return [(x * scale, y * scale) for x, y in points]

    def line(*points: tuple[float, float]) -> None:
        draw.line(xy(*points), fill=color, width=pen)

    def arc(box: tuple[float, float, float, float], start: float, extent: float) -> None:
        x1, y1, x2, y2 = box
        draw.arc(xy((x1, y1), (x2, y2)), start=start, end=start + extent, fill=color, width=pen)

    def ellipse(box: tuple[float, float, float, float], fill: str | None = None) -> None:
        x1, y1, x2, y2 = box
        draw.ellipse(xy((x1, y1), (x2, y2)), outline=None if fill else color, fill=fill, width=pen)

    def round_rect(box: tuple[float, float, float, float], radius: float) -> None:
        x1, y1, x2, y2 = box
        draw.rounded_rectangle(xy((x1, y1), (x2, y2)), radius=radius * scale, outline=color, width=pen)

    if name == "upload":
        line((12, 16), (12, 4))
        line((7, 9), (12, 4), (17, 9))
        line((4, 16), (4, 19), (20, 19), (20, 16))
    elif name == "image":
        round_rect((3, 3, 21, 21), 3)
        ellipse((7, 7, 11, 11))
        line((21, 15), (16, 10), (5, 21))
    elif name == "folder":
        line((3, 8), (3, 19), (21, 19), (21, 9), (11, 9), (9, 6), (5, 6), (3, 8))
    elif name == "dots":
        for center in (6, 12, 18):
            ellipse((center - 1.3, 10.7, center + 1.3, 13.3), fill=color)
    elif name == "gear":
        _gear(draw, scale, pen, color)
    elif name == "help":
        ellipse((3, 3, 21, 21))
        arc((8, 6.5, 16, 13), 200, 280)
        line((12, 13), (12, 15.5))
        ellipse((11.1, 17.6, 12.9, 19.4), fill=color)
    elif name == "info":
        ellipse((3, 3, 21, 21))
        line((12, 11), (12, 17))
        ellipse((11.1, 6.6, 12.9, 8.4), fill=color)
    elif name == "back":
        line((20, 12), (5, 12))
        line((12, 6), (5, 12), (12, 18))
    elif name == "chevron_down":
        line((6, 9), (12, 15), (18, 9))
    elif name == "chevron_up":
        line((6, 15), (12, 9), (18, 15))
    elif name == "theme":
        ellipse((3, 3, 21, 21))
        draw.pieslice(xy((3, 3), (21, 21)), start=90, end=270, fill=color)
    elif name == "globe":
        ellipse((3, 3, 21, 21))
        line((3, 12), (21, 12))
        arc((8, 3, 16, 21), 270, 180)
        arc((8, 3, 16, 21), 90, 180)
    elif name == "sparkles":
        line((12, 3), (13.2, 8.4), (19, 10), (13.2, 11.6), (12, 17), (10.8, 11.6), (5, 10), (10.8, 8.4), (12, 3))
        line((19, 16), (19.6, 18), (21.5, 18.7), (19.6, 19.4), (19, 21.4), (18.4, 19.4), (16.5, 18.7), (18.4, 18), (19, 16))
    elif name == "monitor":
        round_rect((2, 4, 22, 16), 2)
        line((12, 16), (12, 20))
        line((7, 20), (17, 20))
    elif name == "layers":
        line((12, 3), (21, 8), (12, 13), (3, 8), (12, 3))
        line((3, 12), (12, 17), (21, 12))
    elif name == "size":
        round_rect((3, 6, 21, 18), 1)
        line((7, 10), (17, 10))
        line((7, 14), (13, 14))
    elif name == "crop":
        line((6, 3), (6, 16), (19, 16))
        line((18, 21), (18, 8), (5, 8))
    elif name == "drop":
        # Teardrop: point on top, round bottom.
        line((12, 3), (7, 12), (7, 15), (9, 19), (12, 21), (15, 19), (17, 15), (17, 12), (12, 3))
    elif name == "type":
        line((6, 5), (18, 5))
        line((12, 5), (12, 19))
        line((8, 19), (16, 19))
    elif name == "files":
        line((8, 3), (15, 3), (20, 8), (20, 19), (8, 19), (8, 3))
        line((15, 3), (15, 8), (20, 8))
        line((4, 8), (4, 21), (15, 21))
    elif name == "refresh":
        arc((4, 4, 20, 20), 40, 280)
        line((18, 4), (20, 8), (16, 9))
    else:
        ellipse((4, 4, 20, 20))
