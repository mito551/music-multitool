"""The queue list: one row per item with status icon, progress bar and per-item buttons (Qt twin of ui/queue_view.py)."""
from __future__ import annotations

import os
from typing import Callable

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QProgressBar, QToolButton, QVBoxLayout,
                               QWidget)

from audiotoolkit.core.queue import Item, Status
from audiotoolkit.core.tools import RESULT_TEXT

from .rows import icon
from .tabs import TABS

ICONS = {
    Status.PENDING: "document-open-recent-symbolic", Status.RUNNING: "process-working-symbolic",
    Status.DONE: "object-select-symbolic", Status.FAILED: "dialog-error-symbolic", Status.SKIPPED: "go-next-symbolic",
    Status.CANCELLED: "process-stop-symbolic",
}
MARK = {Status.PENDING: "•", Status.RUNNING: "▶", Status.DONE: "✓", Status.FAILED: "✗", Status.SKIPPED: "→",
        Status.CANCELLED: "■"}  # shown when the theme has no icons (Windows)


def describe(item: Item) -> str:
    text = item.message
    if item.status in (Status.DONE, Status.SKIPPED) and item.kind in RESULT_TEXT:
        text = RESULT_TEXT[item.kind](item.result)
    label = f"{item.kind} · {item.status.value}"
    return f"{label} · {text}" if text else label


class _Row(QWidget):
    def __init__(self, item: Item, on_override: Callable[[Item], None]):
        super().__init__()
        self.item = item
        self.mark = QLabel(fixedWidth=20)
        self.title = QLabel(objectName="rowTitle")
        self.sub = QLabel(enabled=False)
        self.bar = QProgressBar(fixedWidth=140, textVisible=False)
        self.override = QToolButton(toolTip="Override options", text="✎")
        self.override.setIcon(icon("document-edit-symbolic"))
        self.folder = QToolButton(toolTip="Open output folder", text="📂")
        self.folder.setIcon(icon("folder-open-symbolic"))
        self.override.clicked.connect(lambda: on_override(self.item))
        self.folder.clicked.connect(self._open_folder)
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(self.title)
        text.addWidget(self.sub)
        lay = QHBoxLayout(self)
        lay.addWidget(self.mark)
        lay.addLayout(text, 1)
        for w in (self.bar, self.override, self.folder):
            lay.addWidget(w)

    def _open_folder(self) -> None:
        if self.item.outputs:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self.item.outputs[0].path)))

    def refresh(self, item: Item) -> None:
        self.item = item
        self.title.setText(item.song)
        self.sub.setText(describe(item))
        self.mark.setText(MARK[item.status])
        if item.status is Status.RUNNING and item.fraction is None:
            self.bar.setRange(0, 0)  # busy indicator
        else:
            self.bar.setRange(0, 1000)
            self.bar.setValue(1000 if item.status in (Status.DONE, Status.SKIPPED) else int((item.fraction or 0) * 1000))
        self.override.setEnabled(item.status is Status.PENDING and item.kind in TABS and TABS[item.kind].has_opts)
        self.folder.setEnabled(bool(item.outputs))


class QueueView(QListWidget):
    def __init__(self, on_override: Callable[[Item], None]):
        super().__init__()
        self.setMinimumHeight(80)
        self.setSelectionMode(QListWidget.NoSelection)
        self._on_override = on_override
        self._rows: dict[str, tuple[QListWidgetItem, _Row]] = {}

    def update_item(self, item: Item) -> None:
        if item.id not in self._rows:
            li, row = QListWidgetItem(), _Row(item, self._on_override)
            self.addItem(li)
            self.setItemWidget(li, row)
            self._rows[item.id] = (li, row)
        li, row = self._rows[item.id]
        row.refresh(item)
        li.setSizeHint(row.sizeHint())

    def remove_item(self, item_id: str) -> None:
        pair = self._rows.pop(item_id, None)
        if pair is not None:
            self.takeItem(self.row(pair[0]))
