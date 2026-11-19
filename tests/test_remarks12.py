"""Remarks 90–91 (2026-11-19): no second line «Поправьте их…» in the batch card when the selected photo has no
reason of its own (90); the prompt copy in the repository, real-photo tests skip without the photos (91).
Synthetic photos only."""
import ast
import csv
import filecmp
import os
from pathlib import Path

import pytest
from PIL import Image

from tests.test_remarks8 import app, pump, close_all      # noqa: F401  (UI fixture)
from tests.test_remarks11 import _one, _two, _open, _select, PAPER
from tests import i18n_prompt_diff as D

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "i18n" / "strings_ru_en.csv"


def rows():
    return {r[0]: r for r in csv.reader(CSV.open(encoding="utf-8-sig", newline=""))}


@pytest.fixture(scope="module")
def mixed12(tmp_path_factory):
    d = tmp_path_factory.mktemp("r12mixed")
    for i in (1, 2):
        _one(d / f"photo_{i}.png")
    _two(d / "photo_3.png")
    Image.new("RGB", (1200, 800), PAPER).save(d / "photo_4.png", dpi=(300, 300))
    return d


# ================================================================== 90
def test_r90_hint_row_and_code_removed():
    assert "batch.attention_hint" not in rows()
    assert "batch.attention_hint" in D.REMOVED
    src = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "ui").rglob("*.py"))
    assert "batch.attention_hint" not in src


def test_r90_selected_photo_without_reason_has_title_only(app, mixed12):
    _open(app, [mixed12])
    pp, b = app.process_page, app.batch
    assert b is not None and len(b.blocking()) == 1                     # photo 4: no signature
    _select(app, "photo_1.png")
    wb = pp.warn_bar
    assert app.job.status == "ready"
    assert wb.visible and wb.title == app.tn("batch.attention_bar", 2) and wb.action.visible
    assert wb.msg == "" and wb.lines() == [] and wb.height() == 48.0
    assert pp.bar.next.disabled                                         # export still locked by photo 4
    _select(app, "photo_4.png")
    assert wb.lines() == [app.t("batch.reason_not_found")]             # 89 unchanged
    _select(app, "photo_3.png")
    assert wb.lines() == [app.t("batch.doubt.several")]


# ================================================================== 91
def test_r91_prompt_copy_in_the_repository():
    docs = ROOT / "docs" / "prompt_v2"
    for name in ("final_prompt_ru.md", "CHANGES.md", "README.md", "i18n/strings_ru_en.csv", "i18n/strings_ru_en.xlsx",
                 *(f"stage_{i}.md" if i else "stage_0_common.md" for i in range(7))):
        assert (docs / name).exists(), name
    assert D.PROMPT_DIR == docs and D.PROMPT_CSV == docs / "i18n" / "strings_ru_en.csv"
    local = Path(os.environ.get("SE_PROMPT_FALLBACK", "/workspace/prompt/v2"))
    if local.exists():                                                  # the copy is not edited …
        for p in local.rglob("*"):
            if p.is_file() and p.name != "strings_ru_en.csv":
                assert filecmp.cmp(p, docs / p.relative_to(local), shallow=False), p
        # … except remark 110 (1.0.1): three unused example rows removed, the note of color.name_placeholder fixed
        gone = (b"export.path_example,", b"color.example_purple,", b"color.example_burgundy,")
        src = [line for line in (local / "i18n" / "strings_ru_en.csv").read_bytes().split(b"\n") if not line.startswith(gone)]
        src = b"\n".join(src).replace(b"Placeholder; the example name must match color.example_purple.",
                                      b"Placeholder with an example colour name.")
        assert (docs / "i18n" / "strings_ru_en.csv").read_bytes() == src
    D.assert_matches_prompt(CSV)


def _uses(tree, names):
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} & names


def test_r91_real_photo_tests_skip_without_the_photos():
    """Every test that reads R48 / ZIP4 / SAMPLE3 / PRIVATE has a skipif marker or calls pytest.skip."""
    local = {"R48", "ZIP4", "SAMPLE3", "PRIVATE"}
    bad = []
    for f in sorted((ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        helpers = {n.name for n in tree.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("test_")
                   and _uses(n, local)}
        for n in tree.body:
            if not (isinstance(n, ast.FunctionDef) and n.name.startswith("test_")):
                continue
            calls = {c.func.id for c in ast.walk(n) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
            if not (_uses(n, local) or calls & helpers):
                continue
            marked = any("skip" in ast.unparse(d) or "needs_" in ast.unparse(d) for d in n.decorator_list)
            skips = "pytest.skip" in ast.unparse(n)
            if not (marked or skips):
                bad.append(f"{f.name}::{n.name}")
    assert bad == []
