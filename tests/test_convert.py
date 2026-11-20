import subprocess
import sys

from audiotoolkit.core.protocol import Done, Failed, Job, decode_event, encode_job
from audiotoolkit.worker.kinds.convert import build_ffmpeg_args, run

BASE = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error"]


def sine(path, seconds=5):
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"sine=frequency=440:duration={seconds}", str(path)], check=True)
    return str(path)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def test_args_minimal():
    assert build_ffmpeg_args("/a.mp3", "/b.wav", {}) == BASE + ["-i", "/a.mp3", "-vn", "/b.wav"]


def test_args_all_options_order():
    opts = {"start": 1.0, "end": 3.0, "trim_silence": True, "loudnorm": -14, "sample_rate": 44100, "channels": 2}
    a = build_ffmpeg_args("/a.mp3", "/b.wav", opts)
    assert a.index("-ss") < a.index("-i") and a.index("-to") < a.index("-i")
    assert a[a.index("-ss") + 1] == "1.0" and a[a.index("-to") + 1] == "3.0"
    af = a[a.index("-af") + 1]
    trim = "silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse"
    assert af == trim + ",loudnorm=I=-14:TP=-1.5:LRA=11"
    assert a[a.index("-ar") + 1] == "44100" and a[a.index("-ac") + 1] == "2"
    assert a[-1] == "/b.wav"


def test_mp3_uses_libmp3lame():
    a = build_ffmpeg_args("/a.wav", "/b.mp3", {"format": "mp3"})
    assert a[a.index("-c:a") + 1] == "libmp3lame" and a[a.index("-b:a") + 1] == "320k"


def test_run_trims_to_two_seconds(tmp_path):
    src = sine(tmp_path / "tone.wav")
    job = Job("j", "convert", src, {"start": 1, "end": 3}, str(tmp_path / "out"))
    outputs, _ = run(job, lambda frac, note="": None)
    assert [o.role for o in outputs] == ["audio"]
    assert outputs[0].path == str(tmp_path / "out" / "audio" / "tone.wav")
    assert abs(duration(outputs[0].path) - 2.0) < 0.1


def test_convert_corrupt_input_emits_failed_and_worker_survives(tmp_path):
    bad = tmp_path / "x.mp3"
    bad.write_text("not audio")
    good = sine(tmp_path / "ok.wav", 1)
    p = subprocess.Popen([sys.executable, "-m", "audiotoolkit.worker"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        def ask(job):
            p.stdin.write(encode_job(job) + "\n")
            p.stdin.flush()
            while True:
                ev = decode_event(p.stdout.readline())
                if isinstance(ev, (Done, Failed)):
                    return ev

        ev = ask(Job("a", "convert", str(bad), {}, str(tmp_path / "o1")))
        assert isinstance(ev, Failed) and ev.message.strip()
        assert isinstance(ask(Job("b", "convert", good, {}, str(tmp_path / "o2"))), Done)
    finally:
        p.kill()
