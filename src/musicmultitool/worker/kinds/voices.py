"""Split a polyphonic MIDI file into N melodic voices (deterministic core, no model)."""
from __future__ import annotations

import os
from pathlib import Path

from musicmultitool.core.outputs import output_path
from musicmultitool.core.protocol import Job, Output
from musicmultitool.core.voicesep import Params, default_voices, read_midi, separate, write_midi, write_report


def run(job: Job, emit) -> tuple[list[Output], dict]:
    emit(None, "reading MIDI")
    m = read_midi(job.input)
    voices = default_voices(int(job.opts.get("voices", 4)))
    emit(None, "separating voices")
    assignment, report = separate(m, voices, Params(mode=job.opts.get("mode", "auto")))
    stem = f"{Path(job.input).stem}.voices"
    mid, rep = output_path(job, "midi", "mid", stem), output_path(job, "analysis", "json", stem)
    os.makedirs(os.path.dirname(mid), exist_ok=True)
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    write_midi(m, voices, assignment, mid)
    write_report(report, rep)
    return [Output("midi", mid), Output("analysis", rep)], {"voices": len(voices), "notes": len(m.notes), "mode": report["mode"]}
