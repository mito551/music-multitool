from __future__ import annotations

from .base import ToolTab, combo, combo_value, set_combo


class MidiTab(ToolTab):
    kind = "midi"
    title = "Transcribe"

    def build(self, group) -> None:
        self.device = combo("Device", ["auto", "cuda", "cpu"])
        group.add(self.device)
        self.add_buttons()

    def get_opts(self) -> dict:
        return {"device": combo_value(self.device)}

    def set_opts(self, opts: dict) -> None:
        set_combo(self.device, opts.get("device", "auto"))
