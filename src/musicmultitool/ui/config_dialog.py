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

from musicmultitool.core.components import BY_ID, COMPONENTS, IDS, estimate_mb, human, installed
from musicmultitool.core.paths import data_dir
from musicmultitool.core.provision import data_size, remove_data
from musicmultitool.core.settings import Settings

from musicmultitool.core.setup_env import REPOS, has_nvidia, local_checkout, plan, run_plan

from .bridge import repo_path, worker_cmd

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
    def __init__(self, settings: Settings, on_changed: Callable[[], None], stop_worker: Callable[[], None],
                 compact: bool = False):  # compact: only the Components page, for the first-run pop-up
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.s, self._changed, self._stop_worker = settings, on_changed, stop_worker
        stack = self.stack = Adw.ViewStack()
        for page in (self._components(), self._general(), self._repos(), self._models(), self._paths()):
            stack.add_titled_with_icon(page, page.get_title().lower(), page.get_title(), page.get_icon_name())
        switcher = Adw.ViewSwitcher(stack=stack, policy=Adw.ViewSwitcherPolicy.WIDE, halign=Gtk.Align.CENTER, margin_top=12)
        self.note = Gtk.Label(xalign=0, css_classes=["dim-label"], margin_start=24, margin_bottom=6)  # replaces toasts
        switcher.set_visible(not compact)
        for w in (switcher, stack, self.note):
            self.append(w)
        stack.set_vexpand(True)

    def _page(self, title: str, icon: str, description: str = "") -> tuple[Adw.PreferencesPage, Adw.PreferencesGroup]:
        page = Adw.PreferencesPage(title=title, icon_name=icon)
        group = Adw.PreferencesGroup(description=description)
        page.add(group)
        return page, group

    def _entry(self, group, title: str, value: str, attr: str, key: str | None = None, browse: bool = False) -> Adw.EntryRow:
        row = Adw.EntryRow(title=title, text=value)

        def changed(r):
            target = getattr(self.s, attr)
            if key is None:
                setattr(self.s, attr, r.get_text())
            else:
                target[key] = r.get_text()
            self._changed()

        row.connect("changed", changed)
        if browse:
            button = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Browse…")
            button.add_css_class("flat")

            def pick(_b) -> None:
                dialog = Gtk.FileDialog(title=title)

                def done(d, result):
                    try:
                        folder = d.select_folder_finish(result)
                    except GLib.Error:
                        return
                    row.set_text(folder.get_path())

                dialog.select_folder(self.get_root(), None, done)

            button.connect("clicked", pick)
            row.add_suffix(button)
        group.add(row)
        return row

    def _general(self) -> Adw.PreferencesPage:
        page, g = self._page("General", "preferences-system-symbolic")
        self._entry(g, "Output folder", self.s.out_root, "out_root", browse=True)
        skip = Adw.SwitchRow(title="Skip existing outputs", active=self.s.skip_existing)
        skip.connect("notify::active", lambda r, _p: (setattr(self.s, "skip_existing", r.get_active()), self._changed()))
        g.add(skip)
        devices = ["auto", "cuda", "cpu"]
        dev = Adw.ComboRow(title="Default device", model=Gtk.StringList.new(devices))
        dev.set_selected(devices.index(self.s.device) if self.s.device in devices else 0)
        dev.connect("notify::selected", lambda r, _p: (setattr(self.s, "device", devices[r.get_selected()]), self._changed()))
        g.add(dev)
        uis = ["auto", "gtk", "qt"]
        ui = Adw.ComboRow(title="Interface (restart to apply)", model=Gtk.StringList.new(uis))
        ui.set_selected(uis.index(self.s.frontend) if self.s.frontend in uis else 0)
        ui.connect("notify::selected", lambda r, _p: (setattr(self.s, "frontend", uis[r.get_selected()]), self._changed()))
        g.add(ui)
        return page

    def _repos(self) -> Adw.PreferencesPage:
        page, g = self._page("Repos", "folder-symbolic",
                             "Where the projects this app wraps come from: a local checkout or a git URL (it is cloned "
                             "under ~/.local/share/music-multitool/repos). Leave a field empty to skip that tool.")
        for name in REPOS:
            self._entry(g, f"{name}: folder or git URL", repo_path(self.s, name), "repos", name, browse=True)
        return page

    def show_components(self) -> None:
        self.stack.set_visible_child_name("components")

    def _components(self) -> Adw.PreferencesPage:
        page, g = self._page("Components", "package-x-generic-symbolic",
                             "Nothing heavy is installed until you choose it. Sizes are approximate disk use; downloads "
                             "are smaller. Switch on what you want, then press Install.")
        self._gpu = has_nvidia()
        if self._gpu:
            row = Adw.SwitchRow(title="Use the NVIDIA GPU", subtitle="CUDA build of PyTorch: much faster, several GB larger",
                                active=self.s.use_gpu)
            row.connect("notify::active", lambda r, _p: (setattr(self.s, "use_gpu", r.get_active()), self._changed(),
                                                         self._summary()))
        else:
            row = Adw.ActionRow(title="No NVIDIA GPU found", subtitle="PyTorch will be the smaller CPU-only build, and slower")
        g.add(row)
        comps = Adw.PreferencesGroup()
        page.add(comps)
        done = set(installed())
        if not self.s.components:
            self.s.components = sorted(done)
        for c in COMPONENTS:
            lines = [c.function, c.note] if c.note else [c.function]
            if c.needs_torch:
                lines.append("Needs PyTorch (shared with the other tools that use it).")
            if c.repo and not self.s.repos.get(c.repo, "").strip():
                lines.append(f"Needs a {c.repo} folder or git URL on the Repos tab.")
            row = Adw.SwitchRow(title=GLib.markup_escape_text(c.name), subtitle=GLib.markup_escape_text("\n".join(lines)),
                                active=c.id in self.s.components)
            row.add_suffix(Gtk.Label(label=f"≈ {human(c.mb)}" + ("  ✓ installed" if c.id in done else ""),
                                     css_classes=["dim-label"]))
            row.connect("notify::active", lambda r, _p, cid=c.id: self._pick(cid, r.get_active()))
            comps.add(row)
        run = Adw.PreferencesGroup()
        page.add(run)
        self.summary_row = Adw.ActionRow(title="Install")
        self.env_btn = Gtk.Button(label="Install selected", valign=Gtk.Align.CENTER, css_classes=["suggested-action"])
        self.env_btn.connect("clicked", self._setup_env)
        self.summary_row.add_suffix(self.env_btn)
        run.add(self.summary_row)
        self.env_row = Adw.ActionRow(title="Worker environment")
        run.add(self.env_row)
        self._summary()
        self._env_status()
        return page

    def _pick(self, cid: str, on: bool) -> None:
        chosen = set(self.s.components)
        (chosen.add if on else chosen.discard)(cid)
        self.s.components = [i for i in IDS if i in chosen]
        self._changed()
        self._summary()

    def _summary(self) -> None:
        pending = [i for i in self.s.components if i not in installed()]
        mb = estimate_mb(pending, self.s.use_gpu and self._gpu, os.name == "nt")
        self.summary_row.set_subtitle(GLib.markup_escape_text(
            f"{', '.join(BY_ID[i].name for i in pending)}: about {human(mb)} on disk" if pending else "Nothing selected to install"))
        self.env_btn.set_sensitive(bool(pending))

    def _env_status(self, text: str = "") -> None:
        ready = Path(worker_cmd(self.s)[0]).is_file()
        self.env_row.set_subtitle(text or (f"ready: {worker_cmd(self.s)[0]}" if ready else "not set up yet"))

    def _setup_env(self, *_) -> None:
        self.env_btn.set_sensitive(False)

        def work():
            err = run_plan(plan(self.s, self.s.components), lambda label: GLib.idle_add(self._env_status, label + "…"))
            GLib.idle_add(finish, err)

        def finish(err):
            self._env_status("failed: " + err if err else "")
            self._summary()
            if err:
                self.note.set_label(err[:200])
            return GLib.SOURCE_REMOVE

        threading.Thread(target=work, daemon=True).start()

    def _models(self) -> Adw.PreferencesPage:
        page, g = self._page("Models", "package-x-generic-symbolic",
                             "Scan score needs these weights. They are not in the repository; Download fetches them "
                             "from Hugging Face.")
        root = local_checkout(self.s, "copisteria")
        if root is None:
            g.add(Adw.ActionRow(title="copisteria not configured", subtitle="Set it on the Repos tab first."))
            return page
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
        data = Adw.PreferencesGroup(title="Downloaded data")
        page.add(data)
        self.data_row = Adw.ActionRow(title=str(data_dir()))
        delete = Gtk.Button(label="Delete…", valign=Gtk.Align.CENTER, css_classes=["destructive-action"])
        delete.connect("clicked", self._delete_data)
        self.data_row.add_suffix(delete)
        data.add(self.data_row)
        self._data_status()
        tools = Adw.PreferencesGroup(title="Found on PATH")
        page.add(tools)
        for exe in ("ffmpeg", "pdftoppm"):
            where = shutil.which(exe, path=self.s.extra_path + os.pathsep + os.environ.get("PATH", ""))
            tools.add(Adw.ActionRow(title=exe, subtitle=where or "not found"))
        return page

    def _data_status(self) -> None:
        size = data_size()
        self.data_row.set_subtitle(f"Environment, repos and tools: {size / 1e9:.1f} GB" if size else "Nothing downloaded")

    def _delete_data(self, *_) -> None:
        also = Gtk.CheckButton(label="Also delete my settings and chains")
        dialog = Adw.AlertDialog(heading="Delete downloaded data?",
                                 body=f"Removes {data_dir()}: the worker environment, cloned repos and downloaded tools "
                                      f"({data_size() / 1e9:.1f} GB). Set it up again from the Repos tab.")
        dialog.set_extra_child(also)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def done(_d, response):
            if response != "delete":
                return
            self._stop_worker()  # a running worker holds files open
            include = also.get_active()

            def work():
                try:
                    remove_data(include)
                    err = ""
                except OSError as e:
                    err = f"Delete failed: {e}"
                GLib.idle_add(finish, err)

            def finish(err):
                self._data_status()
                self._env_status(err)
                self._summary()
                return GLib.SOURCE_REMOVE

            threading.Thread(target=work, daemon=True).start()

        dialog.connect("response", done)
        dialog.present(self)
