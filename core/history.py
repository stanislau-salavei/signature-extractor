"""Unlimited undo/redo stack per photo (stage 2 requirement)."""

from __future__ import annotations
from typing import Any, List, Optional


class HistoryStack:
    def __init__(self):
        self._undo: List[Any] = []
        self._redo: List[Any] = []

    def push(self, state: Any) -> None:
        self._undo.append(state)
        self._redo.clear()

    def can_undo(self) -> bool:
        return len(self._undo) > 1  # keep at least one (current)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> Optional[Any]:
        if not self.can_undo():
            return None
        current = self._undo.pop()
        self._redo.append(current)
        return self._undo[-1]

    def redo(self) -> Optional[Any]:
        if not self.can_redo():
            return None
        state = self._redo.pop()
        self._undo.append(state)
        return state

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def set_initial(self, state: Any) -> None:
        self.clear()
        self._undo.append(state)
