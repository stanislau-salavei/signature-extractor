"""Stage 4 (2026-11-17): batch model, plural forms, save session, worker priorities and the batch
flow in the real app under an X display (UI tests are skipped without one)."""
import importlib
import json
import os
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from core import batch as B
from core import export as ex
from core import processing as P
from core.i18n import I18n

ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ test photos
def _photo(path: Path, ink=True, dpi=True, seed=0):
    im = Image.new("RGB", (900, 560), (239, 236, 227))
    if ink:
        d = ImageDraw.Draw(im)
        pts = [(150 + 60 * k + 7 * seed, 300 + (60 if k % 2 else -60)) for k in range(10)]
        d.line(pts, fill=(30, 45, 140), width=9, joint="curve")
        d.line([(140, 360), (780, 330)], fill=(30, 45, 140), width=7)
    im.save(path, quality=92, **({"dpi": (300, 300)} if dpi else {}))
    return path


@pytest.fixture
def folder(tmp_path):
    d = tmp_path / "photos"
    d.mkdir()
    for i in range(6):
        _photo(d / f"IMG_{100 + i}.jpg", ink=i != 3, dpi=i != 4, seed=i)
    return d


def _jobs(n):
    return [B.Job(path=Path(f"/x/IMG_{i}.jpg")) for i in range(n)]


def _done(job, strokes=3, dpi=True):
    """Mark a job processed without running the pipeline."""
    job.done_version = job.version
    job.stroke_count = strokes
    job.has_dpi = dpi


# ================================================================== Batch model
def test_batch_add_skips_same_file_and_keeps_order(tmp_path):
    a, b = tmp_path / "a.jpg", tmp_path / "b.jpg"
    bt = B.Batch([a, b, a])
    assert [j.name for j in bt.items] == ["a.jpg", "b.jpg"]
    assert bt.add([b, tmp_path / "c.jpg"])[0].name == "c.jpg"
    assert len(bt) == 3


def test_batch_remove_moves_selection():
    bt = B.Batch()
    bt.items = _jobs(4)
    bt.select(2)
    assert bt.remove(bt.items[0]) is bt.items[1] and bt.index == 1     # earlier photo removed
    cur = bt.current
    nxt = bt.remove(cur)                                                # current removed → next one
    assert nxt is bt.items[1] and cur not in bt.items
    bt.select(len(bt.items) - 1)
    last = bt.current
    assert bt.remove(last) is bt.items[-1]                              # last removed → new last
    assert len(bt.items) == 1
    assert bt.remove(bt.items[0]) is None and bt.current is None        # decision 9: empty


def test_attention_bar_states_and_export_lock():
    bt = B.Batch()
    bt.items = _jobs(5)
    assert bt.bar_state() is None and not bt.ready_for_export()        # still processing
    for j in bt.items:
        _done(j)
    _done(bt.items[1], strokes=0)
    _done(bt.items[3], strokes=0)
    bt.note_attention()
    assert bt.bar_state() == "warn" and not bt.ready_for_export()
    assert [j.status for j in bt.items].count("attention") == 2
    bt.select(1)
    assert bt.next_attention() == 3
    bt.select(3)
    assert bt.next_attention() == 1                                     # cyclic
    _done(bt.items[1], strokes=4)                                       # decision 3: found after edit
    bt.remove(bt.items[3])
    assert bt.bar_state() == "ok" and bt.ready_for_export()             # 42 only after problems
    bt.items[0].push(B.EditState(P.ProcessParams(flatten=False), None, ()))
    assert bt.bar_state() is None and not bt.ready_for_export()         # busy again


def test_status_only_not_found_needs_attention():
    j = B.Job(path=Path("x.jpg"))
    assert j.status == "pending"
    _done(j, strokes=1)
    assert j.status == "ready"
    _done(j, strokes=0)
    assert j.status == "attention"


