"""Job kinds, imported lazily so torch is only loaded when a kind needs it."""
from __future__ import annotations

import importlib
from types import ModuleType

KINDS = {k: f"audiotoolkit.worker.kinds.{k}" for k in ("convert", "analyze", "separate", "midi", "lyrics")}


def load_kind(kind: str) -> ModuleType:
    if kind not in KINDS:
        raise ValueError(f"unknown kind: {kind}")
    return importlib.import_module(KINDS[kind])
