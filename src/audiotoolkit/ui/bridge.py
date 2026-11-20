"""Glue between the GTK main loop and the worker: queue + supervisor + runner behind one object."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Iterable

from gi.repository import GLib

from audiotoolkit.core.presets import Preset
from audiotoolkit.core.protocol import Event
from audiotoolkit.core.queue import BatchQueue, Item
from audiotoolkit.core.runner import BatchRunner
from audiotoolkit.core.settings import Settings
from audiotoolkit.core.supervisor import Supervisor

APP_DIR = Path(__file__).resolve().parents[3]


def worker_cmd() -> list[str]:
    python = os.environ.get("AUDIOTOOLKIT_WORKER_PYTHON") or str(APP_DIR / ".venv" / "bin" / "python")
    return [python, "-m", "audiotoolkit.worker"]


class UiBackend:
    def __init__(self, settings: Settings, presets: dict[str, Preset], on_change: Callable[[Item], None]):
        self.queue = BatchQueue()
        self._on_change = on_change
        self.supervisor = Supervisor(worker_cmd(), lambda ev: GLib.idle_add(self._dispatch, ev))
        self.runner = BatchRunner(self.queue, self.supervisor.submit, self.supervisor.cancel, settings.out_root,
                                  presets, settings.skip_existing, on_change)

    def _dispatch(self, ev: Event) -> bool:
        self.runner.on_event(ev)
        return GLib.SOURCE_REMOVE

    def update_settings(self, settings: Settings) -> None:
        self.runner.out_root, self.runner.skip_existing = settings.out_root, settings.skip_existing

    def set_presets(self, presets: dict[str, Preset]) -> None:
        self.runner.presets = presets

    def add(self, paths: Iterable[str], kind: str, opts: dict) -> list[Item]:
        items = self.queue.add(paths, kind, opts)
        for i in items:
            self._on_change(i)
        return items

    def start(self) -> None:
        self.runner.start()

    def cancel(self) -> None:
        self.runner.cancel()

    def retry_failed(self) -> int:
        n = self.queue.retry_failed()
        for i in self.queue.items:
            self._on_change(i)
        return n

    def close(self) -> None:
        self.supervisor.close()