def test_apply_to_all_copies_panel_settings_one_step_per_photo():
    bt = B.Batch()
    bt.items = _jobs(3)
    src = bt.items[0]
    other = bt.items[1]
    other.push(B.EditState(other.state.params, (1, 2, 30, 40), (("stroke",),)))
    params = P.ProcessParams(flatten=False, ink_mode="manual", ink_rgb=(10, 20, 30), denoise=40, sensitivity=70)
    src.push(B.EditState(params, None, ()))
    changed = bt.apply_params_to_all(params, source=src)
    assert changed == bt.items[1:]
    for j in changed:
        assert j.state.params == params
    assert other.state.frame == (1, 2, 30, 40) and other.state.eraser == (("stroke",),)   # per photo
    assert other.history.can_undo()
    before = other.history.undo()
    assert before.params != params and before.frame == (1, 2, 30, 40)    # one undo step back
    other.set_state(before)
    assert bt.apply_params_to_all(params, source=src) == [other]        # only the photo rolled back


def test_thumbnail_is_square(folder):
    img, dpi = P.load_image(folder / "IMG_100.jpg")
    photo = P.prepare_photo(img, dpi, "IMG_100.jpg")
    res = P.process(photo, P.ProcessParams())
    th = B.make_thumbnail(photo, res)
    assert th.size == (B.THUMB_PX, B.THUMB_PX)


def test_process_job_loads_unloaded_photo(folder):
    j = B.Job(path=folder / "IMG_104.jpg")
    photo, res, thumb = B.process_job(j, j.state, None)
    j.apply_result(photo, res, j.version, thumb)
    assert j.status == "ready" and not j.has_dpi and j.source is not None
    j.unload()
    assert j.photo is None and j.result is None and j.source is not None and j.thumb is not None
    blank = B.Job(path=folder / "IMG_103.jpg")
    p2, r2, _ = B.process_job(blank, blank.state, None)
    blank.apply_result(p2, r2, blank.version)
    assert blank.status == "attention" and blank.source is None


# ================================================================== texts
@pytest.fixture(scope="module")
def ru():
    return I18n(ROOT / "i18n" / "strings_ru_en.csv", "ru")


@pytest.fixture(scope="module")
def en():
    return I18n(ROOT / "i18n" / "strings_ru_en.csv", "en")


def test_summary_plural_forms(ru, en):
    assert B.summary_text(ru, 50, 2, 100) == "50 фото × 2 формата = 100 файлов"
    assert B.summary_text(ru, 1, 1, 1) == "1 фото × 1 формат = 1 файл"
    assert B.summary_text(ru, 7, 3, 21) == "7 фото × 3 формата = 21 файл"
    assert B.summary_text(ru, 2, 5, 10) == "2 фото × 5 форматов = 10 файлов"
    assert B.summary_text(en, 50, 2, 100) == "50 photos × 2 formats = 100 files"
    assert B.summary_text(en, 1, 1, 1) == "1 photo × 1 format = 1 file"


def test_batch_plural_rows(ru, en):
    assert ru.tn("batch.attention_bar", 2) == "2 файла требуют внимания"
    assert ru.tn("batch.attention_bar", 1) == "1 файл требует внимания"
    assert ru.tn("batch.attention_hint", 1).startswith("Поправьте его")
    assert ru.tn("batch.attention_hint", 2).startswith("Поправьте их")
    assert ru.tn("batch.saving", 100, done=46, total=100) == "Сохранено 46 из 100 файлов"
    assert ru.tn("batch.saving", 2, done=1, total=2) == "Сохранено 1 из 2 файлов"
    assert ru.tn("batch.skipped_large_title", 3) == "Пропущено 3 файла"
    assert ru.tn("batch.attention_tooltip", 2) == "Сначала решите 2 файла, требующих внимания"
    assert ru.tn("process.meta_batch", 24, forms_from="process.meta", file="IMG_1042.jpg", w="64,1", h="24,6") == \
        "IMG_1042.jpg · 24 штриха · 64,1 × 24,6 мм"
    assert ru.tn("process.meta_batch", 5, forms_from="process.meta", file="a.jpg", w="1", h="2") == \
        "a.jpg · 5 штрихов · 1 × 2 мм"
    assert en.tn("batch.saving", 100, done=46, total=100) == "Saved 46 of 100 files"
    assert en.tn("batch.attention_bar", 1) == "1 file needs attention"
    assert ru.tn("export.saved_status", 100, folder="Подписи") == "Сохранено 100 файлов в папку «Подписи»"


