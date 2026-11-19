"""One background worker with a task queue; stale results are dropped (t4s)."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Callable, Dict, Optional

log = logging.getLogger(__name__)


class BackgroundWorker:
    """Runs tasks one by one on a daemon thread.

    Each task belongs to a *channel*; submitting a new task to the same channel
    makes older queued tasks of that channel stale (skipped, results dropped).
    Results are collected in ``results`` and must be fetched from the UI thread
    with :meth:`poll` (no Tk calls from the worker thread).
    """

    def __init__(self):
        # (priority, seq, task): lower runs first; equal priority keeps FIFO order (stage 4: the
        # current photo and the UI's own work go before background processing of the batch)
        self._tasks: "queue.PriorityQueue[tuple]" = queue.PriorityQueue()
        self.results: "queue.Queue[tuple]" = queue.Queue()
        self._latest: Dict[str, int] = {}
        self._counter = 0
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, name="export-worker", daemon=True)
        self._thread.start()

    def submit(self, channel: str, fn: Callable[[], Any], on_done: Callable[[Any], None],
               on_error: Optional[Callable[[BaseException], None]] = None, priority: int = 0) -> int:
        with self._lock:
            self._counter += 1
            token = self._counter
            self._latest[channel] = token
        self._tasks.put((priority, token, (channel, token, fn, on_done, on_error)))
        return token

    def cancel(self, channel: str) -> None:
        """Drop queued and running work of ``channel`` (its result will not be delivered)."""
        with self._lock:
            self._counter += 1
            self._latest[channel] = -self._counter

    def is_current(self, channel: str, token: int) -> bool:
        return self._latest.get(channel) == token

    def _run(self):
        while True:
            _prio, _seq, (channel, token, fn, on_done, on_error) = self._tasks.get()
            if not self.is_current(channel, token):
                continue
            try:
                res = fn()
                self.results.put((channel, token, on_done, res, None))
            except BaseException as exc:  # noqa: BLE001 — reported to UI, logged
                log.exception("background task %s failed", channel)
                self.results.put((channel, token, on_error, None, exc))

    def poll(self) -> int:
        """Deliver finished results on the calling (UI) thread. Returns count."""
        n = 0
        while True:
            try:
                channel, token, cb, res, exc = self.results.get_nowait()
            except queue.Empty:
                return n
            if not self.is_current(channel, token) or cb is None:
                continue
            n += 1
            cb(exc if exc is not None else res)
