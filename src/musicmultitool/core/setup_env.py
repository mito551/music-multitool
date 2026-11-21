"""The worker environment (torch, demucs, ...) is not part of the app: this plans and runs the commands that build it."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from . import provision
from .components import BY_ID, IDS, mark_installed
from .paths import data_dir
from .proc import QUIET, TEXT
from .settings import Settings

DATA_DIR = data_dir()
WORKER_VENV = DATA_DIR / "venv"
REPOS = ("demucs", "dettato", "copisteria")
CUDA_LIBS = 'sys_platform == "linux" or sys_platform == "win32"'
TORCH_CUDA_INDEX = "https://download.pytorch.org/whl/cu126"  # Windows' PyPI torch is CPU-only
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"  # a few hundred MB instead of several GB
PINS = ["av>=14,<17"]  # faster-whisper breaks on PyAV >= 17

Step = tuple[str, "list[str] | Callable[[], None]"]  # a command to run, or a Python callable (downloads)


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


def _fail(message: str) -> Callable[[], None]:
    def raise_it() -> None:
        raise RuntimeError(message)

    return raise_it


def plan(settings: Settings, components: list[str] | None = None, base_python: str = sys.executable,
         venv: Path = WORKER_VENV, windows: bool = os.name == "nt", nvidia: bool | None = None) -> list[Step]:
    """Steps that install exactly the chosen components (default: all). Re-running only repeats what is needed."""
    chosen = [BY_ID[i] for i in (IDS if components is None else components) if i in BY_ID]
    if not chosen:
        return []
    ids = [c.id for c in chosen]
    gpu = settings.use_gpu and (has_nvidia() if nvidia is None else nvidia)
    missing = [c.repo for c in chosen if c.repo and not settings.repos.get(c.repo, "").strip()]
    if missing:  # before anything is downloaded
        return [(f"{', '.join(missing)}: set a folder or git URL on the Repos tab first", _fail("repo not set"))]
    python = settings.worker_python or str(venv_python(venv))
    steps: list[Step] = []
    if windows or provision.frozen():  # no Python to build with (a stock Windows, or a frozen app): uv fetches one
        uv = provision.tool_path("uv") or str(provision.bin_dir() / "uv" / ("uv.exe" if windows else "uv"))
        steps.append(("Fetching uv", lambda: provision.download("uv")))
        if windows:  # Linux users have these from their distribution
            steps.append(("Fetching ffmpeg", lambda: provision.download("ffmpeg")))
            if "score" in ids:
                steps.append(("Fetching poppler", lambda: provision.download("poppler")))
        pip = [uv, "pip", "install", "--python", python]
        if not settings.worker_python and not Path(python).is_file():
            steps.append(("Creating the environment", [uv, "venv", "--python", "3.12", str(venv)]))
    else:
        pip = [python, "-m", "pip", "install", "-q"]
        if not settings.worker_python and not Path(python).is_file():
            steps.append(("Creating the environment", [base_python, "-m", "venv", str(venv)]))
        steps.append(("Updating pip", [*pip, "-U", "pip"]))
    if any(c.needs_torch for c in chosen):
        torch = [*pip, "torch", "torchaudio"]
        if not gpu:
            steps.append(("Installing PyTorch (CPU only)", [*torch, "--index-url", TORCH_CPU_INDEX]))
        elif windows:
            steps.append(("Installing PyTorch (CUDA)", [*torch, "--index-url", TORCH_CUDA_INDEX]))
        else:  # PyPI's Linux build already has CUDA
            steps.append(("Installing PyTorch (CUDA)", torch))
    packages = [p for c in chosen for p in c.packages]
    if gpu and "lyrics" in ids:
        packages += [f"nvidia-cublas-cu12; {CUDA_LIBS}", f"nvidia-cudnn-cu12; {CUDA_LIBS}"]
    if packages:
        steps.append(("Installing libraries", [*pip, *packages]))
    for c in chosen:
        if not c.repo:
            continue
        spec = settings.repos[c.repo].strip()
        where = local_checkout(settings, c.repo)
        if is_url(spec):
            if (where / ".git").is_dir():
                steps.append((f"Updating {c.repo}", ["git", "-C", str(where), "pull", "--ff-only"]))
            else:
                steps.append((f"Cloning {c.repo}", ["git", "clone", spec.removeprefix("git+"), str(where)]))
        steps.append((f"Installing {c.repo}", [*pip, "-e", str(where)]))
    if "lyrics" in ids:
        steps.append(("Pinning PyAV", [*pip, *PINS]))
    steps.append(("Recording what is installed", lambda: mark_installed(ids)))
    return steps


def run_plan(steps: list[Step], progress: Callable[[str], None]) -> str | None:
    """Runs the steps in order; returns None on success, else the failing step's last output line."""
    for label, cmd in steps:
        progress(label)
        if callable(cmd):
            try:
                cmd()
            except Exception as e:  # download or unpack failed
                return f"{label}: {e}"
            continue
        try:
            r = subprocess.run(cmd, capture_output=True, **TEXT, **QUIET)
        except OSError as e:
            return f"{label}: {e}"
        if r.returncode != 0:
            tail = (r.stderr or r.stdout).strip().splitlines()
            return f"{label}: {tail[-1] if tail else 'exit ' + str(r.returncode)}"
    return None
