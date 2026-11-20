import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
SOURCE = APP.parent / "demucs" / "test.mp3"


@pytest.fixture(scope="session")
def clip(tmp_path_factory) -> str:
    """10 s excerpt of demucs/test.mp3."""
    out = tmp_path_factory.mktemp("clip") / "clip.wav"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-t", "10", "-i", str(SOURCE), str(out)], check=True)
    return str(out)
