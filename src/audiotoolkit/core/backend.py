"""Toolkit-independent glue: queue + supervisor + runner behind one object, and where the worker lives."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Iterable

from .presets import Preset
from .protocol import Event
from .queue import BatchQueue, Item
from .runner import BatchRunner
from .settings import Settings
from .setup_env import venv_python
from .supervisor import Supervisor

PKG_DIR = Path(__file__).resolve().parents[1]
PRESETS_DIR = PKG_DIR / "presets"


def worker_cmd(settings: Settings | None = None) -> list[str]:
    python = (settings and settings.worker_python) or os.environ.get("AUDIOTOOLKIT_WORKER_PYTHON") \
        or str(venv_python())
    return [python, "-m", "audiotoolkit.worker"]


def worker_env(settings: Settings) -> dict:
    """The worker imports this very package (pure Python), so it needs no install of the app inside its environment."""
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(PKG_DIR.parent), os.environ.get("PYTHONPATH")]))}
    if settings.extra_path:
        env["PATH"] = settings.extra_path + os.pathsep + env.get("PATH", "")
    return env


def worker_ready(settings: Settings) -> bool:
    return Path(worker_cmd(settings)[0]).is_file()


def repo_path(settings: Settings, name: str) -> str:
    """A local checkout or git URL the user entered; empty when none."""
    return settings.repos.get(name, "")


class Backend:
    """`post(fn)` must run fn on the UI thread; it is called from the worker's reader thread."""

    def __init__(self, settings: Settings, presets: dict[str, Preset], on_change: Callable[[Item], None],
                 post: Callable[[Callable[[], None]], None]):
        self.queue = BatchQueue()
        self._on_change = on_change
        self.supervisor = Supervisor(worker_cmd(settings), lambda ev: post(lambda: self.runner.on_event(ev)),
                                     worker_env(settings))
        self.runner = BatchRunner(self.queue, self.supervisor.submit, self.supervisor.cancel, settings.out_root,
                                  presets, settings.skip_existing, on_change)

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
