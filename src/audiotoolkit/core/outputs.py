"""Where a job's files go, and the manifests that record finished jobs (skip-existing and chain resume)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .protocol import Job, Output

_SUBDIRS = {"midi": "midi", "lyrics": "lyrics", "audio": "audio"}


def song_dir(out_root: str, song: str) -> str:
    return os.path.join(out_root, song)


def output_path(job: Job, role: str, ext: str, name: str | None = None) -> str:
    if role == "analysis":
        return os.path.join(job.out_dir, "analysis.json")
    sub = "stems" if role.startswith("stem:") else _SUBDIRS[role]
    return os.path.join(job.out_dir, sub, f"{name or Path(job.input).stem}.{ext}")


def manifest_path(job: Job) -> str:
    key = job.input + json.dumps(job.opts, sort_keys=True)
    digest = hashlib.sha1(key.encode()).hexdigest()[:10]
    return os.path.join(job.out_dir, ".manifests", f"{job.kind}-{digest}.json")


def write_manifest(job: Job, outputs: list[Output]) -> None:
    path = manifest_path(job)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump([[o.role, o.path] for o in outputs], f)


def load_manifest(job: Job) -> list[Output] | None:
    try:
        with open(manifest_path(job)) as f:
            outs = [Output(r, p) for r, p in json.load(f)]
    except (OSError, ValueError):
        return None
    return outs if all(os.path.exists(o.path) for o in outs) else None
