import os

from musicmultitool.core.outputs import (
    load_manifest, manifest_path, output_path, song_dir, write_manifest,
)
from musicmultitool.core.protocol import Job, Output


def job(tmp_path, **kw):
    base = dict(id="j", kind="separate", input="/in/My Song.mp3", opts={"model": "x"}, out_dir=str(tmp_path / "My Song"))
    base.update(kw)
    return Job(**base)


def test_song_dir():
    assert song_dir("/out", "My Song") == "/out/My Song"


def test_output_path_by_role(tmp_path):
    j = job(tmp_path)
    d = j.out_dir
    assert output_path(j, "stem:vocals", "wav", name="vocals") == f"{d}/stems/vocals.wav"
    assert output_path(j, "midi", "mid") == f"{d}/midi/My Song.mid"
    assert output_path(j, "lyrics", "srt") == f"{d}/lyrics/My Song.srt"
    assert output_path(j, "audio", "flac", name="x") == f"{d}/audio/x.flac"
    assert output_path(j, "analysis", "json") == f"{d}/analysis/My Song.json"


def test_manifest_roundtrip(tmp_path):
    j = job(tmp_path)
    f = tmp_path / "a.wav"
    f.write_bytes(b"x")
    outs = [Output("audio", str(f))]
    write_manifest(j, outs)
    assert load_manifest(j) == outs


def test_manifest_none_when_absent(tmp_path):
    assert load_manifest(job(tmp_path)) is None


def test_manifest_none_when_file_missing(tmp_path):
    j = job(tmp_path)
    f = tmp_path / "a.wav"
    f.write_bytes(b"x")
    write_manifest(j, [Output("audio", str(f))])
    os.remove(f)
    assert load_manifest(j) is None


def test_manifest_path_differs_by_opts_and_input(tmp_path):
    a = manifest_path(job(tmp_path))
    assert a != manifest_path(job(tmp_path, opts={"model": "y"}))
    assert a != manifest_path(job(tmp_path, input="/in/other.mp3"))
    assert a.startswith(str(tmp_path / "My Song" / ".manifests" / "separate-"))


def test_manifest_none_after_output_overwritten(tmp_path):
    j = job(tmp_path)
    f = tmp_path / "a.wav"
    f.write_bytes(b"first")
    write_manifest(j, [Output("audio", str(f))])
    f.write_bytes(b"second, longer")
    assert load_manifest(j) is None


def test_manifest_none_after_mtime_change(tmp_path):
    j = job(tmp_path)
    f = tmp_path / "a.wav"
    f.write_bytes(b"same")
    write_manifest(j, [Output("audio", str(f))])
    st = os.stat(f)
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert load_manifest(j) is None
