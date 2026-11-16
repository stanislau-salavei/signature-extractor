"""Settings file: defaults, atomic replace, corrupt fallback."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from signature_extractor.settings.model import default_settings
from signature_extractor.settings.store import SettingsStore


class SettingsStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self._tmp.name)
        self.store = SettingsStore(self.directory)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_file_writes_defaults(self) -> None:
        self.assertFalse(self.store.path.exists())
        loaded = self.store.load()
        self.assertEqual(loaded["theme"], "system")
        self.assertEqual(loaded["language"], "system")
        self.assertFalse(loaded["ai_default"])
        self.assertTrue(loaded["gpu_acceleration"])
        self.assertEqual(loaded["formats"], ["png", "dxf"])
        self.assertEqual(loaded["default_size_id"], "15x5")
        self.assertEqual(loaded["frame_margin_mm"], 2.0)
        self.assertEqual(loaded["default_color"], "blue")
        self.assertEqual(loaded["png_dpi"], 600)
        self.assertEqual(loaded["if_exists"], "add_number")
        self.assertTrue(loaded["check_updates"])
        self.assertIsNone(loaded["save_folder"])
        self.assertIsNone(loaded["name_template"])
        on_disk = json.loads(self.store.path.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["theme"], "system")
        self.assertEqual(on_disk["formats"], ["png", "dxf"])

    def test_round_trip_theme_and_language(self) -> None:
        settings = self.store.load()
        settings["theme"] = "dark"
        settings["language"] = "en"
        self.store.save(settings)
        again = SettingsStore(self.directory).load()
        self.assertEqual(again["theme"], "dark")
        self.assertEqual(again["language"], "en")

    def test_partial_file_keeps_known_values_and_fills_defaults(self) -> None:
        self.store.path.parent.mkdir(parents=True, exist_ok=True)
        self.store.path.write_text('{"theme": "light", "future_flag": true}\n', encoding="utf-8")
        loaded = self.store.load()
        self.assertEqual(loaded["theme"], "light")
        self.assertEqual(loaded["language"], "system")
        on_disk = json.loads(self.store.path.read_text(encoding="utf-8"))
        self.assertTrue(on_disk["future_flag"])
        self.assertEqual(on_disk["png_dpi"], 600)

    def test_invalid_values_fall_back_per_field(self) -> None:
        self.store.path.parent.mkdir(parents=True, exist_ok=True)
        self.store.path.write_text(
            json.dumps({"theme": "purple", "png_dpi": 72, "formats": []}),
            encoding="utf-8",
        )
        loaded = self.store.load()
        self.assertEqual(loaded["theme"], "system")
        self.assertEqual(loaded["png_dpi"], 600)
        self.assertEqual(loaded["formats"], ["png", "dxf"])

    def test_corrupt_file_is_replaced_with_defaults(self) -> None:
        self.store.path.parent.mkdir(parents=True, exist_ok=True)
        for contents in ("{", "", "[]", "null", "not-json"):
            with self.subTest(contents=contents):
                self.store.path.write_text(contents, encoding="utf-8")
                loaded = self.store.load()
                self.assertEqual(loaded["theme"], default_settings()["theme"])
                on_disk = json.loads(self.store.path.read_text(encoding="utf-8"))
                self.assertEqual(on_disk["language"], "system")
                self.assertIsInstance(on_disk, dict)

    def test_replace_uses_a_temp_file_in_the_same_directory(self) -> None:
        seen: dict[str, str] = {}
        real_replace = os.replace

        def spy(src: str, dst: str) -> None:
            seen["src"] = src
            seen["dst"] = dst
            real_replace(src, dst)

        self.store.load()
        with mock.patch("signature_extractor.settings.store.os.replace", spy):
            self.store.save(default_settings())
        self.assertEqual(Path(seen["src"]).parent, Path(seen["dst"]).parent)
        self.assertTrue(Path(seen["src"]).name.startswith(".settings-"))
        self.assertEqual(Path(seen["dst"]), self.store.path)
        self.assertFalse(list(self.directory.glob(".settings-*.tmp")))

    def test_failed_replace_keeps_the_original_document(self) -> None:
        self.store.load()
        settings = default_settings()
        settings["theme"] = "dark"
        self.store.save(settings)
        original = self.store.path.read_text(encoding="utf-8")

        def boom(src: str, dst: str) -> None:
            raise OSError("disk full")

        with mock.patch("signature_extractor.settings.store.os.replace", boom):
            with self.assertRaises(OSError):
                failed = default_settings()
                failed["theme"] = "light"
                self.store.save(failed)
        self.assertEqual(self.store.path.read_text(encoding="utf-8"), original)
        self.assertFalse(list(self.directory.glob(".settings-*.tmp")))
        self.assertIn('"dark"', original)


if __name__ == "__main__":
    unittest.main()
