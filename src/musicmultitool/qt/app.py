"""Qt entry point: `python -m musicmultitool --ui qt`."""
from __future__ import annotations

import sys

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from musicmultitool.core.settings import load_settings

from .window import MainWindow


def main(argv: list[str]) -> int:
    smoke = "--smoke" in argv
    app = QApplication([a for a in argv if a != "--smoke"])
    app.setApplicationName("Music Multitool")
    app.setDesktopFileName("io.github.mito551.MusicMultitool")
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[1] / "music-multitool.png")))
    win = MainWindow(load_settings())
    win.show()
    if smoke:
        QTimer.singleShot(500, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
