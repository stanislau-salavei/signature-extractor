"""Capture screen 1 and Settings in both themes for visual comparison.

Run on a display (on Linux: ``xvfb-run -s "-screen 0 1680x1900x24" python tools/capture_stage1.py``).
Screenshots are written to the directory given by ``--out`` (default: ./artifacts).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

# Headless runs must create the display before Tk is imported.
os.environ.setdefault("SIGNATURE_EXTRACTOR_CAPTURE", "1")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    tmp = tempfile.TemporaryDirectory()
    os.environ["APPDATA"] = tmp.name

    from signature_extractor.controller.state import AppController
    from signature_extractor.i18n.loader import load_catalog
    from signature_extractor.settings.store import SettingsStore
    from signature_extractor.ui.window import MainWindow

    store = SettingsStore()
    settings = store.load()
    settings["language"] = "ru"
    settings["theme"] = "light"
    store.save(settings)
    window = MainWindow(AppController(settings, store, load_catalog()))
    window.update()

    def shoot(name: str) -> None:
        window.update_idletasks()
        window.update()
        _grab(window, out / name)
        print("wrote", out / name)

    window.geometry("1280x800+40+20")
    window.apply_state()
    shoot("screen1_light_ru.png")

    window.controller.set_theme("dark")
    window.geometry("1280x800+40+20")
    window.update()
    shoot("screen1_dark_ru.png")

    window.controller.set_theme("light")
    window.controller.open_settings()
    window.geometry("1280x1860+20+10")
    window.update()
    shoot("settings_light_ru.png")

    window.controller.set_theme("dark")
    window.geometry("1280x1860+20+10")
    window.update()
    shoot("settings_dark_ru.png")

    window.controller.set_language_mode("en")
    window.controller.set_theme("light")
    window.controller.close_overlay()
    window.geometry("1280x800+40+20")
    window.update()
    shoot("screen1_light_en.png")

    window.destroy()
    tmp.cleanup()


def _grab(window, path: Path) -> None:
    import mss
    from mss.tools import to_png

    x = window.winfo_rootx()
    y = window.winfo_rooty()
    width = window.winfo_width()
    height = window.winfo_height()
    with mss.MSS() as sct:
        shot = sct.grab({"left": x, "top": y, "width": width, "height": height})
        to_png(shot.rgb, shot.size, output=str(path))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
