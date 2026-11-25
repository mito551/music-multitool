"""Main window (Qt twin of ui/window.py): sidebar | tool form over batch queue, both dividers draggable."""
from __future__ import annotations

import os

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QPushButton, QScrollArea,
                               QSplitter, QStackedWidget, QTextEdit, QVBoxLayout, QWidget)

from musicmultitool.core.backend import PRESETS_DIR, Backend, worker_ready
from musicmultitool.core.components import installed
from musicmultitool.core.paths import user_presets_dir
from musicmultitool.core.presets import load_presets
from musicmultitool.core.queue import Item, Status
from musicmultitool.core.settings import Settings, save_settings

from .chains import ChainsTab
from .config import ConfigView
from .post import Poster
from .queue_view import QueueView
from .rows import ToolTab, icon
from .sidebar import Sidebar
from .tabs import TABS

USER_PRESETS = user_presets_dir()
STYLE = """
QPushButton#tap { border-radius: 38px; min-width: 76px; max-width: 76px; min-height: 76px; max-height: 76px;
                  font-weight: 800; font-size: 18px; background: palette(highlight); color: palette(highlighted-text); }
QLabel#bpmValue, QLabel#keyValue { font-size: 15px; font-weight: bold; }
QLabel#rowTitle { font-weight: bold; }
QFrame#statusPill { background: palette(alternate-base); border: 1px solid palette(mid); border-radius: 12px; }
QListWidget#nav { border: none; background: transparent; }
QListWidget#nav::item { padding: 10px 8px; }
"""
TEXT_INPUTS = (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.setWindowTitle("Music Multitool")
        self.resize(1040, 900)
        self.setAcceptDrops(True)
        self.setStyleSheet(STYLE)
        self.settings = settings
        self.poster = Poster()
        self.presets = load_presets(str(PRESETS_DIR), USER_PRESETS)
        self.backend = Backend(settings, self.presets, self._on_change, self.poster.post)
        self.queue_view = QueueView(self._override_dialog)

        self.stack = QStackedWidget()
        self.tabs: dict[str, ToolTab] = {}
        self.sidebar = Sidebar(self._show_tab, lambda: self._pick(False), lambda: self._pick(True), self._detect)
        for kind, cls in TABS.items():
            self._add_tab(kind, cls())
        self.chains = ChainsTab()
        self._add_tab("chain", self.chains)
        self.chains.bind(str(PRESETS_DIR), USER_PRESETS, self._presets_changed)
        self.config = ConfigView(settings, self._config_changed, self.backend.close)
        self.stack.addWidget(self.config)
        self._pages = {**self.tabs, "settings": self.config}
        self.sidebar.add_page("settings", "Settings", "emblem-system-symbolic")

        forms = QScrollArea(widgetResizable=True)
        forms.setWidget(self.stack)
        forms.setFrameShape(QScrollArea.NoFrame)
        self.vsplit = QSplitter(Qt.Vertical)
        self.vsplit.addWidget(forms)
        self.vsplit.addWidget(self._queue_panel())
        self.vsplit.setStretchFactor(0, 1)
        self.vsplit.setStretchFactor(1, 0)
        self.vsplit.setCollapsible(0, False)
        self.vsplit.setSizes([900 - settings.queue_height, settings.queue_height])
        self.hsplit = QSplitter(Qt.Horizontal)
        self.hsplit.addWidget(self.sidebar)
        self.hsplit.addWidget(self.vsplit)
        self.hsplit.setStretchFactor(1, 1)
        self.hsplit.setCollapsible(0, False)
        self.hsplit.setSizes([settings.sidebar_width, 1040 - settings.sidebar_width])
        self.setCentralWidget(self.hsplit)
        self.sidebar.select(next(iter(self.tabs)))
        if not installed() and not worker_ready(settings):  # first run: nothing is installed unasked, so offer the choice
            QTimer.singleShot(0, self._offer_install)
        QApplication.instance().installEventFilter(self)

    def _offer_install(self) -> None:
        d = QDialog(self)
        d.setWindowTitle("Install tools and models")
        d.resize(560, 460)
        lay = QVBoxLayout(d)
        lay.addWidget(ConfigView(self.settings, self._config_changed, self.backend.close, compact=True))
        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.rejected.connect(d.reject)
        lay.addWidget(box)
        d.open()

    def _add_tab(self, kind: str, tab: ToolTab) -> None:
        tab.set_opts(self.settings.tab_opts.get(kind, {}))
        tab.on_add = lambda paths, k=kind: self.add_paths(paths, k)
        self.tabs[kind] = tab
        if not tab.hidden:  # hidden kinds get a tab object (chains, opts) but no sidebar entry
            self.stack.addWidget(tab)
            self.sidebar.add_page(kind, tab.title, tab.icon_name)

    def _show_tab(self, kind: str) -> None:
        widget = self._pages.get(kind)
        if widget is not None:
            self.stack.setCurrentWidget(widget)

    def _current_tab(self) -> ToolTab | None:
        widget = self.stack.currentWidget()
        return widget if isinstance(widget, ToolTab) else None

    def _queue_panel(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        bar = QHBoxLayout()
        for label, handler in (("Run", self._run), ("Cancel", lambda: self.backend.cancel()),
                               ("Retry failed", lambda: self.backend.retry_failed()), ("Clear done", self._clear_done)):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, h=handler: h())
            bar.addWidget(b)
        bar.addStretch(1)
        skip = QCheckBox("Skip existing", checked=self.settings.skip_existing)
        skip.toggled.connect(self._skip_toggled)
        self.out_button = QPushButton(self._out_label())
        self.out_button.clicked.connect(self._choose_out)
        bar.addWidget(skip)
        bar.addWidget(self.out_button)
        lay.addLayout(bar)
        lay.addWidget(self.queue_view)
        return panel

    def _out_label(self) -> str:
        return "Output: " + os.path.basename(self.settings.out_root.rstrip("/\\"))

    # -- input --------------------------------------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        """Space taps the tempo anywhere except while typing."""
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Space and not event.isAutoRepeat() \
                and self.isActiveWindow() and not isinstance(QApplication.focusWidget(), TEXT_INPUTS):
            self.sidebar.tapper.tap_now()
            return True
        return False

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if (tab := self._current_tab()) and paths:
            tab.accept(paths)
            event.acceptProposedAction()

    def _pick(self, folder: bool) -> None:
        tab = self._current_tab()
        if tab is None:
            return
        if folder:
            found = [QFileDialog.getExistingDirectory(self, "Add folder")]
        else:
            found, _ = QFileDialog.getOpenFileNames(self, "Add files")
        if paths := [p for p in found if p]:
            tab.accept(paths)

    def _detect(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Detect BPM and key")
        if path and self.backend.add([path], "analyze", {}):
            self._run()

    # -- actions ------------------------------------------------------------------------------------------------

    def add_paths(self, paths: list[str], kind: str) -> None:
        self.backend.add(paths, kind, self.tabs[kind].get_opts())

    def _presets_changed(self, presets: dict) -> None:
        self.presets = presets
        self.backend.set_presets(presets)

    def _on_change(self, item: Item) -> None:
        self.queue_view.update_item(item)
        if item.kind == "analyze" and item.status is Status.DONE:  # the sidebar shows the latest analysis
            self.sidebar.tapper.set_detected(item.result.get("bpm") or None)
            self.sidebar.set_key(item.result.get("key"), item.result.get("key_confidence", 0.0))

    def _run(self) -> None:
        for i in self.backend.queue.items:  # pending items follow the tab's current settings unless overridden
            if i.status is Status.PENDING and not i.overrides and i.kind in self.tabs:
                i.opts = self.tabs[i.kind].get_opts()
        self._save()
        self.backend.start()

    def _clear_done(self) -> None:
        for item in list(self.backend.queue.items):
            if item.status in (Status.DONE, Status.SKIPPED):
                self.backend.queue.remove(item.id)
                self.queue_view.remove_item(item.id)

    def _choose_out(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Output folder", self.settings.out_root)
        if folder:
            self.settings.out_root = folder
            self._config_changed()

    def _skip_toggled(self, on: bool) -> None:
        self.settings.skip_existing = on
        self._save()

    def _config_changed(self) -> None:
        self.out_button.setText(self._out_label())
        self._save()

    def _override_dialog(self, item: Item) -> None:
        tab = TABS[item.kind](embedded=True)
        tab.set_opts(self.backend.queue.effective_opts(item))
        dialog = QDialog(self, windowTitle=f"Options: {item.song}")
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        lay = QVBoxLayout(dialog)
        lay.addWidget(tab)
        lay.addWidget(buttons)
        if dialog.exec():
            self.backend.queue.set_override(item.id, tab.get_opts())

    def _save(self) -> None:
        self.settings.tab_opts = {k: t.get_opts() for k, t in self.tabs.items()}
        self.settings.sidebar_width = self.hsplit.sizes()[0]
        self.settings.queue_height = max(80, self.vsplit.sizes()[1])
        save_settings(self.settings)
        self.backend.update_settings(self.settings)

    def closeEvent(self, event) -> None:
        self._save()
        self.backend.close()
        super().closeEvent(event)
