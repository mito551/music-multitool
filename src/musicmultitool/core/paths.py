"""Where the app keeps its files: config (small, roaming on Windows) and data (GBs: environment, repos, tools)."""
from __future__ import annotations

import os
from pathlib import Path


def config_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "MusicMultitool"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "music-multitool"


def data_dir() -> Path:
    if os.name == "nt":  # local, not roaming: the worker environment is several GB
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "MusicMultitool"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "music-multitool"


def user_presets_dir() -> str:
    return str(config_dir() / "presets")
