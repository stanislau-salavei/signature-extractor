"""Remark 81: the log file %APPDATA%\\Signature Extractor\\signature_extractor.log (rotating, UTF-8).

Every caught error is written there (``log.debug`` for expected ones, ``log.warning`` / ``log.exception`` for
real failures); the app's own loggers (``core.*``, ``ui.*``, ``main``) go to the file from DEBUG, other
libraries from WARNING.  Uncaught errors of the main thread, worker threads and Tk callbacks are logged too.
The windowed exe has no console, so stderr is used only when there is one."""
from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from core.settings import get_app_data_dir

LOG_NAME = "signature_extractor.log"
MAX_BYTES = 1_000_000          # ~1 MB per file
BACKUPS = 3                    # signature_extractor.log.1 … .3
FORMAT = "%(asctime)s %(levelname)s %(name)s [%(threadName)s]: %(message)s"
OWN = ("core", "ui", "main", "__main__")

_handler: Optional[RotatingFileHandler] = None


def log_path(app_dir: Optional[Path] = None) -> Path:
    if app_dir is None:
        app_dir = get_app_data_dir()
    return Path(app_dir) / LOG_NAME


def setup_logging(app_dir: Optional[Path] = None) -> Path:
    """Attach the rotating file handler (once per process) and the hooks for uncaught errors."""
    global _handler
    path = log_path(app_dir)
    root = logging.getLogger()
    if _handler is not None:
        root.removeHandler(_handler)
        _handler.close()
    root.setLevel(logging.WARNING)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _handler = RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8", delay=True)
        _handler.setFormatter(logging.Formatter(FORMAT))
        _handler.setLevel(logging.DEBUG)
        root.addHandler(_handler)
    except OSError:
        _handler = None
        logging.getLogger(__name__).warning("cannot open the log file %s", path, exc_info=True)
    if sys.stderr is not None and not any(type(h) is logging.StreamHandler for h in root.handlers):
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter(FORMAT))
        sh.setLevel(logging.INFO)
        root.addHandler(sh)
    for name in OWN:
        logging.getLogger(name).setLevel(logging.DEBUG)
    _install_hooks()
    return path


def _install_hooks() -> None:
    log = logging.getLogger("main")

    def excepthook(tp, val, tb):
        log.critical("uncaught error", exc_info=(tp, val, tb))

    def thread_hook(args):
        log.error("uncaught error in thread %s", getattr(args.thread, "name", "?"),
                  exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    sys.excepthook = excepthook
    threading.excepthook = thread_hook


def tk_callback_error(tp, val, tb) -> None:
    """Tk's report_callback_exception: an error in a button / timer callback goes to the log."""
    logging.getLogger("ui").error("error in a Tk callback", exc_info=(tp, val, tb))
