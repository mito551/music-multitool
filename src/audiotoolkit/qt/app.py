"""Qt entry point: `python -m audiotoolkit --ui qt`."""
from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from audiotoolkit.core.settings import load_settings

from .window import MainWindow


def main(argv: list[str]) -> int:
    smoke = "--smoke" in argv
    app = QApplication([a for a in argv if a != "--smoke"])
    app.setApplicationName("Audio Toolkit")
    app.setDesktopFileName("local.audiotoolkit.AudioToolkit")
    win = MainWindow(load_settings())
    win.show()
    if smoke:
        QTimer.singleShot(500, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
