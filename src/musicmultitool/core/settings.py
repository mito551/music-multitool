"""User settings, stored as JSON."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields

from .paths import config_dir


def default_path() -> str:
    return str(config_dir() / "settings.json")


@dataclass
class Settings:
    out_root: str = field(default_factory=lambda: os.path.expanduser("~/Music/music-multitool"))
    skip_existing: bool = True
    device: str = "auto"
    tab_opts: dict = field(default_factory=dict)
    repos: dict = field(default_factory=dict)  # name -> local checkout or git URL; empty/missing = not installed
    worker_python: str = ""  # empty: the environment the app sets up for itself
    extra_path: str = ""  # directories prepended to the worker's PATH (ffmpeg, poppler)
    components: list = field(default_factory=list)  # ids picked for installation (see components.py)
    use_gpu: bool = True  # NVIDIA CUDA build of PyTorch where a GPU exists; False = the much smaller CPU build
    frontend: str = "auto"  # auto (by desktop), gtk or qt; takes effect on the next start
    sidebar_width: int = 240
    queue_height: int = 240


def load_settings(path: str | None = None) -> Settings:
    try:
        with open(os.path.expanduser(path or default_path())) as f:
            data = json.load(f)
        known = {f.name for f in fields(Settings)}
        return Settings(**{k: v for k, v in data.items() if k in known})
    except (OSError, ValueError, TypeError):
        return Settings()


def save_settings(s: Settings, path: str | None = None) -> None:
    path = os.path.expanduser(path or default_path())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(asdict(s), f, indent=2)
