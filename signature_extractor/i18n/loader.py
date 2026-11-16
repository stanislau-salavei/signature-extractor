"""Load the approved RU/EN string table and fill placeholders."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from signature_extractor.i18n.plurals import (
    PLURAL_COUNT_KEY,
    batch_summary,
    english_plural,
    russian_plural,
    split_en_plural,
)
from signature_extractor.paths import strings_csv_path

_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

# Strings whose English cell is an explicit one/other pair.
def _is_plural_cell(text: str) -> bool:
    return split_en_plural(text) is not None


class Catalog:
    """In-memory copy of ``strings_ru_en.csv``.

    ``text`` raises ``KeyError`` for an unknown id so a missing translation
    cannot be replaced with an invented sentence.
    """

    def __init__(self, rows: dict[str, dict[str, str]]):
        self._rows = rows

    def __len__(self) -> int:
        return len(self._rows)

    def keys(self) -> list[str]:
        return list(self._rows)

    def raw(self, key: str, lang: str) -> str:
        if lang not in ("ru", "en"):
            raise ValueError(f"unsupported language: {lang}")
        try:
            return self._rows[key][lang]
        except KeyError as exc:
            raise KeyError(key) from exc

    def text(self, key: str, lang: str, **params: object) -> str:
        if key == "batch.summary":
            return batch_summary(lang, params)
        raw = self.raw(key, lang)
        count_name = PLURAL_COUNT_KEY.get(key)
        count = _as_int(params.get(count_name)) if count_name else None
        if lang == "en" and _is_plural_cell(raw):
            raw = english_plural(raw, count)
        elif lang == "ru":
            raw = russian_plural(key, raw, count)
        return _substitute(raw, params, lang)


def load_catalog(path: Path | None = None) -> Catalog:
    csv_path = path or strings_csv_path()
    rows: dict[str, dict[str, str]] = {}
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "id" not in reader.fieldnames:
            raise ValueError(f"string table {csv_path} has no id column")
        for record in reader:
            key = (record.get("id") or "").strip()
            if not key:
                continue
            rows[key] = {
                "ru": record.get("Russian") or "",
                "en": record.get("English") or "",
                "note": record.get("note") or "",
                "screens": record.get("screen(s)") or "",
            }
    return Catalog(rows)


def format_number(value: float, lang: str) -> str:
    """Locale decimal separator: comma in Russian, point in English."""
    if isinstance(value, float) and value.is_integer():
        rendered = str(int(value))
    else:
        rendered = str(value)
    if lang == "ru":
        return rendered.replace(".", ",")
    return rendered


def _as_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _substitute(template: str, params: dict[str, object], lang: str) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in params:
            # Leave unknown tokens ({name}, {date}, …) in place.
            return match.group(0)
        value = params[name]
        if isinstance(value, bool) or value is None:
            return str(value)
        if isinstance(value, float):
            return format_number(value, lang)
        if isinstance(value, int):
            return str(value)
        return str(value)

    return _PLACEHOLDER.sub(replace, template)
