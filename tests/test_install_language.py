"""Installer language hook used on the first launch."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from signature_extractor.settings.install_language import ENV_VAR, read_installer_language


class InstallerLanguageTests(unittest.TestCase):
    def test_command_line_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "installer_language.txt"
            path.write_text("en\n", encoding="utf-8")
            found = read_installer_language(["--installer-language", "ru"], Path(tmp))
        self.assertEqual(found, "ru")

    def test_environment_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            previous = os.environ.get(ENV_VAR)
            os.environ[ENV_VAR] = "english"
            try:
                self.assertEqual(read_installer_language([], folder), "en")
            finally:
                if previous is None:
                    os.environ.pop(ENV_VAR, None)
                else:
                    os.environ[ENV_VAR] = previous
            (folder / "installer_language.txt").write_text("russian\n", encoding="utf-8")
            self.assertEqual(read_installer_language([], folder), "ru")

    def test_missing_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.environ.pop(ENV_VAR, None)
            try:
                self.assertIsNone(read_installer_language([], Path(tmp)))
            finally:
                if previous is not None:
                    os.environ[ENV_VAR] = previous

    def test_unknown_token_is_ignored(self) -> None:
        self.assertIsNone(read_installer_language(["--installer-language", "de"]))


if __name__ == "__main__":
    unittest.main()
