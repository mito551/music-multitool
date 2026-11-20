from __future__ import annotations

from .base import ToolTab, combo, combo_value, set_combo, spin


class SeparateTab(ToolTab):
    kind = "separate"
    title = "Separate"
    icon = "view-dual-symbolic"

    def build(self, group) -> None:
        self.model = combo("Model", ["htdemucs", "htdemucs_ft", "htdemucs_6s", "mdx_extra"])
        self.shifts = spin("Shifts (higher = slower, slightly better)", 1, 5, 1, 1)
        self.stems = combo("Stems", ["all", "vocals", "drums", "bass", "other"])
        self.format = combo("Format", ["wav", "flac", "mp3"])
        for row in (self.model, self.shifts, self.stems, self.format):
            group.add(row)

    def get_opts(self) -> dict:
        return {"model": combo_value(self.model), "shifts": int(self.shifts.get_value()),
                "stems": combo_value(self.stems), "format": combo_value(self.format)}

    def set_opts(self, opts: dict) -> None:
        set_combo(self.model, opts.get("model", "htdemucs"))
        self.shifts.set_value(opts.get("shifts", 1))
        set_combo(self.stems, opts.get("stems", "all"))
        set_combo(self.format, opts.get("format", "wav"))