# ================================================================== SaveSession
def _jobs_named(*stems):
    return [B.Job(path=Path(f"/x/{s}.jpg")) for s in stems]


def test_save_names_inside_batch_get_numbers(tmp_path):
    s = B.SaveSession(tmp_path, ("PNG", "DXF"), "add_number", "подпись_{имя}", 3)
    a, b, c = _jobs_named("IMG_1", "IMG_1", "IMG_2")   # same stem from two folders
    assert s.resolve(s.plan(a)) == [("PNG", "подпись_IMG_1"), ("DXF", "подпись_IMG_1")]
    p = s.plan(b)
    assert p.forced_number
    assert s.resolve(p) == [("PNG", "подпись_IMG_1 (2)"), ("DXF", "подпись_IMG_1 (2)")]
    assert s.resolve(s.plan(c))[0][1] == "подпись_IMG_2"
    assert s.total == 6


def test_save_existing_files_modes(tmp_path):
    (tmp_path / "s_A.png").write_bytes(b"x")
    job = _jobs_named("A")[0]
    s = B.SaveSession(tmp_path, ("PNG", "DXF"), "add_number", "s_{name}", 1)
    plan = s.plan(job)
    assert plan.conflicts and not s.needs_question(plan)
    assert s.resolve(plan)[0][1] == "s_A (2)"
    s = B.SaveSession(tmp_path, ("PNG", "DXF"), "replace", "s_{name}", 1)
    assert s.resolve(s.plan(job))[0][1] == "s_A"
    s = B.SaveSession(tmp_path, ("PNG", "DXF"), "ask", "s_{name}", 2)
    plan = s.plan(job)
    assert s.needs_question(plan)
    pairs = s.resolve(plan, "skip", apply_all=True)          # 44 «Отмена» + «Применить ко всем»
    assert pairs == [("DXF", "s_A")] and s.done == 1
    assert not s.needs_question(s.plan(job))                   # the answer is remembered


def test_save_write_counts_files(tmp_path):
    s = B.SaveSession(tmp_path, ("PNG",), "add_number", "{name}", 2)
    for job in _jobs_named("a", "b"):
        for fmt, base in s.resolve(s.plan(job)):
            s.write(fmt, base, b"data")
    assert s.finished and s.saved == 2 and sorted(p.name for p in tmp_path.iterdir()) == ["a.png", "b.png"]


# ================================================================== worker priority
def test_worker_runs_user_requests_before_background():
    from core.worker import BackgroundWorker
    w = BackgroundWorker()
    gate = threading.Event()
    order = []
    w.submit("block", lambda: gate.wait(2), lambda r: None)
    time.sleep(0.05)
    for i in range(5):
        w.submit(f"bg{i}", lambda i=i: order.append(f"bg{i}"), lambda r: None, priority=10)
    w.submit("user", lambda: order.append("user"), lambda r: None, priority=0)
    gate.set()
    end = time.time() + 3
    while time.time() < end and len(order) < 6:
        w.poll()
        time.sleep(0.01)
    assert order[0] == "user" and len(order) == 6


