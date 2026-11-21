"""Settings page: General, Repos, Models, Paths (Qt twin of ui/config_dialog.py)."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QMessageBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QTabWidget, QVBoxLayout, QWidget)

from audiotoolkit.core.backend import repo_path, worker_cmd
from audiotoolkit.core.paths import data_dir
from audiotoolkit.core.provision import data_size, remove_data
from audiotoolkit.core.settings import Settings
from audiotoolkit.core.setup_env import REPOS, local_checkout, plan, run_plan
from audiotoolkit.core.tools import DEVICES

# copisteria weights relative to its checkout, and the Hugging Face repo each one comes from
WEIGHTS = (("Evidence model", "models/evidence-2m.pt", "copisteria"),
           ("Detector 28m", "models/small/v7_obj-recall-30m_best.pt", "copista-28m"),
           ("Detector 2m", "models/small/v7_obj-recall_best.pt", "copista-2m"))
FRONTENDS = ["auto", "gtk", "qt"]


class ConfigView(QWidget):
    _progress = Signal(str)  # a background step reports from its thread
    _finished = Signal(str, str)  # which job, error text ("" = ok)

    def __init__(self, settings: Settings, on_changed: Callable[[], None], stop_worker: Callable[[], None]):
        super().__init__()
        self.s, self._changed, self._stop_worker = settings, on_changed, stop_worker
        self.note = QLabel(wordWrap=True, enabled=False)
        tabs = QTabWidget()
        for title, build in (("General", self._general), ("Repos", self._repos), ("Models", self._models),
                             ("Paths", self._paths)):
            tabs.addTab(build(), title)
        lay = QVBoxLayout(self)
        lay.addWidget(tabs, 1)
        lay.addWidget(self.note)
        self._progress.connect(lambda text: self._env_status(text))
        self._finished.connect(self._job_done)

    def _page(self, description: str = "") -> tuple[QWidget, QFormLayout]:
        page = QWidget()
        lay = QVBoxLayout(page)
        if description:
            lay.addWidget(QLabel(description, wordWrap=True))
        form = QFormLayout()
        lay.addLayout(form)
        lay.addStretch(1)
        page.body = lay  # type: ignore[attr-defined]
        return page, form

    def _entry(self, form: QFormLayout, label: str, value: str, attr: str, key: str | None = None) -> QLineEdit:
        edit = QLineEdit(value)

        def changed(text: str) -> None:
            if key is None:
                setattr(self.s, attr, text)
            else:
                getattr(self.s, attr)[key] = text
            self._changed()

        edit.textChanged.connect(changed)
        form.addRow(label, edit)
        return edit

    def _combo(self, form: QFormLayout, label: str, values: list[str], attr: str) -> None:
        box = QComboBox()
        box.addItems(values)
        box.setCurrentText(getattr(self.s, attr) if getattr(self.s, attr) in values else values[0])
        box.currentTextChanged.connect(lambda text: (setattr(self.s, attr, text), self._changed()))
        form.addRow(label, box)

    def _general(self) -> QWidget:
        page, form = self._page()
        self._entry(form, "Output folder", self.s.out_root, "out_root")
        skip = QCheckBox("Skip existing outputs", checked=self.s.skip_existing)
        skip.toggled.connect(lambda on: (setattr(self.s, "skip_existing", on), self._changed()))
        form.addRow("", skip)
        self._combo(form, "Default device", DEVICES, "device")
        self._combo(form, "Interface (restart to apply)", FRONTENDS, "frontend")
        return page

    def _repos(self) -> QWidget:
        page, form = self._page("Where the projects this app wraps come from: a local checkout or a git URL (it is cloned "
                                "under ~/.local/share/audio-toolkit/repos). Leave a field empty to skip that tool.")
        for name in REPOS:
            self._entry(form, f"{name}: folder or git URL", repo_path(self.s, name), "repos", name)
        box = QGroupBox("Worker environment")
        row = QHBoxLayout(box)
        self.env_label = QLabel(wordWrap=True)
        self.env_btn = QPushButton("Set up / update")
        self.env_btn.clicked.connect(self._setup_env)
        row.addWidget(self.env_label, 1)
        row.addWidget(self.env_btn)
        page.body.insertWidget(page.body.count() - 1, box)  # type: ignore[attr-defined]
        self._env_status()
        return page

    def _env_status(self, text: str = "") -> None:
        python = worker_cmd(self.s)[0]
        self.env_label.setText(text or (f"Ready: {python}" if Path(python).is_file() else "Not set up yet"))

    def _setup_env(self) -> None:
        self.env_btn.setEnabled(False)

        def work() -> None:
            err = run_plan(plan(self.s), lambda label: self._progress.emit(label + "…"))
            self._finished.emit("env", err or "")

        threading.Thread(target=work, daemon=True).start()

    def _job_done(self, job: str, err: str) -> None:
        if job == "env":
            self.env_btn.setEnabled(True)
            self._env_status("Failed: " + err if err else "")
        if job == "model":
            self._rebuild_models()
        if job == "delete":
            self.delete_btn.setEnabled(True)
            self._data_status()
            self._env_status()
            self._rebuild_models()
        self.note.setText(err[:200])

    def _models(self) -> QWidget:
        self.models_page, self.models_form = self._page("Scan score needs these weights. They are not in the repository; "
                                                        "Download fetches them from Hugging Face.")
        self._rebuild_models()
        return self.models_page

    def _rebuild_models(self) -> None:
        form = self.models_form
        while form.rowCount():
            form.removeRow(0)
        root = local_checkout(self.s, "copisteria")
        if root is None:
            form.addRow("copisteria not configured", QLabel("Set it on the Repos tab first."))
            return
        for title, rel, hf_repo in WEIGHTS:
            have = (root / rel).is_file()
            mark = QLabel("found" if have else "missing")
            btn = QPushButton("Download", enabled=not have)
            btn.clicked.connect(lambda _=False, b=btn, m=mark, r=hf_repo, root=root: self._download(b, m, r, root))
            row = QHBoxLayout()
            row.addWidget(QLabel(str(root / rel), enabled=False), 1)
            row.addWidget(mark)
            row.addWidget(btn)
            form.addRow(title, row)

    def _download(self, btn: QPushButton, mark: QLabel, hf_repo: str, root: Path) -> None:
        btn.setEnabled(False)
        mark.setText("downloading…")
        hf = str(Path(worker_cmd(self.s)[0]).with_name("hf.exe" if os.name == "nt" else "hf"))
        cmd = [hf, "download", f"kobimusic/{hf_repo}", "--include", "*.pt", "--local-dir", str(root / "models")]

        def work() -> None:
            r = subprocess.run(cmd, capture_output=True, text=True)
            tail = (r.stderr or r.stdout).strip().splitlines()
            self._finished.emit("model", "" if r.returncode == 0 else (tail[-1] if tail else "download failed"))

        threading.Thread(target=work, daemon=True).start()

    def _paths(self) -> QWidget:
        page, form = self._page("Applies from the next worker start. Leave empty for the defaults.")
        self._entry(form, "Worker Python (default: the app's own environment)", self.s.worker_python, "worker_python")
        self._entry(form, "Extra PATH folders (ffmpeg, poppler)", self.s.extra_path, "extra_path")
        box = QGroupBox("Downloaded data")
        row = QHBoxLayout(box)
        self.data_label = QLabel(wordWrap=True)
        self.delete_btn = QPushButton("Delete…")
        self.delete_btn.clicked.connect(self._delete_data)
        row.addWidget(self.data_label, 1)
        row.addWidget(self.delete_btn)
        page.body.insertWidget(page.body.count() - 1, box)  # type: ignore[attr-defined]
        self._data_status()
        search = self.s.extra_path + os.pathsep + os.environ.get("PATH", "")
        for exe in ("ffmpeg", "pdftoppm"):
            form.addRow(exe, QLabel(shutil.which(exe, path=search) or "not found", enabled=False))
        return page

    def _data_status(self) -> None:
        size = data_size()
        self.data_label.setText(f"{data_dir()}\nWorker environment, cloned repos and downloaded tools: "
                                f"{size / 1e9:.1f} GB" if size else f"{data_dir()}\nNothing downloaded.")

    def _delete_data(self) -> None:
        box = QMessageBox(QMessageBox.Warning, "Delete downloaded data",
                          f"Deletes {data_dir()}: the worker environment, cloned repos and downloaded tools "
                          f"({data_size() / 1e9:.1f} GB). The environment can be set up again from the Repos tab.",
                          QMessageBox.Cancel | QMessageBox.Yes, self)
        also = QCheckBox("Also delete my settings and chains")
        box.setCheckBox(also)
        if box.exec() != QMessageBox.Yes:
            return
        self.delete_btn.setEnabled(False)
        self._stop_worker()  # a running worker holds files open
        include = also.isChecked()

        def work() -> None:
            try:
                remove_data(include)
                self._finished.emit("delete", "")
            except OSError as e:
                self._finished.emit("delete", f"Delete failed: {e}")

        threading.Thread(target=work, daemon=True).start()
