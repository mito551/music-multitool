"""Tools and files the app fetches or reuses: ffmpeg, poppler and uv on Windows, the worker's source when frozen."""
from __future__ import annotations

import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .paths import config_dir, data_dir

UV_URL = {"nt": "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip",
          "posix": "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz"}
URLS = {  # Windows builds, except uv
    "uv": UV_URL["nt" if os.name == "nt" else "posix"],
    "ffmpeg": "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip",
    "poppler": "https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip",
}
EXE = {"uv": "uv", "ffmpeg": "ffmpeg", "poppler": "pdftoppm"}  # the program that proves a download is present


def bin_dir() -> Path:
    return data_dir() / "bin"


def _exe(name: str) -> str:
    return name + (".exe" if os.name == "nt" else "")


def tool_path(name: str, extra_path: str = "") -> str | None:
    """A tool already on the user's PATH (or extra_path) is reused; otherwise one we downloaded earlier."""
    found = shutil.which(name, path=os.pathsep.join(filter(None, [extra_path, os.environ.get("PATH", "")])))
    if found:
        return found
    return next((str(p) for p in bin_dir().rglob(_exe(name)) if p.is_file()), None)


def tool_dirs() -> list[str]:
    """Folders of the downloaded tools, for the worker's PATH."""
    dirs = {str(Path(p).parent) for n in ("ffmpeg", "ffprobe", "pdftoppm") for p in bin_dir().rglob(_exe(n)) if p.is_file()}
    return sorted(dirs)


def download(tool: str) -> None:
    """Fetch and unpack one tool under <data>/bin/<tool>; does nothing if it is already usable."""
    if tool_path(EXE[tool]):
        return
    dest = bin_dir() / tool
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "pkg"
        with urllib.request.urlopen(URLS[tool], timeout=60) as r, open(archive, "wb") as f:
            shutil.copyfileobj(r, f)
        if URLS[tool].endswith(".zip"):
            with zipfile.ZipFile(archive) as z:
                z.extractall(dest)
        else:
            with tarfile.open(archive) as t:
                t.extractall(dest, filter="data")
    if not tool_path(EXE[tool]):
        raise RuntimeError(f"{tool} downloaded but {EXE[tool]} was not found in it")


# -- the worker's copy of this package -----------------------------------------------------------------------------

def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_src() -> Path:
    """Folder holding the plain-Python `musicmultitool` package: the source tree, or the data shipped inside the exe."""
    if frozen():
        return Path(sys._MEIPASS) / "musicmultitool_src"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


def worker_src() -> Path:
    """Where the worker imports `musicmultitool` from. A frozen exe unpacks to a temporary folder each run, so the package
    is copied to a stable place (again whenever the exe changed)."""
    if not frozen():
        return bundle_src()
    target = data_dir() / "worker_src"
    stamp = target / ".stamp"
    mark = str(os.stat(sys.executable).st_mtime_ns)
    if not stamp.is_file() or stamp.read_text() != mark:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(bundle_src() / "musicmultitool", target / "musicmultitool")
        stamp.write_text(mark)
    return target


# -- removing what the app stored -------------------------------------------------------------------------------

def _is_app_dir(p: Path) -> bool:
    return p.name in ("MusicMultitool", "music-multitool") and len(p.parts) > 2


def data_size() -> int:
    d = data_dir()
    return sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) if d.is_dir() else 0


def remove_data(include_settings: bool = False) -> list[str]:
    """Delete the downloaded environment, repos and tools (and optionally settings and your own chains).
    Returns the folders removed."""
    removed = []
    for d in (data_dir(), config_dir()) if include_settings else (data_dir(),):
        if d.is_dir() and _is_app_dir(d):
            shutil.rmtree(d)
            removed.append(str(d))
    return removed
