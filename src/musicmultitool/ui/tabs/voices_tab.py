from __future__ import annotations

from .base import ToolTab, combo, combo_value, set_combo, spin

MODES = ["auto", "quantized", "performance"]


class VoicesTab(ToolTab):
    kind = "voices"
    title = "Voices"
    icon = "view-list-symbolic"
    chainable = False  # takes MIDI files, not audio

    def build(self, group) -> None:
        group.set_description("Splits a polyphonic MIDI file into melodic voices, one track each. Add .mid files.")
        self.count = spin("Voices", 1, 8, 1, 4)
        self.mode = combo("Timing", MODES)
        group.add(self.count)
        group.add(self.mode)

    def get_opts(self) -> dict:
        return {"voices": int(self.count.get_value()), "mode": combo_value(self.mode)}

    def set_opts(self, opts: dict) -> None:
        self.count.set_value(opts.get("voices", 4))
        set_combo(self.mode, opts.get("mode", "auto"))
