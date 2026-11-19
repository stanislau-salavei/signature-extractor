"""Approved differences between the project table and /workspace/prompt/v2/i18n/strings_ru_en.csv.

Since remarks 77–85 (2026-11-19) the prompt table is no longer edited: the project CSV keeps every other row
exactly as in the prompt copy, and only these rows differ (listed in NOTES.md, «Замечания 77–85» and «Замечания 86–89»)."""
import csv
import io
from pathlib import Path

PROMPT_CSV = Path("/workspace/prompt/v2/i18n/strings_ru_en.csv")

# text changed: 78 (no AI), 77 (one photo — the bar under the image), 85 (no final period),
# 88 (no graphics card / DirectX 12 in the issue form), 89 (the reason inside the yellow card)
CHANGED = {
    "import.tip_background": "78", "process.meta.frame_large": "78, 85", "batch.reason_not_found": "78",
    "help.process.frame4": "78", "help.start.settings_text": "78", "help.prep.paper_text": "78",
    "help.batch.all_text": "78", "help.batch.attention_text": "77, 89", "dialog.reset.body": "85",
    "dialog.apply_all.body": "85", "issue.body": "88",
}
# rows removed (78): the AI and GPU switches, the AI help card, dialog 30 (replaced by the card of remark 74)
REMOVED = {
    "process.ai", "process.ai_desc", "settings.ai_default", "settings.ai_default.desc", "settings.gpu",
    "settings.gpu.desc", "settings.gpu.unsupported", "help.process.ai", "errors.no_signature.title",
    "errors.no_signature.body",
}


def _rows(path: Path):
    raw = path.read_bytes()
    return raw, list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline="")))


def assert_matches_prompt(csv_path: Path, prompt_path: Path = PROMPT_CSV) -> None:
    raw_a, a = _rows(csv_path)
    raw_p, p = _rows(prompt_path)
    assert raw_a.startswith(b"\xef\xbb\xbf") == raw_p.startswith(b"\xef\xbb\xbf")
    assert raw_a.count(b"\r\n") == len(a) and b"\n" not in raw_a.replace(b"\r\n", b"")      # CRLF as in the prompt
    out = io.StringIO()
    csv.writer(out, lineterminator="\r\n").writerows(a)
    assert raw_a.decode("utf-8-sig") == out.getvalue()                                  # same quoting
    assert a[0] == p[0]
    ids_a = [r[0] for r in a]
    ids_p = [r[0] for r in p]
    assert set(ids_p) - set(ids_a) == REMOVED and not set(ids_a) - set(ids_p)
    assert ids_a == [i for i in ids_p if i not in REMOVED]                              # same order
    pa = {r[0]: r for r in p}
    for r in a:
        if r[0] in CHANGED:
            assert r[:2] == pa[r[0]][:2] and r[2:4] != pa[r[0]][2:4], r[0]
        else:
            assert r == pa[r[0]], r[0]
