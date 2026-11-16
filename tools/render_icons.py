"""Render the approved SVGs to PNGs so the app does not need Cairo at runtime.

``currentColor`` is replaced with each UI colour. App icons keep their own paints.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cairosvg

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "signature_extractor" / "assets" / "icons"
OUT = SRC / "png"
SIZE = 96

COLOURS = ("1A1A1A", "FFFFFF", "5F5F5F", "C9C9C9", "005FB8", "60CDFF", "000000")
OWN_PAINT = {"app_icon_16.svg", "app_icon_32.svg"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for path in sorted(SRC.glob("*.svg")):
        text = path.read_text(encoding="utf-8")
        if path.name in OWN_PAINT:
            png = OUT / f"{path.stem}.png"
            cairosvg.svg2png(
                bytestring=text.encode("utf-8"),
                write_to=str(png),
                output_width=SIZE,
                output_height=SIZE,
            )
            continue
        for colour in COLOURS:
            painted = text.replace("currentColor", f"#{colour}")
            png = OUT / f"{path.stem}__{colour}.png"
            cairosvg.svg2png(
                bytestring=painted.encode("utf-8"),
                write_to=str(png),
                output_width=SIZE,
                output_height=SIZE,
            )
    print(f"wrote {len(list(OUT.glob('*.png')))} pngs")


if __name__ == "__main__":
    sys.exit(main())
