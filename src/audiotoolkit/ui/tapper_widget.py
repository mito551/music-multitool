"""Tap-tempo widget: Tap button / Space, live BPM, comparison with the last detected BPM."""
from __future__ import annotations

import time

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from audiotoolkit.core.tapper import Tapper, relation


class TapperWidget(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12)
        self.tapper = Tapper()
        self.bpm: float | None = None
        self.detected: float | None = None
        self._key = Gtk.EventControllerKey()
        self._key.connect("key-pressed", self._on_key)

        self.value = Gtk.Label(label="— BPM")
        self.value.add_css_class("title-1")
        self.info = Gtk.Label(label="Tap the button or press Space", css_classes=["dim-label"])
        tap = Gtk.Button(label="Tap", focusable=False, height_request=72)
        tap.add_css_class("suggested-action")
        tap.add_css_class("pill")
        tap.connect("clicked", lambda *_: self.tap_now())
        row = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        reset, copy = Gtk.Button(label="Reset"), Gtk.Button(label="Copy BPM")
        reset.connect("clicked", lambda *_: self.reset())
        copy.connect("clicked", lambda *_: self._copy())
        row.append(reset)
        row.append(copy)
        for w in (Gtk.Label(label="BPM tapper", xalign=0, css_classes=["heading"]), self.value, self.info, tap, row):
            self.append(w)
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)

    def _on_map(self, *_) -> None:
        self.get_root().add_controller(self._key)

    def _on_unmap(self, *_) -> None:
        root = self.get_root()
        if root is not None:
            root.remove_controller(self._key)

    def _on_key(self, _ctrl, keyval, _code, _state) -> bool:
        if keyval != Gdk.KEY_space or isinstance(self.get_root().get_focus(), Gtk.Editable):
            return False
        self.tap_now()
        return True

    def tap_now(self, now: float | None = None) -> None:
        self.bpm = self.tapper.tap(time.monotonic() if now is None else now)
        self._refresh()

    def reset(self) -> None:
        self.tapper.reset()
        self.bpm = None
        self._refresh()

    def set_detected(self, bpm: float | None) -> None:
        self.detected = bpm
        self._refresh()

    def _refresh(self) -> None:
        self.value.set_label("— BPM" if self.bpm is None else f"{self.bpm:.1f} BPM")
        text = f"{self.tapper.count} taps"
        if self.bpm is not None and self.detected:
            text += f" · detected {self.detected:.1f} BPM → {relation(self.bpm, self.detected)}"
        elif self.detected:
            text += f" · detected {self.detected:.1f} BPM"
        self.info.set_label(text if self.tapper.count else "Tap the button or press Space")

    def _copy(self) -> None:
        if self.bpm is not None:
            self.get_clipboard().set(f"{self.bpm:.1f}")
