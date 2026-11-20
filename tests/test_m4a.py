import subprocess

import pytest

from audiotoolkit.core.protocol import Job
from audiotoolkit.worker.kinds import analyze, convert


def codec(path):
    return subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name",
                           "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip()


def no_progress(frac, note=""):
    pass


def test_args_alac_and_aac():
    alac = convert.build_ffmpeg_args("/a.wav", "/b.m4a", {"format": "alac"})
    assert alac[alac.index("-c:a") + 1] == "alac"
    aac = convert.build_ffmpeg_args("/a.wav", "/b.m4a", {"format": "m4a"})
    assert aac[aac.index("-c:a") + 1] == "aac" and aac[aac.index("-b:a") + 1] == "256k"


@pytest.mark.parametrize("fmt,expected", [("alac", "alac"), ("m4a", "aac")])
def test_convert_writes_m4a(clip, tmp_path, fmt, expected):
    job = Job("j", "convert", clip, {"format": fmt}, str(tmp_path / "out"))
    outputs, _ = convert.run(job, no_progress)
    assert outputs[0].path.endswith("/audio/clip.m4a") and codec(outputs[0].path) == expected


@pytest.mark.parametrize("fixture", ["clip_alac", "clip_aac"])
def test_analyze_reads_m4a_input(request, tmp_path, fixture):
    src = request.getfixturevalue(fixture)
    outputs, result = analyze.run(Job("j", "analyze", src, {}, str(tmp_path / "out")), no_progress)
    assert result["bpm"] and result["key"]


@pytest.mark.slow
@pytest.mark.parametrize("kind", ["convert", "separate", "midi", "lyrics"])
@pytest.mark.parametrize("fixture", ["clip_alac", "clip_aac"])
def test_every_kind_reads_m4a_input(request, tmp_path, kind, fixture):
    import importlib

    src = request.getfixturevalue(fixture)
    opts = {"model_size": "tiny"} if kind == "lyrics" else {}
    mod = importlib.import_module(f"audiotoolkit.worker.kinds.{kind}")
    outputs, _ = mod.run(Job("j", kind, src, opts, str(tmp_path / "out")), no_progress)
    assert outputs
