"""Entry point of the one-file Windows build: the Qt interface only (no launcher, no GTK)."""
import sys

from audiotoolkit.qt.app import main

sys.exit(main(sys.argv))
