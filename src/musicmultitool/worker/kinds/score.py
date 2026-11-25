"""Sheet music (image or PDF) to MusicXML with copisteria, one file per page."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

from musicmultitool.core.outputs import output_path
from musicmultitool.core.protocol import Job, Output

_cache: dict = {}

def release() -> None:
    _cache.clear()

def parse_pages(spec: str, count: int) -> list[int]:
    """'all' or '' = every page, 'N', or 'A-B' (B clamped to the page count)."""
    spec = spec.strip().lower()
    if spec in ("", "all"):
        return list(range(1, count + 1))
    m = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", spec)
    if not m or int(m[1]) < 1 or int(m[1]) > count:
        raise ValueError(f"pages '{spec}' not in 1-{count}")
    lo = int(m[1])
    return list(range(lo, min(int(m[2] or lo), count) + 1))

def _page_count(pdf: str) -> int:
    out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True, check=True).stdout
    return int(re.search(r"^Pages:\s+(\d+)", out, re.M)[1])

def run(job: Job, emit) -> tuple[list[Output], dict]:
    from copisteria import pipeline, read
    from copisteria.paths import EVIDENCE
    from copisteria.vision.page.scan import from_pdf

    detector = job.opts.get("detector", "28m")
    device = job.opts.get("device", "auto")
    if device == "auto":
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    os.environ["COPISTERIA_DETECTOR"] = detector  # read per call by copisteria.paths.detector()
    key = (device,)
    if key not in _cache:
        _cache.clear()
        _cache[key] = read.load_model(EVIDENCE, device)
    model = _cache[key]

    # detections are cached beside each page png, so pages live in the output folder, never beside the source
    cache = Path(job.out_dir) / ".cache" / "score" / hashlib.sha1(job.input.encode()).hexdigest()[:10]
    cache.mkdir(parents=True, exist_ok=True)
    src = Path(job.input)
    if src.suffix.lower() == ".pdf":
        pages = parse_pages(job.opts.get("pages", "all"), _page_count(job.input))
        pngs = [(f"{src.stem}_p{n:02d}", from_pdf(job.input, n, cache).path) for n in pages]
    else:
        png = cache / src.name
        shutil.copyfile(src, png)
        pngs = [(src.stem, png)]

    outputs = []
    for i, (name, png) in enumerate(pngs):
        emit(i / len(pngs), f"page {i + 1}/{len(pngs)}")
        xml = pipeline.transcribe(png, model, device=device)
        path = output_path(job, "score", "musicxml", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Path(path).write_text(xml)
        outputs.append(Output("score", path))
    return outputs, {"pages": len(outputs)}
