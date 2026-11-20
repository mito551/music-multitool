"""Stem separation with demucs."""
from __future__ import annotations

import os
from pathlib import Path

from audiotoolkit.core.outputs import output_path
from audiotoolkit.core.protocol import Job, Output

_cache: dict = {}


def separate_progress(info: dict, shifts: int) -> float:
    passes = info["models"] * shifts
    done = info["model_idx_in_bag"] * shifts + info["shift_idx"] + info["segment_offset"] / info["audio_length"]
    return min(1.0, max(0.0, done / passes))


def two_stem(separated: dict, stem: str) -> dict:
    return {stem: separated[stem], f"no_{stem}": sum(w for n, w in separated.items() if n != stem)}


def release() -> None:
    _cache.clear()


def run(job: Job, emit) -> tuple[list[Output], dict]:
    import torch
    from demucs.api import Separator, save_audio

    model = job.opts.get("model", "htdemucs")
    shifts = int(job.opts.get("shifts", 1))
    device = job.opts.get("device", "auto")
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    key = (model, device, shifts)
    if key not in _cache:
        _cache.clear()
        _cache[key] = Separator(model=model, device=device, shifts=shifts)
    sep = _cache[key]

    def on_progress(info: dict) -> None:
        if info["state"] == "end":
            emit(separate_progress(info, shifts), "separating")

    sep.update_parameter(callback=on_progress)
    emit(0.0, "separating")
    _, stems = sep.separate_audio_file(Path(job.input))
    wanted = job.opts.get("stems", "all")
    if wanted != "all":
        stems = two_stem(stems, wanted)
    fmt = job.opts.get("format", "wav")
    outputs = []
    for name, wav in stems.items():
        path = output_path(job, f"stem:{name}", fmt, name=name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        save_audio(wav, path, samplerate=sep.samplerate)
        outputs.append(Output(f"stem:{name}", path))
    return outputs, {}
