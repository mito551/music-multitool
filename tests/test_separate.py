import os

import pytest
import torch

from musicmultitool.core.protocol import Job
from musicmultitool.worker.kinds.separate import run, separate_progress, two_stem


def info(shift=0, offset=0, length=1000, models=1, model_idx=0):
    return {"model_idx_in_bag": model_idx, "shift_idx": shift, "segment_offset": offset,
            "audio_length": length, "models": models, "state": "end"}


def test_progress_start_is_zero():
    assert separate_progress(info(), 1) == 0.0


def test_progress_half_of_single_pass():
    assert separate_progress(info(offset=500), 1) == 0.5


def test_progress_clamps_to_one():
    assert separate_progress(info(offset=1500), 1) == 1.0


def test_progress_two_shifts_second_pass():
    assert separate_progress(info(shift=1), 2) == 0.5


def test_two_stem_sums_others():
    sep = {n: torch.ones(2, 4) for n in ("drums", "bass", "other", "vocals")}
    out = two_stem(sep, "vocals")
    assert set(out) == {"vocals", "no_vocals"}
    assert torch.equal(out["no_vocals"], torch.full((2, 4), 3.0))


@pytest.mark.slow
def test_separate_clip_writes_all_stems(clip, tmp_path):
    job = Job("j", "separate", clip, {}, str(tmp_path / "out"))
    outputs, _ = run(job, lambda frac, note="": None)
    assert sorted(o.role for o in outputs) == ["stem:bass", "stem:drums", "stem:other", "stem:vocals"]
    assert all(os.path.exists(o.path) for o in outputs)
