"""The worker environment (torch, demucs, ...) is not part of the app: this plans and runs the commands that build it."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .settings import Settings

DATA_DIR = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "audio-toolkit"
WORKER_VENV = DATA_DIR / "venv"
REPOS = ("demucs", "dettato", "copisteria")
# From PyPI. PyAV is pinned because faster-whisper breaks on >= 17.
CUDA_LIBS = 'sys_platform == "linux" or sys_platform == "win32"'
BASE = ["torch", "torchaudio", "faster-whisper", "librosa", "soundfile", "huggingface_hub",
        f"nvidia-cublas-cu12; {CUDA_LIBS}", f"nvidia-cudnn-cu12; {CUDA_LIBS}"]
# PyPI's Linux torch already has CUDA; on Windows it is CPU-only, so NVIDIA machines take PyTorch's own CUDA wheels.
TORCH_CUDA_INDEX = "https://download.pytorch.org/whl/cu126"
PINS = ["av>=14,<17"]

Step = tuple[str, list[str]]


def venv_python(venv: Path = WORKER_VENV) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")


def is_url(spec: str) -> bool:
    return spec.startswith(("http://", "https://", "git@", "git+", "ssh://"))


def checkout_dir(name: str) -> Path:
    return DATA_DIR / "repos" / name


def local_checkout(settings: Settings, name: str) -> Path | None:
    """Where the repo's files live: the folder the user gave, or the clone made from its URL."""
    spec = settings.repos.get(name, "").strip()
    if not spec:
        return None
    return checkout_dir(name) if is_url(spec) else Path(spec).expanduser()


def has_nvidia() -> bool:
    return shutil.which("nvidia-smi") is not None


def plan(settings: Settings, base_python: str = sys.executable, venv: Path = WORKER_VENV,
         windows: bool = os.name == "nt", nvidia: bool | None = None) -> list[Step]:
    """Steps to make the worker environment match the settings. Re-running only repeats what is needed."""
    nvidia = has_nvidia() if nvidia is None else nvidia
    python = settings.worker_python or str(venv_python(venv))
    pip = [python, "-m", "pip", "install", "-q"]
    steps: list[Step] = []
    if not settings.worker_python and not Path(python).is_file():
        steps.append(("Creating the environment", [base_python, "-m", "venv", str(venv)]))
    steps.append(("Updating pip", [*pip, "-U", "pip"]))
    if windows:
        if nvidia:
            steps.append(("Installing torch (CUDA)", [*pip, "torch", "torchaudio", "--index-url", TORCH_CUDA_INDEX]))
        else:
            steps.append(("Installing torch (CPU only: no NVIDIA GPU found)", [*pip, "torch", "torchaudio"]))
    steps.append(("Installing whisper, librosa…", [*pip, *BASE]))
    for name in REPOS:
        spec = settings.repos.get(name, "").strip()
        if not spec:
            continue
        where = local_checkout(settings, name)
        if is_url(spec):
            if (where / ".git").is_dir():
                steps.append((f"Updating {name}", ["git", "-C", str(where), "pull", "--ff-only"]))
            else:
                steps.append((f"Cloning {name}", ["git", "clone", spec.removeprefix("git+"), str(where)]))
        steps.append((f"Installing {name}", [*pip, "-e", str(where)]))
    steps.append(("Pinning PyAV", [*pip, *PINS]))
    return steps


def run_plan(steps: list[Step], progress: Callable[[str], None]) -> str | None:
    """Runs the steps in order; returns None on success, else the failing step's last output line."""
    for label, cmd in steps:
        progress(label)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
        except OSError as e:
            return f"{label}: {e}"
        if r.returncode != 0:
            tail = (r.stderr or r.stdout).strip().splitlines()
            return f"{label}: {tail[-1] if tail else 'exit ' + str(r.returncode)}"
    return None
