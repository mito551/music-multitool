"""The queue list: one row per item with status icon, progress bar and per-item buttons."""
from __future__ import annotations

import os
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from audiotoolkit.core.queue import Item, Status

from .tabs import RESULT_TEXT, TABS

QUEUE_HEIGHT = 240  # same on every tab
ICONS = {
    Status.PENDING: "document-open-recent-symbolic", Status.RUNNING: "process-working-symbolic",
    Status.DONE: "object-select-symbolic", Status.FAILED: "dialog-error-symbolic", Status.SKIPPED: "go-next-symbolic",
    Status.CANCELLED: "process-stop-symbolic",
}


def describe(item: Item) -> str:
    text = item.message
    if item.status in (Status.DONE, Status.SKIPPED) and item.kind in RESULT_TEXT:
        text = RESULT_TEXT[item.kind](item.result)
    label = f"{item.kind} · {item.status.value}"
    return f"{label} · {text}" if text else label


class _Row:
    def __init__(self, item: Item, on_override: Callable[[Item], None]):
        self.item = item
        self.widget = Adw.ActionRow(title=GLib.markup_escape_text(item.song))
        self.icon = Gtk.Image()
        self.bar = Gtk.ProgressBar(valign=Gtk.Align.CENTER, width_request=140)
        self.override = Gtk.Button(icon_name="document-edit-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Override options")
        self.folder = Gtk.Button(icon_name="folder-open-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Open output folder")
        self.override.connect("clicked", lambda *_: on_override(self.item))
        self.folder.connect("clicked", lambda *_: self._open_folder())
        self.widget.add_prefix(self.icon)
        for w in (self.bar, self.override, self.folder):
            self.widget.add_suffix(w)

    def _open_folder(self) -> None:
        if self.item.outputs:
            uri = Gio.File.new_for_path(os.path.dirname(self.item.outputs[0].path)).get_uri()
            Gio.AppInfo.launch_default_for_uri(uri, None)

    def refresh(self, item: Item) -> None:
        self.item = item
        self.widget.set_title(GLib.markup_escape_text(item.song))
        self.widget.set_subtitle(GLib.markup_escape_text(describe(item)))
        self.icon.set_from_icon_name(ICONS[item.status])
        self.bar.set_fraction(1.0 if item.status in (Status.DONE, Status.SKIPPED) else item.fraction or 0.0)
        self.override.set_sensitive(item.status is Status.PENDING and item.kind in TABS and TABS[item.kind].has_opts)
        self.folder.set_sensitive(bool(item.outputs))


class QueueView(Gtk.ScrolledWindow):
    def __init__(self, on_override: Callable[[Item], None]):
        super().__init__(vexpand=False, min_content_height=QUEUE_HEIGHT, max_content_height=QUEUE_HEIGHT)
        self._on_override = on_override
        self._rows: dict[str, _Row] = {}
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list.add_css_class("boxed-list")
        self.set_child(self.list)
        GLib.timeout_add(120, self._pulse)

    def update(self, item: Item) -> None:
        row = self._rows.get(item.id)
        if row is None:
            row = self._rows[item.id] = _Row(item, self._on_override)
            self.list.append(row.widget)
        row.refresh(item)

    def remove(self, item_id: str) -> None:
        row = self._rows.pop(item_id, None)
        if row is not None:
            self.list.remove(row.widget)

    def _pulse(self) -> bool:
        for row in self._rows.values():
            if row.item.status is Status.RUNNING and row.item.fraction is None:
                row.bar.pulse()
        return GLib.SOURCE_CONTINUE
