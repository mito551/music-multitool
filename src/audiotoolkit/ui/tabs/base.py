"""Base class and form-row helpers for the tool tabs."""
from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402


def combo(title: str, labels: list[str]) -> Adw.ComboRow:
    row = Adw.ComboRow(title=title)
    row.set_model(Gtk.StringList.new(labels))
    return row


def combo_value(row: Adw.ComboRow) -> str:
    return row.get_selected_item().get_string()


def set_combo(row: Adw.ComboRow, value) -> None:
    model = row.get_model()
    labels = [model.get_string(i) for i in range(model.get_n_items())]
    if str(value) in labels:
        row.set_selected(labels.index(str(value)))


def spin(title: str, lo: float, hi: float, step: float, value: float, digits: int = 0) -> Adw.SpinRow:
    row = Adw.SpinRow.new_with_range(lo, hi, step)
    row.set_title(title)
    row.set_digits(digits)
    row.set_value(value)
    return row


def switch(title: str, active: bool = False) -> Adw.SwitchRow:
    row = Adw.SwitchRow(title=title)
    row.set_active(active)
    return row


def entry(title: str, text: str = "") -> Adw.EntryRow:
    row = Adw.EntryRow(title=title)
    row.set_text(text)
    return row


class ToolTab(Gtk.Box):
    """One tool's settings form. Subclasses set `kind`/`title` and implement build/get_opts/set_opts."""

    kind: str = ""
    title: str = ""
    icon: str = "image-missing"
    has_opts: bool = True  # False: nothing to configure, so no override/step-options dialog

    def __init__(self, embedded: bool = False) -> None:
        """embedded=True: the form alone, for dialogs (no Add files/folder buttons, no outer margins)."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.embedded = embedded
        if not embedded:
            for side, px in (("top", 24), ("bottom", 12), ("start", 24), ("end", 24)):
                getattr(self, f"set_margin_{side}")(px)
        self.on_add: Callable[[list[str]], None] = lambda paths: None
        self.group = Adw.PreferencesGroup()  # no heading: the title bar and sidebar already name the tool
        self.append(self.group)
        self.build(self.group)

    def add_buttons(self) -> None:
        if self.embedded:
            return
        box = Gtk.Box(spacing=6)
        files = Gtk.Button(label="Add files…")
        folder = Gtk.Button(label="Add folder…")
        files.connect("clicked", lambda *_: self._pick(folder=False))
        folder.connect("clicked", lambda *_: self._pick(folder=True))
        box.append(files)
        box.append(folder)
        self.append(box)

    def _pick(self, folder: bool) -> None:
        dialog = Gtk.FileDialog()
        parent = self.get_root()
        def done(d, result):
            try:
                files = [d.select_folder_finish(result)] if folder else d.open_multiple_finish(result)
            except GLib.Error:  # dialog cancelled
                return
            self._picked(files, result)

        if folder:
            dialog.select_folder(parent, None, done)
        else:
            dialog.open_multiple(parent, None, done)

    def _picked(self, files, _result) -> None:
        self.on_add([f.get_path() for f in files if f is not None and f.get_path()])

    def build(self, group: Adw.PreferencesGroup) -> None:
        raise NotImplementedError

    def get_opts(self) -> dict:
        raise NotImplementedError

    def set_opts(self, opts: dict) -> None:
        raise NotImplementedError
