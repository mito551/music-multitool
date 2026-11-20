import numpy as np
import soundfile as sf

from audiotoolkit.worker.kinds.analyze import detect, key_from_chroma

SR = 22050


def chroma(*notes):
    v = np.zeros(12)
    v[list(notes)] = 1.0
    return v


def test_key_c_major_triad():
    assert key_from_chroma(chroma(0, 4, 7))[0] == "C major"


def test_key_a_minor_triad():
    name, conf = key_from_chroma(chroma(9, 0, 4))
    assert name == "A minor" and 0 < conf <= 1


def test_bpm_click_track_120(tmp_path):
    y = np.zeros(SR * 10)
    burst = np.sin(2 * np.pi * 1000 * np.arange(int(0.03 * SR)) / SR) * np.hanning(int(0.03 * SR))
    for t in np.arange(0, 10, 0.5):
        i = int(t * SR)
        y[i:i + len(burst)] += burst
    path = str(tmp_path / "click.wav")
    sf.write(path, y, SR)
    r = detect(path)
    assert abs(r["bpm"] - 120) <= 3.6  # librosa quantizes tempo bins: 117.45 for a 120 BPM click track


def test_silence_returns_none(tmp_path):
    path = str(tmp_path / "silence.wav")
    sf.write(path, np.zeros(SR * 5), SR)
    r = detect(path)
    assert r["bpm"] is None and r["key"] is None and r["key_confidence"] == 0.0
