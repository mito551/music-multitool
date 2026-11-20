"""Tool tabs. TABS maps a job kind to its form; RESULT_TEXT maps a kind to a one-line summary of an item's result."""
from __future__ import annotations

from typing import Callable

from .base import ToolTab
from .convert_tab import ConvertTab

TABS: dict[str, type[ToolTab]] = {}
RESULT_TEXT: dict[str, Callable[[dict], str]] = {}

for _tab in (ConvertTab,):
    TABS[_tab.kind] = _tab
