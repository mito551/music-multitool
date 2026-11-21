"""Tool tabs. TABS maps a job kind to its form; RESULT_TEXT maps a kind to a one-line summary of an item's result."""
from __future__ import annotations

from audiotoolkit.core.tools import RESULT_TEXT

from .analyze_tab import AnalyzeTab
from .base import ToolTab
from .convert_tab import ConvertTab
from .lyrics_tab import LyricsTab
from .midi_tab import MidiTab
from .score_tab import ScoreTab
from .separate_tab import SeparateTab

TABS: dict[str, type[ToolTab]] = {}

for _tab in (ConvertTab, SeparateTab, MidiTab, AnalyzeTab, LyricsTab, ScoreTab):
    TABS[_tab.kind] = _tab
