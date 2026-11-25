from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from .base import ToolTab, combo, combo_value, entry, set_combo, switch


class LyricsTab(ToolTab):
    kind = "lyrics"
    title = "Lyrics"
    icon = "format-justify-left-symbolic"

    def build(self, group) -> None:
        self.size = combo("Model size", ["tiny", "base", "small", "medium", "large-v3"])
        self.language = entry("Language code (empty = auto)")
        self.device = combo("Device", ["auto", "cuda", "cpu"])
        self.synthv = switch("SynthV lyrics (words on MIDI notes)")
        self.midi = entry("MIDI file (empty = this song's own)")
        pick = Gtk.Button(icon_name="document-open-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Choose MIDI…")
        pick.connect("clicked", self._pick_midi)
        self.midi.add_suffix(pick)
        for row in (self.size, self.language, self.device, self.synthv, self.midi):
            group.add(row)
        group.set_description("Drop a .synthv.txt (with the original .txt beside it) to turn SynthV lyrics back into text.")

    def _pick_midi(self, *_) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_default_filter(filt := Gtk.FileFilter(name="MIDI"))
        filt.add_pattern("*.mid")
        filt.add_pattern("*.midi")

        def done(d, result):
            try:
                self.midi.set_text(d.open_finish(result).get_path())
            except GLib.Error:
                pass

        dialog.open(self.get_root(), None, done)

    def get_opts(self) -> dict:
        opts = {"model_size": combo_value(self.size), "device": combo_value(self.device)}
        if self.synthv.get_active():
            opts["synthv"] = True
            if self.midi.get_text().strip():
                opts["midi"] = self.midi.get_text().strip()
        if self.language.get_text().strip():
            opts["language"] = self.language.get_text().strip()
        return opts

    def set_opts(self, opts: dict) -> None:
        set_combo(self.size, opts.get("model_size", "medium"))
        self.language.set_text(opts.get("language") or "")
        set_combo(self.device, opts.get("device", "auto"))
        self.synthv.set_active(bool(opts.get("synthv")))
        self.midi.set_text(opts.get("midi") or "")
