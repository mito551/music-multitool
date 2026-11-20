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


def _encode(clip, tmp_path_factory, name, codec_args):
    out = tmp_path_factory.mktemp(name) / f"{name}.m4a"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", clip, *codec_args, str(out)], check=True)
    return str(out)


@pytest.fixture(scope="session")
def clip_alac(clip, tmp_path_factory) -> str:
    return _encode(clip, tmp_path_factory, "alac", ["-c:a", "alac"])


@pytest.fixture(scope="session")
def clip_aac(clip, tmp_path_factory) -> str:
    return _encode(clip, tmp_path_factory, "aac", ["-c:a", "aac", "-b:a", "256k"])
