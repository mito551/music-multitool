"""Entry point of the frozen builds (Windows exe, Linux AppImage): the Qt interface only (no launcher, no GTK)."""
import sys

from musicmultitool.qt.app import main

sys.exit(main(sys.argv))
