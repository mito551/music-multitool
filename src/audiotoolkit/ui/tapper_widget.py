"""Tap-tempo block for the sidebar: big TAP button, live BPM, reset/copy, comparison with the last detected BPM."""
from __future__ import annotations

import time

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from audiotoolkit.core.tapper import Tapper, relation


class TapperWidget(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.tapper = Tapper()
        self.bpm: float | None = None
        self.detected: float | None = None
        # Capture phase: Space must tap even while a button has focus (a focused button would turn it into a click).
        self._key = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        self._key.connect("key-pressed", self._on_key)

        tap = Gtk.Button(label="TAP", width_request=76, height_request=76, valign=Gtk.Align.CENTER, focusable=False,
                         css_classes=["circular", "suggested-action", "tap-button"])
        tap.connect("clicked", lambda *_: self.tap_now())
        self.value = Gtk.Label(label="BPM: —", xalign=0, css_classes=["title-3"])
        self.taps = Gtk.Label(label="Tap or press Space", xalign=0, css_classes=["caption", "dim-label"])
        reset = Gtk.Button(icon_name="edit-undo-symbolic", tooltip_text="Reset taps", css_classes=["flat", "circular"], focusable=False)
        copy = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text="Copy BPM", css_classes=["flat", "circular"], focusable=False)
        reset.connect("clicked", lambda *_: self.reset())
        copy.connect("clicked", lambda *_: self._copy())
        buttons = Gtk.Box(spacing=2)
        buttons.append(reset)
        buttons.append(copy)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER, hexpand=True)
        for w in (self.value, self.taps, buttons):
            info.append(w)
        row = Gtk.Box(spacing=14)
        row.append(tap)
        row.append(info)
        self.hint = Gtk.Label(xalign=0, wrap=True, css_classes=["caption", "dim-label"], visible=False)
        self.append(row)
        self.append(self.hint)
        self.connect("map", lambda *_: self.get_root().add_controller(self._key))
        self.connect("unmap", self._on_unmap)

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
        self.value.set_label("BPM: —" if self.bpm is None else f"BPM: {self.bpm:.1f}")
        self.taps.set_label(f"{self.tapper.count} taps" if self.tapper.count else "Tap or press Space")
        hint = ""
        if self.detected:
            hint = f"Detected {self.detected:.1f} BPM"
            if self.bpm is not None:
                hint += f" → {relation(self.bpm, self.detected)}"
        self.hint.set_label(hint)
        self.hint.set_visible(bool(hint))

    def _copy(self) -> None:
        if self.bpm is not None:
            self.get_clipboard().set(f"{self.bpm:.1f}")
