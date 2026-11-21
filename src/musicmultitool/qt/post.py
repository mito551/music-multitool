"""Run a function on the UI thread from any thread (the worker's reader thread reports through this)."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, Signal


class Poster(QObject):
    _call = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._call.connect(lambda fn: fn())  # a signal emitted from another thread is queued to this object's thread

    def post(self, fn: Callable[[], None]) -> None:
        self._call.emit(fn)
