"""Environment check: every library the worker needs, run once on a 10 s clip. Prints ENV OK on success."""
import subprocess
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
SOURCE = APP.parent / "demucs" / "test.mp3"


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True)


def main() -> int:
    ok = True
    tmp = Path(tempfile.mkdtemp())
    clip = str(tmp / "clip.wav")
    sh("ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-t", "10", "-i", str(SOURCE), clip).check_returncode()

    import torch

    cuda = torch.cuda.is_available()
    print("torch cuda:", cuda, torch.cuda.get_device_name(0) if cuda else "-")
    device = "cuda" if cuda else "cpu"

    from demucs.api import Separator

    _, stems = Separator(model="htdemucs", device=device).separate_audio_file(Path(clip))
    print("demucs stems:", sorted(stems))

    from dettato import Dettato

    result = Dettato.from_pretrained().transcribe(clip)
    print("dettato tracks:", len(result.tracks))

    try:
        from faster_whisper import WhisperModel

        model = WhisperModel("tiny", device="cuda", compute_type="float16")
        list(model.transcribe(clip)[0])
        print("whisper: cuda")
    except Exception as e:  # not fatal: Task 8 falls back to CPU
        print(f"whisper: cpu fallback ({e})")

    import librosa

    y, sr = librosa.load(clip, sr=22050)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    print("librosa tempo:", tempo)

    r = sh("ffmpeg", "-version")
    print("ffmpeg:", r.stdout.splitlines()[0] if r.returncode == 0 else "MISSING")
    ok &= r.returncode == 0

    r = sh("/usr/bin/python3", "-c", "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1')")
    print("gtk4/adw:", "ok" if r.returncode == 0 else f"MISSING {r.stderr.strip()}")
    ok &= r.returncode == 0

    print("ENV OK" if ok else "ENV FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