# ================================================================== UI (real app under X)
@pytest.fixture(scope="module")
def app(tmp_path_factory):
    if not os.environ.get("DISPLAY"):
        pytest.skip("no X display")
    tmp = tmp_path_factory.mktemp("appdata4")
    old = {k: os.environ.get(k) for k in ("APPDATA", "USERPROFILE", "LANG")}
    os.environ["APPDATA"] = str(tmp)
    os.environ["USERPROFILE"] = str(tmp)
    os.environ["LANG"] = "ru_RU.UTF-8"
    (tmp / "Signature Extractor").mkdir()
    (tmp / "Signature Extractor" / "settings.json").write_text(json.dumps({"theme": "light", "language": "ru"}))
    import core.settings
    importlib.reload(core.settings)
    from ui import app as A
    a = A.App([])
    a.root.geometry("1024x616+0+0")
    a.root.update()
    yield a
    from ui.widgets.overlay import Popup
    Popup.close_current()
    a.root.destroy()
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def pump(app, ms=50, until=None, timeout=20.0):
    end = time.time() + (timeout if until else ms / 1000)
    while time.time() < end:
        app.root.update()
        if until is not None and until():
            break
        time.sleep(0.01)


def _close_popups():
    from ui.widgets.overlay import Popup
    while Popup.current is not None:
        Popup.close_current()


def _open_batch(app, folder):
    _close_popups()
    app.go_home()
    app.open_paths([folder])
    pump(app, until=lambda: app.batch is not None and app.page == "process" and not app.batch.busy())
    pump(app, 100)


def test_ui_folder_opens_batch_and_flags_attention(app, folder):
    _open_batch(app, folder)
    b = app.batch
    assert len(b.items) == 6 and app.page == "process"
    assert [j.status for j in b.items].count("attention") == 1
    pp = app.process_page
    assert pp.strip.visible and pp.warn_bar.visible and pp.apply_btn.visible
    assert pp.bar.next.disabled                                         # «Далее» locked (39)
    assert "1 файл" in pp._next_tip()
    loaded = [j for j in b.items if j.photo is not None]
    assert len(loaded) <= B.LOADED_MAX                                  # memory: only recent photos kept
    app.show_next_attention()
    pump(app, until=lambda: app.job.loaded)
    assert app.job.status == "attention" and pp.warn_bar.msg == app.t("batch.reason_not_found")   # remark 89


def test_ui_arrows_switch_photos_and_remove(app, folder):
    _open_batch(app, folder)
    b = app.batch
    app.step_photo(1)
    pump(app, until=lambda: app.job.loaded)
    assert b.index == 1 and app.job is b.items[1]
    victim = b.items[3]                                                 # the photo without a signature
    app.remove_photo(victim)
    pump(app, 100)
    assert victim not in b.items and not b.attention()
    pump(app, until=lambda: b.ready_for_export())
    pump(app, 50)
    assert app.process_page.ok_bar.visible and not app.process_page.bar.next.disabled


def test_ui_apply_to_all_reprocesses_others(app, folder):
    _open_batch(app, folder)
    b = app.batch
    app.edit(flatten=False)
    from ui.dialogs import content
    seen = []
    orig = content.ContentDialog.__init__

    def spy(self, *a, **kw):
        seen.append(self)
        orig(self, *a, **kw)

    content.ContentDialog.__init__ = spy
    try:
        app.apply_to_all()                     # 38: asks first
    finally:
        content.ContentDialog.__init__ = orig
    assert len(seen) == 1 and seen[0].esc_index == 1
    seen[0]._activate(0)                       # «Применить»
    pump(app, 50)
    assert all(not j.state.params.flatten for j in b.items)
    pump(app, until=lambda: not b.busy())
    assert all(j.done_version == j.version for j in b.items)


def test_ui_add_photos_and_skipped_large(app, folder, tmp_path):
    _open_batch(app, folder)
    b = app.batch
    extra = _photo(tmp_path / "IMG_900.jpg", seed=9)
    big = tmp_path / "big.jpg"
    with open(big, "wb") as f:
        f.truncate(51 * 1024 * 1024)
    cur = app.job
    app.add_photos([extra, big, folder / "IMG_100.jpg"])
    assert len(b.items) == 7 and app.job is cur                         # duplicate path skipped
    assert b.skipped_large == [big] and app.process_page.skip_bar.visible
    app.close_skipped_bar()
    assert not app.process_page.skip_bar.visible


