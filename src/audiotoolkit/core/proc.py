"""subprocess options shared by everything the app starts."""
from __future__ import annotations

import os

# A windowed Windows app starting console programs would flash a console window for each; Linux needs nothing.
QUIET: dict = {"creationflags": 0x08000000} if os.name == "nt" else {}  # CREATE_NO_WINDOW
TEXT: dict = {"text": True, "encoding": "utf-8", "errors": "replace"}  # not the locale's code page
