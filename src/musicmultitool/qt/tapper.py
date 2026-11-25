"""Tap-tempo block for the sidebar (Qt twin of ui/tapper_widget.py)."""
from __future__ import annotations

import time

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

from musicmultitool.core.tapper import Tapper, relation

from .rows import icon


class TapperWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.tapper = Tapper()
        self.bpm: float | None = None
        self.detected: float | None = None
        tap = QPushButton("TAP", objectName="tap", focusPolicy=Qt.NoFocus, fixedSize=QSize(76, 76))  # Qt.NoFocus: Space must tap, not click the button
        tap.clicked.connect(lambda: self.tap_now())
        self.value = QLabel("BPM: —", objectName="bpmValue")
        self.taps = QLabel("Tap or press Space", enabled=False)
        reset = QToolButton(toolTip="Reset taps", focusPolicy=Qt.NoFocus)
        reset.setIcon(icon("edit-undo-symbolic"))
        reset.setText("↺")
        copy = QToolButton(toolTip="Copy BPM", focusPolicy=Qt.NoFocus)
        copy.setIcon(icon("edit-copy-symbolic"))
        copy.setText("⧉")
        reset.clicked.connect(self.reset)
        copy.clicked.connect(self._copy)
        buttons = QHBoxLayout()
        buttons.addWidget(reset)
        buttons.addWidget(copy)
        buttons.addStretch(1)
        info = QVBoxLayout()
        for w in (self.value, self.taps):
            info.addWidget(w)
        info.addLayout(buttons)
        row = QHBoxLayout()
        row.addWidget(tap)
        row.addLayout(info, 1)
        self.hint = QLabel(wordWrap=True, enabled=False)
        self.hint.hide()
        outer = QVBoxLayout(self)
        outer.addLayout(row)
        outer.addWidget(self.hint)

    def tap_now(self, now: float | None = None) -> None:
        self.bpm = self.tapper.tap(time.monotonic() if now is None else now)
        self._refresh()

    def reset(self) -> None:
        self.tapper.reset()
        self.bpm = None
        self._refresh()

    def set_detected(self, bpm: float | None) -> None:
        self.detected = bpm
        self._refresh()

    def _refresh(self) -> None:
        self.value.setText("BPM: —" if self.bpm is None else f"BPM: {self.bpm:.1f}")
        self.taps.setText(f"{self.tapper.count} taps" if self.tapper.count else "Tap or press Space")
        hint = ""
        if self.detected:
            hint = f"Detected {self.detected:.1f} BPM"
            if self.bpm is not None:
                hint += f" → {relation(self.bpm, self.detected)}"
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))

    def _copy(self) -> None:
        if self.bpm is not None:
            QGuiApplication.clipboard().setText(f"{self.bpm:.1f}")
