"""Left pane: tap tempo on top, tool navigation below. The selected row merges into the content pane."""
from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from .tapper_widget import TapperWidget


class Sidebar(Gtk.WindowHandle):
    def __init__(self, on_select: Callable[[str], None], on_files: Callable[[], None], on_folder: Callable[[], None],
                 on_detect: Callable[[], None] = lambda: None):
        super().__init__(width_request=200, css_classes=["sidebar-pane"])
        self._on_select = on_select
        self._kinds: dict[Gtk.ListBoxRow, str] = {}
        self.tapper = TapperWidget()
        self.tapper.set_margin_top(20)
        self.tapper.set_margin_bottom(16)
        self.tapper.set_margin_start(16)
        self.tapper.set_margin_end(16)
        self.key = Gtk.Label(label="Key: —", xalign=0, margin_start=16, margin_end=16, margin_bottom=12,
                             css_classes=["title-3"])
        detect = Gtk.Button(label="Detect BPM & key…", margin_start=16, margin_end=16, margin_bottom=16,
                            tooltip_text="Analyze one audio file (a few seconds)")
        detect.connect("clicked", lambda *_: on_detect())
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=["nav-list"])
        self.list.connect("row-selected", self._selected)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self.tapper)
        box.append(self.key)
        box.append(detect)
        box.append(self.list)
        add = Gtk.Box(spacing=8, homogeneous=True, margin_start=12, margin_end=12, margin_top=12, margin_bottom=16)
        for label, handler in (("Add files…", on_files), ("Add folder…", on_folder)):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda *_, h=handler: h())
            add.append(b)
        box.append(add)
        self.set_child(box)

    def add_page(self, kind: str, title: str, icon: str) -> None:
        row = Gtk.ListBoxRow()
        content = Gtk.Box(spacing=12)
        content.append(Gtk.Image(icon_name=icon))
        content.append(Gtk.Label(label=title, xalign=0))
        row.set_child(content)
        self._kinds[row] = kind
        self.list.append(row)

    def set_key(self, key: str | None, confidence: float = 0.0) -> None:
        self.key.set_label(f"Key: {key} ({confidence:.0%})" if key else "Key: —")

    def select(self, kind: str) -> None:
        for row, k in self._kinds.items():
            if k == kind:
                self.list.select_row(row)

    def _selected(self, _list, row) -> None:
        if row is not None:
            self._on_select(self._kinds[row])
