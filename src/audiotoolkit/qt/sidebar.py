"""Left pane: tap tempo and key on top, tool navigation below, Add buttons at the bottom."""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from .rows import icon
from .tapper import TapperWidget


class Sidebar(QWidget):
    def __init__(self, on_select: Callable[[str], None], on_files: Callable[[], None], on_folder: Callable[[], None],
                 on_detect: Callable[[], None]):
        super().__init__()
        self.setMinimumWidth(200)
        self._on_select = on_select
        self.tapper = TapperWidget()
        self.key = QLabel("Key: —", objectName="keyValue")
        detect = QPushButton("Detect BPM && key…", toolTip="Analyze one audio file (a few seconds)")
        detect.clicked.connect(lambda: on_detect())
        self.list = QListWidget(objectName="nav")
        self.list.currentItemChanged.connect(self._selected)
        add = QHBoxLayout()
        for label, handler in (("Add files…", on_files), ("Add folder…", on_folder)):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, h=handler: h())
            add.addWidget(b)
        lay = QVBoxLayout(self)
        for w in (self.tapper, self.key, detect, self.list):
            lay.addWidget(w)
        lay.addLayout(add)

    def add_page(self, kind: str, title: str, icon_name: str) -> None:
        item = QListWidgetItem(icon(icon_name), title)
        item.setData(256, kind)  # Qt.UserRole
        self.list.addItem(item)

    def set_key(self, key: str | None, confidence: float = 0.0) -> None:
        self.key.setText(f"Key: {key} ({confidence:.0%})" if key else "Key: —")

    def select(self, kind: str) -> None:
        for i in range(self.list.count()):
            if self.list.item(i).data(256) == kind:
                self.list.setCurrentRow(i)

    def _selected(self, item, _previous) -> None:
        if item is not None:
            self._on_select(item.data(256))
