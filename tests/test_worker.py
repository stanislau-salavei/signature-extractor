import threading
import time

from core.worker import BackgroundWorker


def _drain(w, done, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end and not done():
        w.poll()
        time.sleep(0.01)
    time.sleep(0.1)
    w.poll()


def test_stale_results_are_dropped_and_errors_delivered():
    w = BackgroundWorker()
    gate = threading.Event()
    got = []
    w.submit("blocker", lambda: (gate.wait(2), "b")[1], got.append)
    w.submit("preview", lambda: "old", got.append)
    w.submit("preview", lambda: "new", got.append)
    errs = []
    w.submit("save", lambda: 1 / 0, got.append, errs.append)
    gate.set()
    _drain(w, lambda: errs and len(got) >= 2)
    assert "new" in got and "old" not in got and "b" in got
    assert len(errs) == 1 and isinstance(errs[0], ZeroDivisionError)
