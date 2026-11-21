"""Toolkit-neutral facts about the tools, shared by every frontend."""
from __future__ import annotations

from typing import Callable


def _analyze(r: dict) -> str:
    if r.get("bpm") is None:
        return "no tempo/key found"
    return f"BPM {r['bpm']:.1f} · {r['key']} ({r['key_confidence']:.0%})"


# one-line summary of a finished item's result, by kind
RESULT_TEXT: dict[str, Callable[[dict], str]] = {
    "analyze": _analyze,
    "score": lambda r: f"{r['pages']} page{'s' if r['pages'] != 1 else ''} read",
}

ROLES = ["source", "audio", "stem:*", "stem:vocals", "stem:drums", "stem:bass", "stem:other", "midi", "lyrics", "analysis"]
DEVICES = ["auto", "cuda", "cpu"]
