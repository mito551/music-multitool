"""Form-row helpers and the base class of the tool tabs (Qt twin of ui/tabs/base.py)."""
from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
                               QWidget)


def icon(name: str) -> QIcon:
    """Theme icon by freedesktop name; GTK's "-symbolic" variants fall back to the plain one. Empty where no theme exists."""
    return QIcon.fromTheme(name) if QIcon.hasThemeIcon(name) else QIcon.fromTheme(name.removesuffix("-symbolic"))


def combo(labels: list[str]) -> QComboBox:
    c = QComboBox()
    c.addItems(labels)
    return c


def set_combo(c: QComboBox, value) -> None:
    i = c.findText(str(value))
    if i >= 0:
        c.setCurrentIndex(i)


def spin(lo: float, hi: float, step: float, value: float, digits: int = 0) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setDecimals(digits)
    s.setValue(value)
    return s


class ToolTab(QWidget):
    """One tool's settings form. Subclasses set `kind`/`title` and implement build/get_opts/set_opts."""

    kind: str = ""
    title: str = ""
    icon_name: str = "image-missing"
    hidden: bool = False  # no sidebar entry; the kind still exists (chain steps, queue items)
    chainable: bool = True  # False: input isn't audio, so the tool can't be a preset step
    has_opts: bool = True  # False: nothing to configure, so no override/step-options dialog

    def __init__(self, embedded: bool = False) -> None:
        """embedded=True: the form alone, for dialogs."""
        super().__init__()
        self.embedded = embedded
        self.on_add: Callable[[list[str]], None] = lambda paths: None
        outer = QVBoxLayout(self)
        if embedded:
            outer.setContentsMargins(0, 0, 0, 0)
        self.note = QLabel(wordWrap=True)
        self.note.hide()
        self.form = QFormLayout()
        outer.addWidget(self.note)
        outer.addLayout(self.form)
        outer.addStretch(1)
        self.build()

    def describe(self, text: str) -> None:
        self.note.setText(text)
        self.note.show()

    def row(self, label: str, widget: QWidget) -> QWidget:
        self.form.addRow(label, widget)
        return widget

    def accept(self, paths: list[str]) -> None:
        """Files chosen in the sidebar or dropped on the window: queue them for this tool."""
        self.on_add(paths)

    def build(self) -> None:
        raise NotImplementedError

    def get_opts(self) -> dict:
        raise NotImplementedError

    def set_opts(self, opts: dict) -> None:
        raise NotImplementedError
