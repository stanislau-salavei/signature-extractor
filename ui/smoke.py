"""Stage 6: start-up self-check of the built program (GitHub Actions, after PyInstaller).

``SE_SMOKE_REPORT=<file.json> SignatureExtractor.exe`` opens the window as usual, about 2 s later writes a
report (version, frozen, drag and drop, HEIC, OpenCV, files of the onedir build) and closes the window
without saving its size.  Without the variable nothing happens."""
from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)
ENV = "SE_SMOKE_REPORT"


def report(app) -> dict:
    from ui import app as A
    out = {"version": A.VERSION, "frozen": bool(getattr(sys, "frozen", False)),
           "dnd": bool(getattr(app.root, "dnd_ok", False)), "language": app.i18n.lang,
           "title": app.root.title(), "assets": (A.ROOT_DIR / "assets" / "app.ico").exists(),
           "i18n": (A.ROOT_DIR / "i18n" / "strings_ru_en.csv").exists()}
    try:
        import cv2
        out["opencv"] = cv2.__version__
    except Exception as exc:                           # pragma: no cover - reported, not raised
        log.error("smoke: opencv failed", exc_info=True)
        out["opencv"] = f"error: {exc}"
    try:
        from PIL import Image
        from core import processing as P
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "smoke.heic"
            Image.new("RGB", (64, 48), (250, 250, 250)).save(p)
            img, _dpi = P.load_image(p)                # pillow-heif writes and reads HEIC
            out["heic"] = list(img.size)
    except Exception as exc:
        log.error("smoke: heic failed", exc_info=True)
        out["heic"] = f"error: {exc}"
    try:
        from PIL import Image, ImageTk
        ph = ImageTk.PhotoImage(Image.new("RGBA", (8, 8), (0, 0, 0, 255)), master=app.root)
        out["imagetk"] = [ph.width(), ph.height()]
    except Exception as exc:
        log.error("smoke: imagetk failed", exc_info=True)
        out["imagetk"] = f"error: {exc}"
    try:
        import potrace  # noqa: F401
        import ezdxf
        out["ezdxf"] = ezdxf.__version__
    except Exception as exc:
        log.error("smoke: ezdxf failed", exc_info=True)
        out["ezdxf"] = f"error: {exc}"
    out["log_errors"] = _log_errors()
    out["ok"] = bool(out["log_errors"] == 0 and isinstance(out["imagetk"], list) and out["assets"] and out["i18n"] and out["dnd"] and isinstance(out["heic"], list)
                     and not str(out["opencv"]).startswith("error") and not str(out["ezdxf"]).startswith("error"))
    return out


def _log_errors() -> int:
    """ERROR / CRITICAL lines in the log of this launch (the file is rotated at 1 MB, so count all)."""
    n = 0
    for h in logging.getLogger().handlers:
        name = getattr(h, "baseFilename", None)
        if name and Path(name).exists():
            h.flush()
            text = Path(name).read_text(encoding="utf-8", errors="replace")
            n += sum(1 for line in text.splitlines() if " ERROR " in line or " CRITICAL " in line)
    return n


def maybe_schedule(app, delay_ms: int = 2000) -> bool:
    target = os.environ.get(ENV)
    if not target:
        return False

    def run():
        try:
            data = report(app)
        except Exception as exc:
            log.exception("smoke report failed")
            data = {"ok": False, "error": repr(exc)}
        Path(target).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        app.root.destroy()
    app.root.after(delay_ms, run)
    return True
