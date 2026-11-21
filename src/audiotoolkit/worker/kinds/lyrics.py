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


def _vocal_notes(job: Job) -> list[tuple[float, float]]:
    """Note spans of opts["midi"], else of the song's own MIDI (the vocals' one if several)."""
    import glob

    import pretty_midi

    path = job.opts.get("midi")
    if not path:
        found = sorted(glob.glob(os.path.join(job.out_dir, "midi", "*.mid")))
        path = next((f for f in found if "vocal" in os.path.basename(f).lower()), found[0] if found else None)
    if not path:
        raise FileNotFoundError(f"no MIDI for this song in {job.out_dir}/midi; run MIDI on the vocals first or pick a file")
    insts = [i for i in pretty_midi.PrettyMIDI(path).instruments if not i.is_drum]
    singers = [i for i in insts if any(k in i.name.lower() for k in ("voice", "vocal", "choir"))]  # a full-mix MIDI
    return [(n.start, n.end) for inst in singers or insts for n in inst.notes]


def _reverse(job: Job) -> tuple[list[Output], dict]:
    """<name>.synthv.txt + the original text -> clean lyrics with the original's line breaks."""
    from audiotoolkit.core.synthv import from_synthv

    base = job.input[: -len(".synthv.txt")]
    originals = [base + ".txt", os.path.join(job.out_dir, "lyrics", os.path.basename(base) + ".txt")]
    original = next((p for p in originals if os.path.isfile(p)), None)
    if original is None:
        raise FileNotFoundError(f"original lyrics not found: put {os.path.basename(base)}.txt next to the file")
    with open(job.input, encoding="utf-8") as f, open(original, encoding="utf-8") as g:
        text, unconfirmed = from_synthv(f.read(), g.read())
    path = output_path(job, "lyrics", "txt", name=os.path.basename(base) + ".clean")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return [Output("lyrics", path)], {"language": "", "segments": 0, "unconfirmed": unconfirmed}


def run(job: Job, emit) -> tuple[list[Output], dict]:
    if job.input.lower().endswith(".synthv.txt"):
        return _reverse(job)
    synthv = bool(job.opts.get("synthv"))
    notes = _vocal_notes(job) if synthv else []  # fail before the slow transcription if there is no MIDI
    size = job.opts.get("model_size", "medium")
    device = job.opts.get("device", "auto")
    if (size, device) not in _cache:
        _cache.clear()
        _cache[(size, device)] = _load(size, device)
    emit(None, "transcribing")
    gen, info = _cache[(size, device)].transcribe(job.input, language=job.opts.get("language") or None, vad_filter=True,
                                                     word_timestamps=synthv)
    raw = list(gen)
    segs = [(s.start, s.end, s.text) for s in raw]
    words = [(w.start, w.end, w.word) for s in raw for w in (s.words or [])]
    outputs = []
    for role_ext, fmt in (("srt", format_srt), ("lrc", format_lrc), ("txt", format_txt)):
        path = output_path(job, "lyrics", role_ext)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(fmt(segs))
        outputs.append(Output("lyrics", path))
    result = {"language": info.language, "segments": len(segs)}
    if synthv:
        from audiotoolkit.core.synthv import to_synthv

        text, result["unplaced"] = to_synthv(words, notes)
        path = output_path(job, "lyrics", "synthv.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        outputs.append(Output("lyrics", path))
    return outputs, result
