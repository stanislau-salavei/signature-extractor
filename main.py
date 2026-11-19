"""Извлечение подписи / Signature Extractor — entry point.

Usage: python main.py [--installer-language ru|en] [files or folders ...]
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    from core.logs import setup_logging
    path = setup_logging()                    # remark 81: %APPDATA%\Signature Extractor\signature_extractor.log
    log = logging.getLogger("main")
    log.info("start, log %s", path)
    from ui.app import App
    app = App(argv)
    files = [Path(a) for a in argv if not a.startswith("--") and a not in ("ru", "en")]
    if files:
        app.root.after(200, lambda: app.open_paths(files))
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
