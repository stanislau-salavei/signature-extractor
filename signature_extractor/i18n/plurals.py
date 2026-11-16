"""Plural forms taken from the i18n table.

English ``one: … | other: …`` cells are parsed from the CSV. Russian forms
live in the ``note`` column; the templates below are those notes, copied
verbatim. The CSV cell itself is the few-form used on the mockups.
"""

from __future__ import annotations

# Which placeholder selects the form. ``batch.summary`` uses several counts.
PLURAL_COUNT_KEY: dict[str, str] = {
    "import.skipped_body": "n",
    "process.meta": "n",
    "process.meta_batch": "n",
    "export.save_count": "n",
    "export.saved_status": "n",
    "batch.attention_bar": "n",
    "batch.attention_hint": "n",
    "batch.attention_tooltip": "n",
    "batch.skipped_large_bar": "n",
    "batch.skipped_large_title": "n",
    "batch.saving": "total",
}

# Russian one / few / many templates from the note column.
RU_FORMS: dict[str, dict[str, str]] = {
    "import.skipped_body": {
        "one": "Найдено {photos} фото, остальные {n} файл, не являющийся фото, пропущен",
        "few": "Найдено {photos} фото, остальные {n} файла, не являющиеся фото, пропущены",
        "many": "Найдено {photos} фото, остальные {n} файлов, не являющихся фото, пропущены",
    },
    "process.meta": {
        "one": "{n} штрих · {w} × {h} мм",
        "few": "{n} штриха · {w} × {h} мм",
        "many": "{n} штрихов · {w} × {h} мм",
    },
    "process.meta_batch": {
        "one": "{file} · {n} штрих · {w} × {h} мм",
        "few": "{file} · {n} штриха · {w} × {h} мм",
        "many": "{file} · {n} штрихов · {w} × {h} мм",
    },
    "export.save_count": {
        "one": "Сохранить ({n} файл)",
        "few": "Сохранить ({n} файла)",
        "many": "Сохранить ({n} файлов)",
    },
    "export.saved_status": {
        "one": "Сохранён {n} файл в папку «{folder}»",
        "few": "Сохранено {n} файла в папку «{folder}»",
        "many": "Сохранено {n} файлов в папку «{folder}»",
    },
    "batch.attention_bar": {
        "one": "{n} файл требует внимания",
        "few": "{n} файла требуют внимания",
        "many": "{n} файлов требуют внимания",
    },
    "batch.attention_hint": {
        "one": "Поправьте его или уберите из пакета, чтобы перейти к экспорту",
        "few": "Поправьте их или уберите из пакета, чтобы перейти к экспорту",
        "many": "Поправьте их или уберите из пакета, чтобы перейти к экспорту",
    },
    "batch.attention_tooltip": {
        "one": "Сначала решите {n} файл, требующий внимания",
        "few": "Сначала решите {n} файла, требующих внимания",
        "many": "Сначала решите {n} файлов, требующих внимания",
    },
    "batch.skipped_large_bar": {
        "one": "{n} файл пропущен: больше 50 МБ",
        "few": "{n} файла пропущено: больше 50 МБ",
        "many": "{n} файлов пропущено: больше 50 МБ",
    },
    "batch.skipped_large_title": {
        "one": "Пропущен {n} файл",
        "few": "Пропущено {n} файла",
        "many": "Пропущено {n} файлов",
    },
    "batch.saving": {
        "one": "Сохранено {done} из {total} файла",
        "few": "Сохранено {done} из {total} файлов",
        "many": "Сохранено {done} из {total} файлов",
    },
}


def ru_category(count: int) -> str:
    """Russian plural category: one / few / many."""
    number = abs(int(count))
    if number % 10 == 1 and number % 100 != 11:
        return "one"
    if number % 10 in (2, 3, 4) and number % 100 not in (12, 13, 14):
        return "few"
    return "many"


def en_category(count: int) -> str:
    """English plural category: one / other."""
    return "one" if int(count) == 1 else "other"


def split_en_plural(raw: str) -> tuple[str, str] | None:
    """Parse ``one: … | other: …``. Returns None when the cell is not plural."""
    if "one:" not in raw or "other:" not in raw or "|" not in raw:
        return None
    one = other = None
    for part in raw.split("|"):
        piece = part.strip()
        if piece.startswith("one:"):
            one = piece[4:].strip()
        elif piece.startswith("other:"):
            other = piece[6:].strip()
    if one is None or other is None:
        return None
    return one, other


def english_plural(raw: str, count: int | None) -> str:
    forms = split_en_plural(raw)
    if forms is None:
        return raw
    one, other = forms
    if count is None:
        return other
    return one if en_category(count) == "one" else other


def russian_plural(key: str, csv_text: str, count: int | None) -> str:
    forms = RU_FORMS.get(key)
    if forms is None or count is None:
        return csv_text
    return forms[ru_category(count)]


def _en_phrase(count: int, singular: str, plural: str) -> str:
    if int(count) == 1:
        return f"1 {singular}"
    return f"{int(count)} {plural}"


def _ru_word(count: int, one: str, few: str, many: str) -> str:
    return {"one": one, "few": few, "many": many}[ru_category(count)]


def batch_summary(lang: str, params: dict) -> str:
    """``batch.summary`` pluralises three counts independently.

    Russian «фото» does not change. English one/other forms come from the
    note (1 photo, 1 format, 1 file); the CSV cell is the other-form.
    """
    photos = int(params.get("photos", 0))
    formats = int(params.get("formats", 0))
    files = int(params.get("files", 0))
    if lang == "ru":
        format_word = _ru_word(formats, "формат", "формата", "форматов")
        file_word = _ru_word(files, "файл", "файла", "файлов")
        return f"{photos} фото × {formats} {format_word} = {files} {file_word}"
    photos_phrase = _en_phrase(photos, "photo", "photos")
    formats_phrase = _en_phrase(formats, "format", "formats")
    files_phrase = _en_phrase(files, "file", "files")
    return f"{photos_phrase} × {formats_phrase} = {files_phrase}"
