"""Atomic JSON settings at ``%APPDATA%\\Signature Extractor\\settings.json``."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from signature_extractor.paths import settings_directory, settings_path
from signature_extractor.settings.model import coerce_settings, default_settings, merge_for_save

logger = logging.getLogger(__name__)


class SettingsStore:
    """Read and write ``settings.json``.

    A write goes to a temporary file in the same directory and is then
    moved into place with ``os.replace``. If the process stops before the
    replace, the previous document is left intact. A missing or unreadable
    file is replaced with the defaults and does not stop startup.
    """

    def __init__(self, directory: Path | None = None):
        self.directory = directory if directory is not None else settings_directory()
        self.path = self.directory / "settings.json" if directory is not None else settings_path()
        self.extra: dict[str, Any] = {}

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> dict[str, Any]:
        """Return settings, creating or repairing the file when needed."""
        if not self.path.is_file():
            logger.info("settings file is missing, writing defaults: %s", self.path)
            settings = default_settings()
            self.extra = {}
            self.save(settings)
            return settings
        try:
            raw = self._read_json(self.path)
        except (OSError, json.JSONDecodeError, UnicodeError, ValueError) as exc:
            logger.warning("settings file is unreadable (%s), restoring defaults: %s", exc, self.path)
            settings = default_settings()
            self.extra = {}
            self.save(settings)
            return settings
        settings, self.extra = coerce_settings(raw)
        self.save(settings)
        return settings

    def save(self, settings: dict[str, Any]) -> None:
        payload = merge_for_save(settings, self.extra)
        # Keep the in-memory extra map aligned with what was just written.
        _coerced, self.extra = coerce_settings(payload)
        # coerce drops unknown keys into extra; merge again so they stay on disk.
        payload = merge_for_save(settings, self.extra)
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self._atomic_write(self.path, text)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8-sig")
        if not text.strip():
            raise ValueError("empty settings file")
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("settings file is not a JSON object")
        return parsed

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=str(path.parent))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except Exception:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                logger.warning("could not remove temporary settings file %s", tmp_path, exc_info=True)
            raise
