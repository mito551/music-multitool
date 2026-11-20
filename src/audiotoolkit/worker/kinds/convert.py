"""Convert/trim with ffmpeg."""
from __future__ import annotations

import os
import subprocess

from audiotoolkit.core.outputs import output_path
from audiotoolkit.core.protocol import Job, Output

CODECS = {
    "mp3": ["-c:a", "libmp3lame", "-b:a", "320k"],
    "alac": ["-c:a", "alac"],  # lossless, in an .m4a container
    "m4a": ["-c:a", "aac", "-b:a", "256k"],
}
EXTENSIONS = {"alac": "m4a"}
_TRIM = "silenceremove=start_periods=1:start_threshold=-50dB"


def build_ffmpeg_args(src: str, dst: str, opts: dict) -> list[str]:
    args = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error"]
    if opts.get("start") is not None:
        args += ["-ss", str(opts["start"])]
    if opts.get("end") is not None:
        args += ["-to", str(opts["end"])]
    args += ["-i", src, "-vn"]
    filters = []
    if opts.get("trim_silence"):
        filters.append(f"{_TRIM},areverse,{_TRIM},areverse")
    if opts.get("loudnorm") is not None:
        filters.append(f"loudnorm=I={opts['loudnorm']}:TP=-1.5:LRA=11")
    if filters:
        args += ["-af", ",".join(filters)]
    if opts.get("sample_rate"):
        args += ["-ar", str(opts["sample_rate"])]
    if opts.get("channels"):
        args += ["-ac", str(opts["channels"])]
    args += CODECS.get(opts.get("format", "wav"), [])
    return args + [dst]


def run(job: Job, emit) -> tuple[list[Output], dict]:
    fmt = job.opts.get("format", "wav")
    dst = output_path(job, "audio", EXTENSIONS.get(fmt, fmt))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    emit(None, "converting")
    r = subprocess.run(build_ffmpeg_args(job.input, dst, job.opts), capture_output=True, text=True)
    if r.returncode != 0:
        lines = r.stderr.strip().splitlines()
        raise RuntimeError(lines[-1] if lines else f"ffmpeg exited {r.returncode}")
    return [Output("audio", dst)], {}
