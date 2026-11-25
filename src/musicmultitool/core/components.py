"""The optional heavy parts: what each does, roughly how much disk it takes, what it needs. Nothing is installed unasked."""
from __future__ import annotations

import json
from dataclasses import dataclass

from .paths import data_dir


@dataclass(frozen=True)
class Component:
    id: str
    name: str
    function: str
    mb: int  # own size on disk, excluding PyTorch (approximate)
    needs_torch: bool = False
    repo: str = ""  # which entry of Settings.repos it installs from
    packages: tuple[str, ...] = ()
    note: str = ""  # sizes of things fetched later, on first use


COMPONENTS = (
    Component("convert", "Convert / Trim", "Format, sample-rate and loudness conversion, trimming silence (uses ffmpeg).", 20),
    Component("analyze", "BPM & key detection", "Detects tempo and musical key (librosa, numba, scipy).", 400,
              packages=("librosa", "soundfile")),
    Component("separate", "Stem separation", "Splits a song into vocals, drums, bass and other (demucs).", 120,
              needs_torch=True, repo="demucs", note="Model weights, 80–400 MB each, download on first use."),
    Component("midi", "Audio to MIDI", "Transcribes notes and drums to a MIDI file (dettato).", 250,
              needs_torch=True, repo="dettato", note="Model weights download on first use (a few hundred MB)."),
    Component("voices", "Voice separation", "Splits a polyphonic MIDI file into separate melodic voices (mido).", 5,
              packages=("mido",)),
    Component("lyrics", "Lyrics", "Transcribes sung lyrics with timestamps, optional SynthV format (faster-whisper).", 250,
              packages=("faster-whisper", "huggingface_hub"),
              note="Whisper model downloads on first use: 75 MB (tiny) to 3 GB (large-v3). +1.5 GB of CUDA libraries on an NVIDIA GPU."),
    Component("score", "Sheet-music scan", "Reads scanned scores and PDFs into MusicXML (copisteria).", 350,
              needs_torch=True, repo="copisteria", note="+130 MB of model weights (Models tab); PDFs need poppler."),
)
IDS = [c.id for c in COMPONENTS]
BY_ID = {c.id: c for c in COMPONENTS}

# PyTorch, shared by the components that need it. Approximate disk use; the download is smaller.
TORCH_MB = {"linux-cuda": 6500, "windows-cuda": 4500, "cpu": 700}
FFMPEG_MB_WINDOWS = 280  # downloaded only on Windows when ffmpeg is not already on PATH
CUDA_LIBS_MB = 1500  # cuBLAS + cuDNN for faster-whisper on a GPU


def torch_mb(gpu: bool, windows: bool) -> int:
    return TORCH_MB["cpu"] if not gpu else TORCH_MB["windows-cuda" if windows else "linux-cuda"]


def estimate_mb(selected: list[str], gpu: bool, windows: bool) -> int:
    """Disk the selected components add, including PyTorch once if any of them needs it."""
    comps = [BY_ID[i] for i in selected if i in BY_ID]
    total = sum(c.mb for c in comps)
    if any(c.needs_torch for c in comps):
        total += torch_mb(gpu, windows)
    if gpu and "lyrics" in selected:
        total += CUDA_LIBS_MB
    if windows and comps:
        total += FFMPEG_MB_WINDOWS
    return total


def human(mb: int) -> str:
    return f"{mb / 1000:.1f} GB" if mb >= 1000 else f"{mb} MB"


# -- what is installed -------------------------------------------------------------------------------------------

def _marker():
    return data_dir() / "installed.json"


def installed() -> list[str]:
    try:
        return [i for i in json.loads(_marker().read_text()) if i in BY_ID]
    except (OSError, ValueError):
        return []


def mark_installed(ids: list[str]) -> None:
    _marker().parent.mkdir(parents=True, exist_ok=True)
    _marker().write_text(json.dumps(sorted(set(installed()) | set(ids))))
