"""Main window: tool tabs on top, the batch queue below."""
from __future__ import annotations

import os

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from audiotoolkit.core.presets import load_presets
from audiotoolkit.core.queue import Item, Status
from audiotoolkit.core.settings import Settings, save_settings

from .bridge import APP_DIR, UiBackend
from .queue_view import QueueView
from .tabs import TABS

USER_PRESETS = os.path.expanduser("~/.config/audio-toolkit/presets")


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, settings: Settings):
        super().__init__(application=app, title="Audio Toolkit", default_width=900, default_height=780)
        self.settings = settings
        self.presets = load_presets(str(APP_DIR / "presets"), USER_PRESETS)
        self.backend = UiBackend(settings, self.presets, self._on_change)
        self.queue_view = QueueView(self._override_dialog)

        self.stack = Adw.ViewStack()
        self.tabs: dict[str, object] = {}
        for kind, cls in TABS.items():
            self._add_tab(kind, cls())

        header = Adw.HeaderBar()
        header.set_title_widget(Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE))
        paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL, position=420, shrink_start_child=False)
        paned.set_start_child(self.stack)
        paned.set_end_child(self._queue_panel())
        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(paned)
        self.set_content(view)
        self.connect("close-request", self._on_close)

    def _add_tab(self, kind: str, tab) -> None:
        tab.set_opts(self.settings.tab_opts.get(kind, {}))
        tab.on_add = lambda paths, k=kind: self.add_paths(paths, k)
        self.tabs[kind] = tab
        self.stack.add_titled(tab, kind, tab.title)

    def _queue_panel(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6, margin_bottom=12, margin_start=12, margin_end=12)
        bar = Gtk.Box(spacing=6)
        for label, handler in (("Run", self._run), ("Cancel", lambda *_: self.backend.cancel()),
                               ("Retry failed", lambda *_: self.backend.retry_failed()), ("Clear done", self._clear_done)):
            b = Gtk.Button(label=label)
            b.connect("clicked", handler)
            if label == "Run":
                b.add_css_class("suggested-action")
            bar.append(b)
        spacer = Gtk.Box(hexpand=True)
        self.out_button = Gtk.Button(label=self._out_label())
        self.out_button.connect("clicked", self._choose_out)
        skip = Gtk.Switch(active=self.settings.skip_existing, valign=Gtk.Align.CENTER)
        skip.connect("notify::active", self._skip_toggled)
        for w in (spacer, Gtk.Label(label="Skip existing"), skip, self.out_button):
            bar.append(w)
        box.append(bar)
        box.append(self.queue_view)
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        box.add_controller(drop)
        return box

    def _out_label(self) -> str:
        return "Output: " + os.path.basename(self.settings.out_root.rstrip("/"))

    # -- actions ------------------------------------------------------------------------------------------------

    def add_paths(self, paths: list[str], kind: str) -> None:
        self.backend.add(paths, kind, self.tabs[kind].get_opts())

    def _on_drop(self, _target, value, _x, _y) -> bool:
        paths = [f.get_path() for f in value.get_files() if f.get_path()]
        kind = self.stack.get_visible_child_name()
        if kind not in self.tabs:
            return False
        self.add_paths(paths, kind)
        return True

    def _on_change(self, item: Item) -> None:
        self.queue_view.update(item)
        if item.kind == "analyze" and item.status is Status.DONE:  # the tapper compares against the latest analysis
            self.tabs["analyze"].tapper.set_detected(item.result.get("bpm"))

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
        tab = TABS[item.kind]()
        tab.set_opts(self.backend.queue.effective_opts(item))
        apply_btn = Gtk.Button(label="Apply", halign=Gtk.Align.END, margin_bottom=12, margin_end=12)
        apply_btn.add_css_class("suggested-action")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
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
        save_settings(self.settings)
        self.backend.update_settings(self.settings)

    def _on_close(self, *_) -> bool:
        self._save()
        self.backend.close()
        return False
