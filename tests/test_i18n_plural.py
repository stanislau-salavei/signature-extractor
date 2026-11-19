from pathlib import Path

import pytest

from core.i18n import I18n, ru_plural_category
from tests.i18n_prompt_diff import assert_matches_prompt  # noqa: E402

CSV = Path(__file__).resolve().parents[1] / "i18n" / "strings_ru_en.csv"


@pytest.mark.parametrize("n,cat", [(1, "one"), (21, "one"), (2, "few"), (4, "few"), (22, "few"),
                                   (5, "many"), (11, "many"), (12, "many"), (14, "many"), (111, "many"), (0, "many")])
def test_ru_category(n, cat):
    assert ru_plural_category(n) == cat


def test_ru_save_button():
    i = I18n(CSV, "ru")
    assert i.tn("export.save_count", 1) == "Сохранить (1 файл)"
    assert i.tn("export.save_count", 2) == "Сохранить (2 файла)"
    assert i.tn("export.save_count", 5) == "Сохранить (5 файлов)"
    assert i.tn("export.save_count", 21) == "Сохранить (21 файл)"


def test_ru_saved_status():
    i = I18n(CSV, "ru")
    assert i.tn("export.saved_status", 1, folder="Подписи").startswith("Сохранён 1 файл")
    assert i.tn("export.saved_status", 5, folder="Подписи").startswith("Сохранено 5 файлов")
    assert "Подписи" in i.tn("export.saved_status", 3, folder="Подписи")


def test_en_plural():
    i = I18n(CSV, "en")
    assert i.tn("export.save_count", 1) == "Save (1 file)"
    assert i.tn("export.save_count", 2) == "Save (2 files)"


def test_missing_key_and_bad_format_do_not_raise():
    i = I18n(CSV, "ru")
    assert i.t("no.such.key") == "no.such.key"
    assert i.tn("no.such.key", 3) == "no.such.key"
    assert isinstance(i.t("export.saved_status"), str)


def test_vector_tag_badge():
    ru, en = I18n(CSV, "ru"), I18n(CSV, "en")
    assert ru.t("export.vector_tag", size=ru.t("export.size.wxh", w="15", h="5"), kb=190) == "15 × 5 мм · вектор · ≈ 190 КБ"
    assert en.t("export.vector_tag", size=en.t("export.size.wxh", w="15", h="5"), kb=190) == "15 × 5 mm · vector · ≈ 190 KB"


def test_project_csv_matches_prompt_csv():
    from tests.i18n_prompt_diff import PROMPT_CSV as prompt   # remark 91: docs/prompt_v2 in the repository
    if not prompt.exists():
        pytest.skip("prompt table not available")
    assert_matches_prompt(CSV, prompt)         # remarks 77–85: approved differences only
