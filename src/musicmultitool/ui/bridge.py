"""GTK side of the backend: marshals the worker's events onto the GLib main loop."""
from __future__ import annotations

from typing import Callable

from gi.repository import GLib

from musicmultitool.core.backend import (PRESETS_DIR, Backend, repo_path, worker_cmd, worker_env,  # noqa: F401
                                       worker_ready)
from musicmultitool.core.presets import Preset
from musicmultitool.core.queue import Item
from musicmultitool.core.settings import Settings


class UiBackend(Backend):
    def __init__(self, settings: Settings, presets: dict[str, Preset], on_change: Callable[[Item], None]):
        super().__init__(settings, presets, on_change, lambda fn: GLib.idle_add(lambda: fn() and False))
