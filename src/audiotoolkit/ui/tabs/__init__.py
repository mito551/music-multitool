"""Tool tabs. TABS maps a job kind to its form; RESULT_TEXT maps a kind to a one-line summary of an item's result."""
from __future__ import annotations

from typing import Callable

from .analyze_tab import AnalyzeTab, result_text as _analyze_text
from .base import ToolTab
from .convert_tab import ConvertTab
from .lyrics_tab import LyricsTab
from .midi_tab import MidiTab
from .score_tab import ScoreTab
from .separate_tab import SeparateTab

TABS: dict[str, type[ToolTab]] = {}
RESULT_TEXT: dict[str, Callable[[dict], str]] = {}

for _tab in (ConvertTab, SeparateTab, MidiTab, AnalyzeTab, LyricsTab, ScoreTab):
    TABS[_tab.kind] = _tab
RESULT_TEXT["analyze"] = _analyze_text
RESULT_TEXT["score"] = lambda r: f"{r['pages']} page{'s' if r['pages'] != 1 else ''} read"