def test_ui_remove_last_photo_returns_home(app, tmp_path):
    d = tmp_path / "two"
    d.mkdir()
    _photo(d / "a.jpg")
    _photo(d / "b.jpg", seed=3)
    _open_batch(app, d)
    for j in list(app.batch.items):
        app.remove_photo(j)
        pump(app, 50)
    assert app.page == "import" and app.batch is None


def test_ui_batch_save_writes_all_files(app, folder, tmp_path):
    _open_batch(app, folder)
    app.remove_photo(app.batch.items[3])
    pump(app, until=lambda: app.batch.ready_for_export())
    app.go_export()
    pump(app, 300)
    pg = app.export_page
    assert app.page == "export" and pg.strip.visible and pg.count.visible
    fmts = pg.selected_formats()
    out = tmp_path / "out"
    out.mkdir()
    app.settings.set("if_exists", "add_number")   # 43: default is now «Спрашивать»
    pg.start_batch_save(out, fmts)
    assert app.saving and pg.dim.active
    pump(app, until=lambda: not pg._saving, timeout=40)
    files = sorted(p.name for p in out.iterdir())
    assert len(files) == 5 * len(fmts)
    assert pg.saved == (5 * len(fmts), out) and app.batch.saved and not pg.dim.active
    # second run into the same folder, «Если файл уже есть» = Добавить номер
    pg.changed()
    pg.start_batch_save(out, fmts)
    pump(app, until=lambda: not pg._saving, timeout=40)
    assert len(list(out.iterdir())) == 10 * len(fmts)
    assert any(n.endswith("(2).png") for n in (p.name for p in out.iterdir()))


def test_ui_batch_save_cancel_shows_real_count(app, folder, tmp_path):
    _open_batch(app, folder)
    app.remove_photo(app.batch.items[3])
    pump(app, until=lambda: app.batch.ready_for_export())
    app.go_export()
    pump(app, 200)
    pg = app.export_page
    out = tmp_path / "cancel"
    out.mkdir()
    pg.start_batch_save(out, pg.selected_formats())
    pump(app, until=lambda: pg._sess.saved >= 1, timeout=20)
    pg.cancel_batch_save()
    n = len(list(out.iterdir()))
    assert not app.saving and pg.saved == (n, out) and n >= 1
    assert not app.batch.saved                                          # unsaved work remains
    pump(app, 500)
    assert len(list(out.iterdir())) == n                                # nothing written after cancel


def test_ui_ask_mode_dialog_with_apply_all(app, folder, tmp_path):
    from ui.widgets.overlay import Popup
    _open_batch(app, folder)
    app.remove_photo(app.batch.items[3])
    pump(app, until=lambda: app.batch.ready_for_export())
    app.go_export()
    pump(app, 200)
    pg = app.export_page
    out = tmp_path / "ask"
    out.mkdir()
    tpl = app.settings.name_template(app.t("settings.name_template.value"))
    for stem in ("IMG_100", "IMG_101"):
        (out / (ex.expand_template(tpl, stem) + ".png")).write_bytes(b"old")
    app.settings.set("if_exists", "ask")
    try:
        pg.start_batch_save(out, ("PNG",))
        pump(app, until=lambda: Popup.current is not None)
        dlg = Popup.current
        assert dlg.check_label == app.t("batch.apply_all")
        dlg.checked = True
        dlg._activate(1)                                               # «Заменить» for all
        pump(app, until=lambda: not pg._saving, timeout=30)
        assert Popup.current is None and pg._sess.decision == "replace"
        assert len(list(out.iterdir())) == 5
        assert (out / (ex.expand_template(tpl, "IMG_101") + ".png")).read_bytes() != b"old"
    finally:
        app.settings.set("if_exists", "add_number")


def test_ui_single_file_still_single(app, folder):
    _close_popups()
    app.go_home()
    app.open_paths([folder / "IMG_100.jpg"])
    pump(app, until=lambda: app.page == "process")
    pump(app, 100)
    assert app.batch is None and not app.process_page.strip.visible and not app.process_page.apply_btn.visible
