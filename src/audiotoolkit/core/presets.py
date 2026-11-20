"""Chain presets: ordered steps; a step's input is the source file or a role pattern over earlier outputs."""
from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import dataclass, field
from typing import Iterable

from .protocol import Output


@dataclass(frozen=True)
class Step:
    kind: str
    opts: dict = field(default_factory=dict)
    input: str = "source"


@dataclass(frozen=True)
class Preset:
    name: str
    steps: tuple[Step, ...]


def select_inputs(step: Step, source: str, prev: list[Output]) -> list[str]:
    """prev = all outputs produced by the item's earlier steps, in order."""
    if step.input == "source":
        return [source]
    return [o.path for o in prev if fnmatch.fnmatchcase(o.role, step.input)]


def validate_preset(p: Preset, known_kinds: Iterable[str]) -> list[str]:
    if not p.steps:
        return ["no steps"]
    kinds, errors = set(known_kinds), []
    for s in p.steps:
        if s.kind not in kinds:
            errors.append(f"unknown kind: {s.kind}")
    if p.steps[0].input != "source":
        errors.append("first step input must be 'source'")
    return errors


def _parse(path: str) -> Preset | None:
    try:
        with open(path) as f:
            d = json.load(f)
        return Preset(d["name"], tuple(Step(s["kind"], s.get("opts", {}), s.get("input", "source")) for s in d["steps"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load_presets(builtin_dir: str, user_dir: str) -> dict[str, Preset]:
    presets: dict[str, Preset] = {}
    for d in (builtin_dir, user_dir):
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.endswith(".json") and (p := _parse(os.path.join(d, name))):
                presets[p.name] = p
    return presets


def save_preset(user_dir: str, p: Preset) -> None:
    os.makedirs(user_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", p.name.lower()).strip("-") or "preset"
    data = {"name": p.name, "steps": [{"kind": s.kind, "opts": s.opts, "input": s.input} for s in p.steps]}
    with open(os.path.join(user_dir, f"{slug}.json"), "w") as f:
        json.dump(data, f, indent=2)
