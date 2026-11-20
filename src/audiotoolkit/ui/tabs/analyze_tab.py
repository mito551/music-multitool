from __future__ import annotations

from .base import ToolTab


def result_text(result: dict) -> str:
    if result.get("bpm") is None:
        return "no tempo/key found"
    return f"BPM {result['bpm']:.1f} · {result['key']} ({result['key_confidence']:.0%})"


class AnalyzeTab(ToolTab):
    kind = "analyze"
    title = "Analyze"
    icon = "view-continuous-symbolic"
    has_opts = False

    def build(self, group) -> None:
        group.set_description("Detects tempo (BPM) and musical key. Key is a best guess; BPM may read half or double.")

    def get_opts(self) -> dict:
        return {}

    def set_opts(self, opts: dict) -> None:
        pass
