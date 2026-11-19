import csv
import re
from pathlib import Path
from typing import Dict

_RU_FORM_RE = re.compile(r"\b(one|few|many):?\s*«([^»]*)»")


def ru_plural_category(n: int) -> str:
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return "one"
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return "few"
    return "many"


def ru_plural_text(base: str, note: str, n: int) -> str:
    """Russian plural forms come from the table note: one «…» / few «…» / many «…».

    The Russian cell holds the «few» form; a partial form (e.g. «({n} файла)»)
    replaces the matching part of it, a full form replaces the whole phrase.
    """
    forms = {k: v.rstrip("…").strip() for k, v in _RU_FORM_RE.findall(note or "")}
    cat = ru_plural_category(n)
    target = forms.get(cat) or (forms.get("many") if cat == "few" else None)
    # reference = the form written in the Russian cell (normally «few»; «many» for batch.saving)
    ref = next((forms[k] for k in ("few", "many", "one") if forms.get(k) and forms[k] in base), None)
    if not target:
        return base
    if ref is None:
        # only a full «one» sentence is given (batch.attention_hint: «Поправьте его…»)
        return target if (cat == "one" and set(forms) == {"one"}) else base
    idx = base.index(ref)
    prefix = base[:idx]
    if prefix and target.startswith(prefix):
        return target + base[idx + len(ref):]
    return base[:idx] + target + base[idx + len(ref):]


class I18n:
    def __init__(self, csv_path: Path, lang: str = "ru"):
        self.lang = lang if lang in ("ru", "en") else "ru"
        self.strings: Dict[str, Dict[str, str]] = {}
        self.notes: Dict[str, str] = {}
        self._load_csv(csv_path)

    def _load_csv(self, csv_path: Path) -> None:
        with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row.get("id") or "").strip()
                if not key:
                    continue
                self.strings[key] = {
                    "ru": row.get("Russian") or "",
                    "en": row.get("English") or "",
                }
                self.notes[key] = row.get("note") or ""

    def set_language(self, lang: str) -> None:
        if lang in ("ru", "en"):
            self.lang = lang

    def t(self, key: str, **kwargs) -> str:
        entry = self.strings.get(key)
        if not entry:
            return key
        text = entry.get(self.lang) or entry.get("en") or key

        if self.lang == "en" and "one:" in text and "|" in text and "n" in kwargs:
            n = kwargs["n"]
            parts = [p.strip() for p in text.split("|")]
            forms = {}
            for p in parts:
                if ":" in p:
                    form_name, form_val = p.split(":", 1)
                    forms[form_name.strip()] = form_val.strip()
            text = forms.get("one" if n == 1 else "other", text)

        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                pass
        return text

    def tn(self, key: str, n: int, forms_from: str = "", **kwargs) -> str:
        """Plural-aware lookup: English «one: … | other: …», Russian forms from the note
        (``forms_from`` = another row whose note lists the forms, e.g. process.meta for process.meta_batch)."""
        kwargs = dict(kwargs)
        kwargs.setdefault("n", n)
        if self.lang == "ru":
            entry = self.strings.get(key)
            if not entry:
                return key
            text = ru_plural_text(entry.get("ru") or "", self.notes.get(forms_from or key, ""), n)
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
        return self.t(key, **kwargs)
