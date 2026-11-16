"""Initial UI language for the first launch.

Stage 6's installer (Inno Setup, Russian or English) is the source of the
language the first time ``settings.json`` does not exist yet. The installer
does not write ``settings.json`` — updates and uninstall leave that file
alone — so the language is passed beside it:

1. Command line ``--installer-language ru`` or ``--installer-language en``
   (the installer can pass this when it starts the app after setup).
2. Environment variable ``SIGNATURE_EXTRACTOR_INSTALLER_LANGUAGE`` with the
   same values. Useful for tests; the installer does not have to set it.
3. A text file ``installer_language.txt`` in the install directory (next to
   the executable, or the repository root when running from source) whose
   contents are ``ru`` or ``en``.

Accepted aliases, so an Inno language name can be written as-is:
``ru``, ``russian``, ``en``, ``english``.

When none of these is present, the first settings file uses
"use system language".
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from signature_extractor.paths import INSTALLER_LANGUAGE_FILE_NAME, install_dir

ENV_VAR = "SIGNATURE_EXTRACTOR_INSTALLER_LANGUAGE"

_ALIASES = {
    "ru": "ru",
    "russian": "ru",
    "ru-ru": "ru",
    "en": "en",
    "english": "en",
    "en-us": "en",
    "en-gb": "en",
}


def normalize_language_token(value: str | None) -> str | None:
    if value is None:
        return None
    token = value.strip().lower().replace("_", "-")
    return _ALIASES.get(token)


def read_installer_language(argv: list[str] | None = None, directory: Path | None = None) -> str | None:
    """Return ``ru`` or ``en`` from the installer hook, or None."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--installer-language", dest="installer_language")
    known, _rest = parser.parse_known_args(argv if argv is not None else [])
    from_args = normalize_language_token(known.installer_language)
    if from_args:
        return from_args
    from_env = normalize_language_token(os.environ.get(ENV_VAR))
    if from_env:
        return from_env
    folder = directory if directory is not None else install_dir()
    file_path = folder / INSTALLER_LANGUAGE_FILE_NAME
    if file_path.is_file():
        try:
            contents = file_path.read_text(encoding="utf-8")
        except OSError:
            return None
        return normalize_language_token(contents.splitlines()[0] if contents.strip() else "")
    return None
