"""Tool tabs. TABS maps a job kind to its form; RESULT_TEXT maps a kind to a one-line summary of an item's result."""
from __future__ import annotations

from typing import Callable

from .base import ToolTab
from .convert_tab import ConvertTab
from .lyrics_tab import LyricsTab
from .midi_tab import MidiTab
from .separate_tab import SeparateTab

TABS: dict[str, type[ToolTab]] = {}
RESULT_TEXT: dict[str, Callable[[dict], str]] = {}

for _tab in (ConvertTab, SeparateTab, MidiTab, LyricsTab):
    TABS[_tab.kind] = _tab
