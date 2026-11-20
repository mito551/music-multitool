from __future__ import annotations

from .base import ToolTab, combo, combo_value, entry, set_combo


class LyricsTab(ToolTab):
    kind = "lyrics"
    title = "Lyrics"

    def build(self, group) -> None:
        self.size = combo("Model size", ["tiny", "base", "small", "medium", "large-v3"])
        self.language = entry("Language code (empty = auto)")
        self.device = combo("Device", ["auto", "cuda", "cpu"])
        for row in (self.size, self.language, self.device):
            group.add(row)
        self.add_buttons()

    def get_opts(self) -> dict:
        opts = {"model_size": combo_value(self.size), "device": combo_value(self.device)}
        if self.language.get_text().strip():
            opts["language"] = self.language.get_text().strip()
        return opts

    def set_opts(self, opts: dict) -> None:
        set_combo(self.size, opts.get("model_size", "medium"))
        self.language.set_text(opts.get("language") or "")
        set_combo(self.device, opts.get("device", "auto"))
