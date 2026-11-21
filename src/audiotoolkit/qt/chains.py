"""Chains: pick, edit and save presets; Add files queues one `chain` item per file (Qt twin of ui/tabs/chains_tab.py)."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QPushButton,
                               QToolButton, QVBoxLayout, QWidget)

from audiotoolkit.core.presets import Preset, Step, delete_preset, load_presets, save_preset, validate_preset
from audiotoolkit.core.tools import ROLES

from .rows import ToolTab, icon
from .tabs import TABS


def _chainable() -> list[str]:
    return [k for k, t in TABS.items() if t.chainable]


def _dropdown(values: list[str], current: str, on_change: Callable[[str], None]) -> QComboBox:
    values = values if current in values else values + [current]
    box = QComboBox()
    box.addItems(values)
    box.setCurrentIndex(values.index(current))
    box.currentTextChanged.connect(on_change)
    return box


class ChainsTab(ToolTab):
    kind, title, icon_name = "chain", "Chains", "insert-link-symbolic"

    def build(self) -> None:
        self.presets: dict[str, Preset] = {}
        self.steps: list[Step] = []
        self.name = ""
        self.dirty = False
        self._want = ""
        self._builtin = self._user = ""
        self._on_changed: Callable[[dict[str, Preset]], None] = lambda presets: None
        self._loading = False
        outer = self.layout()
        outer.removeItem(self.form)  # this tab has its own layout instead of the form
        self.picker = QComboBox()
        self.picker.currentTextChanged.connect(self._on_pick)
        top = QHBoxLayout()
        for label, handler in (("Add step", self._add_step), ("Save as…", self._save_dialog), ("Delete", self._delete)):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, h=handler: h())
            top.addWidget(b)
        top.addWidget(QLabel("Preset"))
        top.addWidget(self.picker, 1)
        self.steps_box = QVBoxLayout()
        self.status = QLabel(wordWrap=True)
        pill = QFrame(objectName="statusPill")
        pl = QHBoxLayout(pill)
        pl.setContentsMargins(10, 2, 10, 2)
        heading = QLabel("Status:")
        heading.setStyleSheet("font-weight: bold")
        pl.addWidget(heading)
        pl.addWidget(self.status)
        pill_row = QHBoxLayout()
        pill_row.addWidget(pill)
        pill_row.addStretch(1)
        outer.insertLayout(0, top)
        outer.insertLayout(1, self.steps_box)
        outer.insertLayout(2, pill_row)

    # -- wiring -------------------------------------------------------------------------------------------------

    def bind(self, builtin_dir: str, user_dir: str, on_changed: Callable[[dict[str, Preset]], None]) -> None:
        self._builtin, self._user, self._on_changed = builtin_dir, user_dir, on_changed
        self._reload(self._want)

    def get_opts(self) -> dict:
        return {"preset": self.name}

    def set_opts(self, opts: dict) -> None:
        self._want = opts.get("preset", "")
        if self.presets:
            self._select(self._want)

    def _reload(self, select: str) -> None:
        self.presets = load_presets(self._builtin, self._user)
        self._on_changed(self.presets)
        self._loading = True
        self.picker.clear()
        self.picker.addItems(list(self.presets))
        self._loading = False
        self._select(select if select in self.presets else next(iter(self.presets), ""))

    def _select(self, name: str) -> None:
        if name in self.presets:
            self._loading = True
            self.picker.setCurrentText(name)
            self._loading = False
        self.name = name
        self.steps = list(self.presets[name].steps) if name in self.presets else []
        self.dirty = False
        self._rebuild()

    def _on_pick(self, name: str) -> None:
        if not self._loading and self.presets:
            self._select(name)

    # -- editing ------------------------------------------------------------------------------------------------

    def _touch(self) -> None:
        self.dirty = True
        QTimer.singleShot(0, self._rebuild)  # not while a signal from a row being replaced is still running

    def _rebuild(self) -> None:
        while self.steps_box.count():
            w = self.steps_box.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        for i, step in enumerate(self.steps):
            row = QFrame()
            lay = QHBoxLayout(row)
            lay.addWidget(QLabel(f"Step {i + 1}"), 1)
            lay.addWidget(_dropdown(_chainable(), step.kind, lambda k, i=i: self._set_kind(i, k)))
            lay.addWidget(_dropdown(ROLES, step.input, lambda r, i=i: self._set_input(i, r)))
            buttons = [("⚙", "emblem-system-symbolic", "Options", lambda i=i: self._edit_opts(i)),
                       ("↑", "go-up-symbolic", "Move up", lambda i=i: self._move(i, -1)),
                       ("↓", "go-down-symbolic", "Move down", lambda i=i: self._move(i, 1)),
                       ("🗑", "user-trash-symbolic", "Remove", lambda i=i: self._remove(i))]
            if not TABS[step.kind].has_opts:
                buttons.pop(0)
            for text, icon_name, tip, fn in buttons:
                b = QToolButton(text=text, toolTip=tip)
                b.setIcon(icon(icon_name))
                b.clicked.connect(lambda _=False, fn=fn: fn())
                lay.addWidget(b)
            self.steps_box.addWidget(row)
        self.status.setText(self._blocking_reason() or "Ready")

    def _set_kind(self, i: int, kind: str) -> None:
        if self.steps[i].kind != kind:
            self.steps[i] = Step(kind, {}, self.steps[i].input)
            self._touch()

    def _set_input(self, i: int, role: str) -> None:
        if self.steps[i].input != role:
            self.steps[i] = Step(self.steps[i].kind, self.steps[i].opts, role)
            self._touch()

    def _move(self, i: int, d: int) -> None:
        j = i + d
        if 0 <= j < len(self.steps):
            self.steps[i], self.steps[j] = self.steps[j], self.steps[i]
            self._touch()

    def _remove(self, i: int) -> None:
        del self.steps[i]
        self._touch()

    def _add_step(self) -> None:
        self.steps.append(Step("convert", {}, "source" if not self.steps else "audio"))
        self._touch()

    def _edit_opts(self, i: int) -> None:
        step = self.steps[i]
        form = TABS[step.kind](embedded=True)
        form.set_opts(step.opts)
        dialog = QDialog(self, windowTitle=f"Step {i + 1}: {step.kind}")
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        lay = QVBoxLayout(dialog)
        lay.addWidget(form)
        lay.addWidget(buttons)
        if dialog.exec():
            self.steps[i] = Step(step.kind, form.get_opts(), step.input)
            self._touch()

    # -- save / delete / run ------------------------------------------------------------------------------------

    def _errors(self) -> list[str]:
        return validate_preset(Preset(self.name, tuple(self.steps)), _chainable())

    def _blocking_reason(self) -> str:
        if not self.name:
            return "Choose or save a preset first."
        if (errors := self._errors()):
            return "Fix: " + "; ".join(errors)
        if self.dirty:
            return "Unsaved changes: use Save as… before running."
        return ""

    def _save_dialog(self) -> None:
        if (errors := self._errors()):
            self.status.setText("Fix: " + "; ".join(errors))
            return
        name, ok = QInputDialog.getText(self, "Save preset", "Name for this chain", text=self.name)
        if ok and name.strip():
            save_preset(self._user, Preset(name.strip(), tuple(self.steps)))
            self._reload(name.strip())

    def _delete(self) -> None:
        if delete_preset(self._user, self.name):
            self._reload("")
        else:
            self.status.setText("Only your own presets can be deleted.")

    def accept(self, paths: list[str]) -> None:
        if (reason := self._blocking_reason()):
            self.status.setText(reason)
            return
        super().accept(paths)
