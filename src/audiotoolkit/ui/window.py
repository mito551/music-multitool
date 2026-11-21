"""Main window: sidebar (tap tempo + tool list) on the left, tool form and batch queue on the right."""
from __future__ import annotations

import os
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from audiotoolkit.core.paths import user_presets_dir
from audiotoolkit.core.presets import load_presets
from audiotoolkit.core.queue import Item, Status
from audiotoolkit.core.settings import Settings, save_settings

from .bridge import PRESETS_DIR, UiBackend
from .config_dialog import ConfigView
from .queue_view import QueueView
from .sidebar import Sidebar
from .tabs import TABS
from .tabs.chains_tab import ChainsTab

USER_PRESETS = user_presets_dir()


def load_css() -> None:
    provider = Gtk.CssProvider()
    provider.load_from_path(str(Path(__file__).with_name("style.css")))
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, settings: Settings):
        super().__init__(application=app, title="Audio Toolkit", default_width=1040, default_height=900)
        load_css()
        self.settings = settings
        self.presets = load_presets(str(PRESETS_DIR), USER_PRESETS)
        self.backend = UiBackend(settings, self.presets, self._on_change)
        self.queue_view = QueueView(self._override_dialog)

        self.stack = Adw.ViewStack(vhomogeneous=False)
        self.tabs: dict[str, object] = {}
        self.sidebar = Sidebar(self._show_tab, lambda: self._pick(False), lambda: self._pick(True), self._detect)
        for kind, cls in TABS.items():
            self._add_tab(kind, cls())  # hidden kinds get a tab object (chains, opts) but no sidebar entry
        self.chains = ChainsTab()
        self._add_tab("chain", self.chains)
        self.chains.bind(str(PRESETS_DIR), USER_PRESETS, self._presets_changed)
        self.stack.add_named(ConfigView(settings, self._config_changed, self.backend.close), "settings")
        self.sidebar.add_page("settings", "Settings", "emblem-system-symbolic")

        # The form area takes whatever height is left and scrolls if a form is taller; its size never depends on the
        # visible tab, and the queue below has one fixed height for every tab.
        forms = Gtk.ScrolledWindow(child=self.stack, hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True,
                                   css_classes=["form-area"])
        forms.set_overflow(Gtk.Overflow.HIDDEN)
        # Both dividers drag; the sizes are saved with the settings. The queue keeps its height when the window grows.
        self.main = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL, shrink_start_child=False, shrink_end_child=False,
                              resize_start_child=True, resize_end_child=False, start_child=forms,
                              end_child=self._queue_panel(), position=900 - 48 - settings.queue_height)
        header = Adw.HeaderBar(title_widget=Gtk.Box(), css_classes=["flat"])  # window controls only
        content = Adw.ToolbarView(content=self.main, hexpand=True, css_classes=["content-pane"])
        content.add_top_bar(header)
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        content.add_controller(drop)

        self.root = Gtk.Paned(shrink_start_child=False, shrink_end_child=False, resize_start_child=False,
                              start_child=self.sidebar, end_child=content, position=settings.sidebar_width)
        self.set_content(self.root)
        self.sidebar.select(next(iter(self.tabs)))
        self.connect("close-request", self._on_close)

    def _add_tab(self, kind: str, tab) -> None:
        tab.set_opts(self.settings.tab_opts.get(kind, {}))
        tab.on_add = lambda paths, k=kind: self.add_paths(paths, k)
        self.tabs[kind] = tab
        if not tab.hidden:
            self.stack.add_named(tab, kind)
            self.sidebar.add_page(kind, tab.title, tab.icon)

    def _show_tab(self, kind: str) -> None:
        self.stack.set_visible_child_name(kind)

    def _queue_panel(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=8, margin_bottom=20,
                      margin_start=24, margin_end=24)
        bar = Gtk.Box(spacing=8)
        for label, handler in (("Run", self._run), ("Cancel", lambda *_: self.backend.cancel()),
                               ("Retry failed", lambda *_: self.backend.retry_failed()), ("Clear done", self._clear_done)):
            b = Gtk.Button(label=label)
            b.connect("clicked", handler)
            if label == "Run":
                b.add_css_class("suggested-action")
            bar.append(b)
        bar.append(Gtk.Box(hexpand=True))
        skip = Gtk.Switch(active=self.settings.skip_existing, valign=Gtk.Align.CENTER)
        skip.connect("notify::active", self._skip_toggled)
        self.out_button = Gtk.Button(label=self._out_label())
        self.out_button.connect("clicked", self._choose_out)
        for w in (Gtk.Label(label="Skip existing"), skip, self.out_button):
            bar.append(w)
        box.append(bar)
        box.append(self.queue_view)
        return box

    def _out_label(self) -> str:
        return "Output: " + os.path.basename(self.settings.out_root.rstrip("/"))

    # -- actions ------------------------------------------------------------------------------------------------

    def _presets_changed(self, presets: dict) -> None:
        self.presets = presets
        self.backend.set_presets(presets)

    def _pick(self, folder: bool) -> None:
        dialog = Gtk.FileDialog()

        def done(d, result):
            try:
                files = [d.select_folder_finish(result)] if folder else d.open_multiple_finish(result)
            except GLib.Error:  # dialog cancelled
                return
            tab = self.tabs.get(self.stack.get_visible_child_name())
            if tab:
                tab.accept([f.get_path() for f in files if f and f.get_path()])

        if folder:
            dialog.select_folder(self, None, done)
        else:
            dialog.open_multiple(self, None, done)

    def add_paths(self, paths: list[str], kind: str) -> None:
        self.backend.add(paths, kind, self.tabs[kind].get_opts())

    def _on_drop(self, _target, value, _x, _y) -> bool:
        paths = [f.get_path() for f in value.get_files() if f.get_path()]
        kind = self.stack.get_visible_child_name()
        if kind not in self.tabs:
            return False
        self.tabs[kind].accept(paths)
        return True

    def _on_change(self, item: Item) -> None:
        self.queue_view.update(item)
        if item.kind == "analyze" and item.status is Status.DONE:  # the sidebar shows the latest analysis
            self.sidebar.tapper.set_detected(item.result.get("bpm") or None)
            self.sidebar.set_key(item.result.get("key"), item.result.get("key_confidence", 0.0))

    def _detect(self) -> None:
        dialog = Gtk.FileDialog(title="Detect BPM and key")

        def done(d, result):
            try:
                f = d.open_finish(result)
            except GLib.Error:
                return
            if self.backend.add([f.get_path()], "analyze", {}):
                self._run()

        dialog.open(self, None, done)

    def _config_changed(self) -> None:
        self.out_button.set_label(self._out_label())
        self._save()

    def _run(self, *_) -> None:
        self._save()
        self.backend.start()

    def _clear_done(self, *_) -> None:
        for item in list(self.backend.queue.items):
            if item.status in (Status.DONE, Status.SKIPPED):
                self.backend.queue.remove(item.id)
                self.queue_view.remove(item.id)

    def _choose_out(self, *_) -> None:
        dialog = Gtk.FileDialog()

        def done(d, result):
            try:
                folder = d.select_folder_finish(result)
            except GLib.Error:
                return
            self.settings.out_root = folder.get_path()
            self.out_button.set_label(self._out_label())
            self._save()

        dialog.select_folder(self, None, done)

    def _skip_toggled(self, switch, _pspec) -> None:
        self.settings.skip_existing = switch.get_active()
        self._save()

    def _override_dialog(self, item: Item) -> None:
        tab = TABS[item.kind](embedded=True)
        tab.set_opts(self.backend.queue.effective_opts(item))
        apply_btn = Gtk.Button(label="Apply", halign=Gtk.Align.END, margin_bottom=16, margin_end=24,
                               css_classes=["suggested-action"])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_start=24, margin_end=24)
        box.append(tab)
        box.append(apply_btn)
        dialog = Adw.Dialog(title=f"Options: {item.song}", child=box, content_width=480)

        def apply(*_):
            self.backend.queue.set_override(item.id, tab.get_opts())
            dialog.close()

        apply_btn.connect("clicked", apply)
        dialog.present(self)

    def _save(self) -> None:
        self.settings.tab_opts = {k: t.get_opts() for k, t in self.tabs.items()}
        self.settings.sidebar_width = self.root.get_position()
        if self.main.get_height() > 0:
            self.settings.queue_height = max(80, self.main.get_height() - self.main.get_position())
        save_settings(self.settings)
        self.backend.update_settings(self.settings)

    def _on_close(self, *_) -> bool:
        self._save()
        self.backend.close()
        return False
