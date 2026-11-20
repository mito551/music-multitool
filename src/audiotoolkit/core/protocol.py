"""Job/event messages exchanged between the UI and the worker: one JSON object per line."""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Output:
    role: str
    path: str


@dataclass(frozen=True)
class Job:
    id: str
    kind: str
    input: str
    opts: dict
    out_dir: str


@dataclass(frozen=True)
class Progress:
    id: str
    fraction: float | None
    note: str = ""


@dataclass(frozen=True)
class Done:
    id: str
    outputs: tuple[Output, ...]
    result: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Failed:
    id: str
    message: str


Event = Progress | Done | Failed


def encode_job(job: Job) -> str:
    return json.dumps({"id": job.id, "kind": job.kind, "input": job.input, "opts": job.opts, "out_dir": job.out_dir})


def decode_job(line: str) -> Job:
    d = json.loads(line)
    return Job(d["id"], d["kind"], d["input"], d["opts"], d["out_dir"])


def encode_event(ev: Event) -> str:
    if isinstance(ev, Progress):
        d = {"event": "progress", "id": ev.id, "fraction": ev.fraction, "note": ev.note}
    elif isinstance(ev, Done):
        d = {"event": "done", "id": ev.id, "outputs": [[o.role, o.path] for o in ev.outputs], "result": ev.result}
    else:
        d = {"event": "failed", "id": ev.id, "message": ev.message}
    return json.dumps(d)


def decode_event(line: str) -> Event:
    d = json.loads(line)
    kind = d["event"]
    if kind == "progress":
        return Progress(d["id"], d["fraction"], d.get("note", ""))
    if kind == "done":
        return Done(d["id"], tuple(Output(r, p) for r, p in d["outputs"]), d.get("result", {}))
    return Failed(d["id"], d["message"])
