"""Worker process: reads job lines on stdin, writes event lines on stdout."""
from __future__ import annotations

import gc
import sys

from musicmultitool.core.outputs import write_manifest
from musicmultitool.core.protocol import Done, Failed, Progress, decode_job, encode_event
from musicmultitool.worker.registry import load_kind


def main() -> None:
    proto = sys.stdout
    sys.stdout = sys.stderr  # libraries may print; stdout is reserved for protocol lines

    def send(ev) -> None:
        proto.write(encode_event(ev) + "\n")
        proto.flush()

    current = None  # (kind, module) whose models may be loaded
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            job = decode_job(line)
        except Exception as e:
            send(Failed("", f"bad job line: {e}"))
            continue
        try:
            mod = load_kind(job.kind)
            if current is not None and current[0] != job.kind:
                release = getattr(current[1], "release", None)
                if release:
                    release()
                gc.collect()
                if "torch" in sys.modules:
                    sys.modules["torch"].cuda.empty_cache()
            current = (job.kind, mod)
            outputs, result = mod.run(job, lambda frac, note="", _id=job.id: send(Progress(_id, frac, note)))
            write_manifest(job, outputs)
            send(Done(job.id, tuple(outputs), result))
        except Exception as e:
            send(Failed(job.id, str(e) or type(e).__name__))


main()
