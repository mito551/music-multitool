from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib  # noqa: E402

from musicmultitool.core.settings import load_settings

from .window import MainWindow

APP_ID = "io.github.mito551.MusicMultitool"


class MusicMultitoolApp(Adw.Application):
    def __init__(self, smoke: bool = False):
        super().__init__(application_id=APP_ID)
        self.smoke = smoke

    def do_activate(self) -> None:
        win = self.props.active_window or MainWindow(self, load_settings())
        win.present()
        if self.smoke:
            GLib.timeout_add(500, self.quit)


def main(argv: list[str]) -> int:
    smoke = "--smoke" in argv
    return MusicMultitoolApp(smoke).run([a for a in argv if a != "--smoke"])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
