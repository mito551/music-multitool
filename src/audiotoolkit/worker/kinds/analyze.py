"""BPM and key detection with librosa."""
from __future__ import annotations

import json
import os
import subprocess

import numpy as np

from audiotoolkit.core.outputs import output_path
from audiotoolkit.core.protocol import Job, Output

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
SR = 22050


def key_from_chroma(chroma: np.ndarray) -> tuple[str, float]:
    """Best of the 24 rotated Krumhansl-Kessler profiles; confidence is its Pearson correlation."""
    best = ("", -2.0)
    for mode, profile in (("major", MAJOR), ("minor", MINOR)):
        for tonic in range(12):
            r = np.nan_to_num(np.corrcoef(chroma, np.roll(profile, tonic))[0, 1])
            if r > best[1]:
                best = (f"{NOTES[tonic]} {mode}", float(r))
    return best


def _load(path: str):
    """librosa/soundfile first; formats libsndfile cannot open (m4a, ALAC, AAC) are decoded by ffmpeg."""
    import librosa

    try:
        return librosa.load(path, sr=SR, mono=True)
    except Exception:
        r = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", path, "-vn", "-f", "f32le", "-ac", "1",
                            "-ar", str(SR), "-"], capture_output=True)
        if r.returncode != 0:
            lines = r.stderr.decode(errors="replace").strip().splitlines()
            raise RuntimeError(lines[-1] if lines else f"ffmpeg exited {r.returncode}")
        return np.frombuffer(r.stdout, dtype=np.float32), SR


def detect(path: str) -> dict:
    import librosa

    y, sr = _load(path)
    if len(y) == 0 or float(np.sqrt(np.mean(y**2))) < 1e-4:
        return {"bpm": None, "bpm_candidates": [], "key": None, "key_confidence": 0.0}
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, _ = librosa.beat.beat_track(onset_envelope=onset, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    key, conf = key_from_chroma(librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1))
    return {"bpm": bpm, "bpm_candidates": [bpm / 2, bpm * 2], "key": key, "key_confidence": conf}


def run(job: Job, emit) -> tuple[list[Output], dict]:
    emit(None, "analyzing")
    result = detect(job.input)
    path = output_path(job, "analysis", "json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
    return [Output("analysis", path)], result
