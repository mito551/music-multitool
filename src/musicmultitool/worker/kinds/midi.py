"""Audio to MIDI with dettato."""
from __future__ import annotations

import os

from musicmultitool.core.outputs import output_path
from musicmultitool.core.protocol import Job, Output

_cache: dict = {}


def release() -> None:
    _cache.clear()


def run(job: Job, emit) -> tuple[list[Output], dict]:
    from dettato import Dettato
    from dettato.pipeline import default_device

    device = job.opts.get("device", "auto")
    if device == "auto":
        device = default_device()
    if device not in _cache:
        _cache.clear()
        _cache[device] = Dettato.from_pretrained(device)
    emit(None, "transcribing")
    transcription = _cache[device].transcribe(job.input)
    path = output_path(job, "midi", "mid")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    transcription.save_midi(path)
    return [Output("midi", path)], transcription.summary()
