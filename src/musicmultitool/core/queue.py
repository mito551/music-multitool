"""The batch queue: items, statuses, overrides. No I/O beyond walking folders."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable

from .protocol import Output

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".aiff"}
SYNTHV_EXT = ".synthv.txt"  # lyrics tool, reverse direction: SynthV lyrics back to plain text
MIDI_EXTS = {".mid", ".midi"}
SCORE_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


class Status(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class Item:
    id: str
    source: str
    song: str
    kind: str
    opts: dict
    overrides: dict = field(default_factory=dict)
    status: Status = Status.PENDING
    fraction: float | None = None
    message: str = ""
    outputs: list[Output] = field(default_factory=list)
    result: dict = field(default_factory=dict)


def gather_audio(paths: Iterable[str], exts: set[str] = AUDIO_EXTS) -> list[str]:
    found: list[str] = []
    for p in paths:
        if os.path.isdir(p):
            found += sorted(str(f) for f in Path(p).rglob("*") if f.is_file() and f.name.lower().endswith(tuple(exts)))
        elif Path(p).name.lower().endswith(tuple(exts)):
            found.append(p)
    return found


class BatchQueue:
    def __init__(self) -> None:
        self.items: list[Item] = []

    def add(self, paths: Iterable[str], kind: str, opts: dict) -> list[Item]:
        added = []
        exts = {"voices": MIDI_EXTS, "score": SCORE_EXTS, "lyrics": AUDIO_EXTS | {SYNTHV_EXT}}.get(kind, AUDIO_EXTS)
        for src in gather_audio(paths, exts):
            same = next((i for i in self.items if i.source == src), None)  # same file, other tool: same folder
            stem = Path(src).stem.removesuffix(".synthv")
            song, n = stem, 1
            if same is not None:
                song = same.song
            taken = {i.song for i in self.items}
            while same is None and song in taken:
                n += 1
                song = f"{stem} ({n})"
            item = Item(uuid.uuid4().hex[:8], src, song, kind, dict(opts))
            self.items.append(item)
            added.append(item)
        return added

    def get(self, item_id: str) -> Item:
        return next(i for i in self.items if i.id == item_id)

    def set_override(self, item_id: str, opts: dict) -> None:
        self.get(item_id).overrides = dict(opts)

    def effective_opts(self, item: Item) -> dict:
        return {**item.opts, **item.overrides}

    def next_pending(self) -> Item | None:
        return next((i for i in self.items if i.status is Status.PENDING), None)

    def mark(self, item_id: str, status: Status, *, fraction: float | None = None, message: str = "") -> None:
        item = self.get(item_id)
        item.status, item.fraction, item.message = status, fraction, message

    def retry_failed(self) -> int:
        n = 0
        for i in self.items:
            if i.status in (Status.FAILED, Status.CANCELLED):
                i.status, i.fraction, i.message = Status.PENDING, None, ""
                n += 1
        return n

    def remove(self, item_id: str) -> None:
        self.items = [i for i in self.items if i.id != item_id]
