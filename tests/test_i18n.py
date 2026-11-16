"""String catalog: every key in both languages, plurals, placeholders."""

from __future__ import annotations

import unittest

from signature_extractor.i18n.loader import load_catalog
from signature_extractor.i18n.plurals import RU_FORMS
from signature_extractor.paths import strings_csv_path


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_catalog(strings_csv_path())

    def test_all_keys_have_russian_and_english(self) -> None:
        keys = self.catalog.keys()
        self.assertEqual(len(keys), 293)
        self.assertEqual(len(set(keys)), 293)
        for key in keys:
            russian = self.catalog.text(key, "ru")
            english = self.catalog.text(key, "en")
            self.assertTrue(russian.strip(), key)
            self.assertTrue(english.strip(), key)

    def test_import_step_is_import_in_english(self) -> None:
        self.assertEqual(self.catalog.text("shell.step.import", "ru"), "Загрузка")
        self.assertEqual(self.catalog.text("shell.step.import", "en"), "Import")

    def test_language_names_are_not_translated(self) -> None:
        self.assertEqual(self.catalog.text("settings.language.ru", "en"), "Русский")
        self.assertEqual(self.catalog.text("settings.language.en", "ru"), "English")

    def test_unknown_key_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.catalog.text("not.a.real.key", "ru")

    def test_template_tokens_are_left_in_place(self) -> None:
        self.assertIn("{имя}", self.catalog.text("settings.name_template.desc", "ru"))
        self.assertIn("{дата}", self.catalog.text("settings.name_template.desc", "ru"))
        self.assertIn("{name}", self.catalog.text("settings.name_template.desc", "en"))
        self.assertIn("{date}", self.catalog.text("settings.name_template.desc", "en"))
        self.assertEqual(self.catalog.text("settings.name_template.value", "ru"), "подпись_{имя}")
        self.assertEqual(self.catalog.text("settings.name_template.value", "en"), "signature_{name}")

    def test_placeholders_and_decimal_separator(self) -> None:
        self.assertEqual(self.catalog.text("about.version", "ru", version="1.0"), "Версия: 1.0")
        self.assertEqual(self.catalog.text("about.version", "en", version="1.0"), "Version 1.0")
        self.assertEqual(self.catalog.text("export.size.mm_value", "ru", n=64.1), "64,1 мм")
        self.assertEqual(self.catalog.text("export.size.mm_value", "en", n=64.1), "64.1 mm")
        self.assertEqual(self.catalog.text("export.dpi_value", "en", n=600), "600 DPI")

    def test_russian_few_forms_match_the_table(self) -> None:
        for key, forms in RU_FORMS.items():
            self.assertEqual(self.catalog.raw(key, "ru"), forms["few"], key)

    def test_save_count_plural(self) -> None:
        self.assertEqual(self.catalog.text("export.save_count", "ru", n=1), "Сохранить (1 файл)")
        self.assertEqual(self.catalog.text("export.save_count", "ru", n=2), "Сохранить (2 файла)")
        self.assertEqual(self.catalog.text("export.save_count", "ru", n=5), "Сохранить (5 файлов)")
        self.assertEqual(self.catalog.text("export.save_count", "ru", n=21), "Сохранить (21 файл)")
        self.assertEqual(self.catalog.text("export.save_count", "ru", n=11), "Сохранить (11 файлов)")
        self.assertEqual(self.catalog.text("export.save_count", "en", n=1), "Save (1 file)")
        self.assertEqual(self.catalog.text("export.save_count", "en", n=2), "Save (2 files)")

    def test_saved_status_plural(self) -> None:
        self.assertEqual(
            self.catalog.text("export.saved_status", "ru", n=1, folder="Подписи"),
            "Сохранён 1 файл в папку «Подписи»",
        )
        self.assertEqual(
            self.catalog.text("export.saved_status", "ru", n=2, folder="Подписи"),
            "Сохранено 2 файла в папку «Подписи»",
        )
        self.assertEqual(
            self.catalog.text("export.saved_status", "ru", n=5, folder="Подписи"),
            "Сохранено 5 файлов в папку «Подписи»",
        )
        self.assertEqual(
            self.catalog.text("export.saved_status", "en", n=1, folder="Signatures"),
            "Saved 1 file to “Signatures”",
        )
        self.assertEqual(
            self.catalog.text("export.saved_status", "en", n=3, folder="Signatures"),
            "Saved 3 files to “Signatures”",
        )

    def test_batch_saving_plural_follows_total(self) -> None:
        self.assertEqual(
            self.catalog.text("batch.saving", "ru", done=3, total=1),
            "Сохранено 3 из 1 файла",
        )
        self.assertEqual(
            self.catalog.text("batch.saving", "ru", done=3, total=21),
            "Сохранено 3 из 21 файла",
        )
        self.assertEqual(
            self.catalog.text("batch.saving", "ru", done=3, total=5),
            "Сохранено 3 из 5 файлов",
        )
        self.assertEqual(
            self.catalog.text("batch.saving", "en", done=3, total=1),
            "Saved 3 of 1 file",
        )
        self.assertEqual(
            self.catalog.text("batch.saving", "en", done=3, total=4),
            "Saved 3 of 4 files",
        )

    def test_batch_summary_pluralises_each_count(self) -> None:
        self.assertEqual(
            self.catalog.text("batch.summary", "ru", photos=2, formats=1, files=1),
            "2 фото × 1 формат = 1 файл",
        )
        self.assertEqual(
            self.catalog.text("batch.summary", "ru", photos=2, formats=2, files=2),
            "2 фото × 2 формата = 2 файла",
        )
        self.assertEqual(
            self.catalog.text("batch.summary", "ru", photos=2, formats=5, files=5),
            "2 фото × 5 форматов = 5 файлов",
        )
        self.assertEqual(
            self.catalog.text("batch.summary", "en", photos=1, formats=1, files=1),
            "1 photo × 1 format = 1 file",
        )
        self.assertEqual(
            self.catalog.text("batch.summary", "en", photos=2, formats=2, files=3),
            "2 photos × 2 formats = 3 files",
        )

    def test_stroke_count_plural(self) -> None:
        self.assertEqual(
            self.catalog.text("process.meta", "ru", n=1, w=10, h=5),
            "1 штрих · 10 × 5 мм",
        )
        self.assertEqual(
            self.catalog.text("process.meta", "ru", n=3, w=10, h=5),
            "3 штриха · 10 × 5 мм",
        )
        self.assertEqual(
            self.catalog.text("process.meta", "ru", n=5, w=10, h=5),
            "5 штрихов · 10 × 5 мм",
        )
        self.assertEqual(
            self.catalog.text("process.meta", "en", n=1, w=10, h=5),
            "1 stroke · 10 × 5 mm",
        )
        self.assertEqual(
            self.catalog.text("process.meta", "en", n=4, w=10, h=5),
            "4 strokes · 10 × 5 mm",
        )


if __name__ == "__main__":
    unittest.main()
