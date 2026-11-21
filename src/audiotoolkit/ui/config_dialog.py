"""Settings page of the main window: General, Repos (local checkouts of the integrated projects), Models (weights), Paths."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from audiotoolkit.core.settings import Settings

from .bridge import repo_path, worker_cmd

REPOS = ("demucs", "dettato", "copisteria")
# copisteria weights relative to its checkout, and the Hugging Face repo each one comes from
WEIGHTS = (("Evidence model", "models/evidence-2m.pt", "copisteria"),
           ("Detector 28m", "models/small/v7_obj-recall-30m_best.pt", "copista-28m"),
           ("Detector 2m", "models/small/v7_obj-recall_best.pt", "copista-2m"))


def _run_async(cmd: list[str], done: Callable[[bool, str], None]) -> None:
    def work():
        r = subprocess.run(cmd, capture_output=True, text=True)
        tail = (r.stderr or r.stdout).strip().splitlines()
        GLib.idle_add(done, r.returncode == 0, tail[-1] if tail else "")

    threading.Thread(target=work, daemon=True).start()


class ConfigView(Gtk.Box):
    def __init__(self, settings: Settings, on_changed: Callable[[], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.s, self._changed = settings, on_changed
        stack = Adw.ViewStack()
        for page in (self._general(), self._repos(), self._models(), self._paths()):
            stack.add_titled_with_icon(page, page.get_title().lower(), page.get_title(), page.get_icon_name())
        switcher = Adw.ViewSwitcher(stack=stack, policy=Adw.ViewSwitcherPolicy.WIDE, halign=Gtk.Align.CENTER, margin_top=12)
        self.note = Gtk.Label(xalign=0, css_classes=["dim-label"], margin_start=24, margin_bottom=6)  # replaces toasts
        for w in (switcher, stack, self.note):
            self.append(w)
        stack.set_vexpand(True)

    def _page(self, title: str, icon: str, description: str = "") -> tuple[Adw.PreferencesPage, Adw.PreferencesGroup]:
        page = Adw.PreferencesPage(title=title, icon_name=icon)
        group = Adw.PreferencesGroup(description=description)
        page.add(group)
        return page, group

    def _entry(self, group, title: str, value: str, attr: str, key: str | None = None) -> Adw.EntryRow:
        row = Adw.EntryRow(title=title, text=value)

        def changed(r):
            target = getattr(self.s, attr)
            if key is None:
                setattr(self.s, attr, r.get_text())
            else:
                target[key] = r.get_text()
            self._changed()

        row.connect("changed", changed)
        group.add(row)
        return row

    def _general(self) -> Adw.PreferencesPage:
        page, g = self._page("General", "preferences-system-symbolic")
        self._entry(g, "Output folder", self.s.out_root, "out_root")
        skip = Adw.SwitchRow(title="Skip existing outputs", active=self.s.skip_existing)
        skip.connect("notify::active", lambda r, _p: (setattr(self.s, "skip_existing", r.get_active()), self._changed()))
        g.add(skip)
        devices = ["auto", "cuda", "cpu"]
        dev = Adw.ComboRow(title="Default device", model=Gtk.StringList.new(devices))
        dev.set_selected(devices.index(self.s.device) if self.s.device in devices else 0)
        dev.connect("notify::selected", lambda r, _p: (setattr(self.s, "device", devices[r.get_selected()]), self._changed()))
        g.add(dev)
        return page

    def _repos(self) -> Adw.PreferencesPage:
        page, g = self._page("Repos", "folder-symbolic",
                             "Local checkouts of the projects this app wraps. Reinstall runs pip install -e on the folder "
                             "in the worker's Python.")
        for name in REPOS:
            row = self._entry(g, name, repo_path(self.s, name), "repos", name)
            status = Gtk.Label(css_classes=["dim-label"])
            btn = Gtk.Button(label="Reinstall", valign=Gtk.Align.CENTER)

            def reinstall(_b, row=row, status=status, btn=btn):
                btn.set_sensitive(False)
                status.set_label("installing…")

                def done(ok, msg):
                    btn.set_sensitive(True)
                    status.set_label("installed" if ok else "failed")
                    if not ok:
                        self.note.set_label(msg[:160] or "pip failed")
                    return GLib.SOURCE_REMOVE

                _run_async([worker_cmd(self.s)[0], "-m", "pip", "install", "-q", "-e", row.get_text()], done)

            btn.connect("clicked", reinstall)
            row.add_suffix(status)
            row.add_suffix(btn)
        return page

    def _models(self) -> Adw.PreferencesPage:
        page, g = self._page("Models", "package-x-generic-symbolic",
                             "Scan score needs these weights. They are not in the repository; Download fetches them "
                             "from Hugging Face.")
        root = Path(repo_path(self.s, "copisteria"))
        for title, rel, hf_repo in WEIGHTS:
            row = Adw.ActionRow(title=title, subtitle=str(root / rel))
            have = (root / rel).is_file()
            mark = Gtk.Label(label="found" if have else "missing", css_classes=["dim-label"])
            btn = Gtk.Button(label="Download", valign=Gtk.Align.CENTER, sensitive=not have)

            def download(_b, btn=btn, mark=mark, hf_repo=hf_repo):
                btn.set_sensitive(False)
                mark.set_label("downloading…")
                hf = str(Path(worker_cmd(self.s)[0]).with_name("hf"))
                src = hf_repo if "/" in hf_repo else f"kobimusic/{hf_repo}"

                def done(ok, msg):
                    mark.set_label("found" if ok else "failed")
                    btn.set_sensitive(not ok)
                    if not ok:
                        self.note.set_label(msg[:160] or "download failed")
                    return GLib.SOURCE_REMOVE

                _run_async([hf, "download", src, "--include", "*.pt", "--local-dir", str(root / "models")], done)

            btn.connect("clicked", download)
            row.add_suffix(mark)
            row.add_suffix(btn)
            g.add(row)
        return page

    def _paths(self) -> Adw.PreferencesPage:
        page, g = self._page("Paths", "applications-system-symbolic",
                             "Applies from the next worker start. Leave empty for the defaults.")
        self._entry(g, "Worker Python (default: the app's .venv)", self.s.worker_python, "worker_python")
        self._entry(g, "Extra PATH folders (ffmpeg, poppler)", self.s.extra_path, "extra_path")
        tools = Adw.PreferencesGroup(title="Found on PATH")
        page.add(tools)
        for exe in ("ffmpeg", "pdftoppm"):
            where = shutil.which(exe, path=self.s.extra_path + os.pathsep + os.environ.get("PATH", ""))
            tools.add(Adw.ActionRow(title=exe, subtitle=where or "not found"))
        return page
