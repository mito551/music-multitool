"""`music-multitool --install-desktop`: launcher entry and icon under ~/.local/share, pointing at this install."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_ID = "io.github.mito551.MusicMultitool"
HERE = Path(__file__).resolve().parent  # the .desktop template and icon sit beside this module


def launcher() -> str:
    sibling = Path(sys.executable).with_name("music-multitool")  # next to the interpreter of a venv/pipx install
    exe = shutil.which("music-multitool") or (str(sibling) if sibling.is_file() else None)
    return exe or f"{sys.executable} -m musicmultitool"


def install(data_home: Path | None = None) -> Path:
    data = data_home or Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    apps, icons = data / "applications", data / "icons" / "hicolor" / "256x256" / "apps"
    apps.mkdir(parents=True, exist_ok=True)
    icons.mkdir(parents=True, exist_ok=True)
    target = apps / f"{APP_ID}.desktop"
    target.write_text((HERE / f"{APP_ID}.desktop").read_text().replace("@EXEC@", launcher()))
    shutil.copy(HERE / "music-multitool.png", icons / "music-multitool.png")
    return target
