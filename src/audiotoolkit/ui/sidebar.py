"""Left pane: tap tempo on top, tool navigation below. The selected row merges into the content pane."""
from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from .tapper_widget import TapperWidget


class Sidebar(Gtk.WindowHandle):
    def __init__(self, on_select: Callable[[str], None]):
        super().__init__(width_request=240, css_classes=["sidebar-pane"])
        self._on_select = on_select
        self._kinds: dict[Gtk.ListBoxRow, str] = {}
        self.tapper = TapperWidget()
        self.tapper.set_margin_top(20)
        self.tapper.set_margin_bottom(16)
        self.tapper.set_margin_start(16)
        self.tapper.set_margin_end(16)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=["nav-list"], vexpand=True)
        self.list.connect("row-selected", self._selected)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self.tapper)
        box.append(self.list)
        self.set_child(box)

    def add_page(self, kind: str, title: str, icon: str) -> None:
        row = Gtk.ListBoxRow()
        content = Gtk.Box(spacing=12)
        content.append(Gtk.Image(icon_name=icon))
        content.append(Gtk.Label(label=title, xalign=0))
        row.set_child(content)
        self._kinds[row] = kind
        self.list.append(row)

    def select(self, kind: str) -> None:
        for row, k in self._kinds.items():
            if k == kind:
                self.list.select_row(row)

    def _selected(self, _list, row) -> None:
        if row is not None:
            self._on_select(self._kinds[row])
