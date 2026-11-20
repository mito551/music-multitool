"""Lyrics/transcript with faster-whisper."""
from __future__ import annotations

import os

from audiotoolkit.core.outputs import output_path
from audiotoolkit.core.protocol import Job, Output

Seg = tuple[float, float, str]
_cache: dict = {}


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def format_srt(segs: list[Seg]) -> str:
    return "".join(f"{i}\n{_srt_time(a)} --> {_srt_time(b)}\n{text.strip()}\n\n" for i, (a, b, text) in enumerate(segs, 1))


def format_lrc(segs: list[Seg]) -> str:
    out = []
    for a, _, text in segs:
        cs = int(round(a * 100))
        out.append(f"[{cs // 6000:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}]{text.strip()}\n")
    return "".join(out)


def format_txt(segs: list[Seg]) -> str:
    return "".join(f"{text.strip()}\n" for _, _, text in segs)


def _preload_cuda_libs() -> None:
    """CTranslate2 needs cuBLAS 12 / cuDNN 9, which pip installs under site-packages/nvidia/*/lib, off the loader path."""
    import ctypes
    import glob
    import importlib.util

    for pkg, pattern in (("nvidia.cublas", "libcublas*.so.12"), ("nvidia.cudnn", "libcudnn*.so.9")):
        try:
            spec = importlib.util.find_spec(pkg)
        except ModuleNotFoundError:
            continue
        for loc in (spec.submodule_search_locations or []) if spec else []:
            for f in sorted(glob.glob(os.path.join(loc, "lib", pattern))):
                try:
                    ctypes.CDLL(f, mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass


def _load(size: str, device: str):
    from faster_whisper import WhisperModel

    if device in ("auto", "cuda"):
        _preload_cuda_libs()
        try:
            return WhisperModel(size, device="cuda", compute_type="float16")
        except Exception:
            if device == "cuda":
                raise
    return WhisperModel(size, device="cpu", compute_type="int8")


def release() -> None:
    _cache.clear()


def run(job: Job, emit) -> tuple[list[Output], dict]:
    size = job.opts.get("model_size", "medium")
    device = job.opts.get("device", "auto")
    if (size, device) not in _cache:
        _cache.clear()
        _cache[(size, device)] = _load(size, device)
    emit(None, "transcribing")
    gen, info = _cache[(size, device)].transcribe(job.input, language=job.opts.get("language") or None, vad_filter=True)
    segs = [(s.start, s.end, s.text) for s in gen]
    outputs = []
    for role_ext, fmt in (("srt", format_srt), ("lrc", format_lrc), ("txt", format_txt)):
        path = output_path(job, "lyrics", role_ext)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(fmt(segs))
        outputs.append(Output("lyrics", path))
    return outputs, {"language": info.language, "segments": len(segs)}
