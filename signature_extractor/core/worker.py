"""Background job queue.

Stage 1 does not process photos. Later stages submit recognition and export
jobs here so the window thread never waits on that work. Results from an
older job are ignored once a newer one has been submitted.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Worker:
    """Single worker thread. The stage 1 methods are empty entry points."""

    def start(self) -> None:
        logger.debug("background worker is not started in stage 1")

    def submit(self, job: Any, cancel_token: Any = None) -> None:
        logger.debug("ignoring job %r; processing starts in stage 2", type(job).__name__)

    def shutdown(self) -> None:
        return
