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


def worker_cmd(settings: Settings | None = None) -> list[str]:
    python = (settings and settings.worker_python) or os.environ.get("AUDIOTOOLKIT_WORKER_PYTHON") \
        or str(APP_DIR / ".venv" / "bin" / "python")
    return [python, "-m", "audiotoolkit.worker"]


def worker_env(settings: Settings) -> dict | None:
    if not settings.extra_path:
        return None
    return {**os.environ, "PATH": settings.extra_path + os.pathsep + os.environ.get("PATH", "")}


def repo_path(settings: Settings, name: str) -> str:
    return settings.repos.get(name) or str(APP_DIR.parent / name)


class UiBackend:
    def __init__(self, settings: Settings, presets: dict[str, Preset], on_change: Callable[[Item], None]):
        self.queue = BatchQueue()
        self._on_change = on_change
        self.supervisor = Supervisor(worker_cmd(settings), lambda ev: GLib.idle_add(self._dispatch, ev),
                                    worker_env(settings))
        self.runner = BatchRunner(self.queue, self.supervisor.submit, self.supervisor.cancel, settings.out_root,
                                  presets, settings.skip_existing, on_change)

    def _dispatch(self, ev: Event) -> bool:
        self.runner.on_event(ev)
        return GLib.SOURCE_REMOVE

    def update_settings(self, settings: Settings) -> None:
        self.runner.out_root, self.runner.skip_existing = settings.out_root, settings.skip_existing
        self.supervisor.set_launch(worker_cmd(settings), worker_env(settings))

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
