import pretty_midi
import pytest

from musicmultitool.core.protocol import Job
from musicmultitool.worker.kinds.midi import run


@pytest.mark.slow
def test_midi_clip_writes_parseable_file(clip, tmp_path):
    job = Job("j", "midi", clip, {}, str(tmp_path / "out"))
    outputs, result = run(job, lambda frac, note="": None)
    assert [o.role for o in outputs] == ["midi"]
    assert pretty_midi.PrettyMIDI(outputs[0].path).instruments
    assert result["tracks"]
