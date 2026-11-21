from __future__ import annotations

from .base import ToolTab, combo, combo_value, entry, set_combo


class ScoreTab(ToolTab):
    kind = "score"
    title = "Scan score"
    icon = "document-edit-symbolic"
    chainable = False  # takes images and PDFs, not audio

    def build(self, group) -> None:
        group.set_description("Reads scanned sheet music (images or PDFs) into MusicXML, one file per page.")
        self.detector = combo("Detector", ["28m", "2m"])
        self.device = combo("Device", ["auto", "cuda", "cpu"])
        self.pages = entry("PDF pages (all, 3, or 2-5)", "all")
        for row in (self.detector, self.device, self.pages):
            group.add(row)

    def get_opts(self) -> dict:
        return {"detector": combo_value(self.detector), "device": combo_value(self.device),
                "pages": self.pages.get_text().strip() or "all"}

    def set_opts(self, opts: dict) -> None:
        set_combo(self.detector, opts.get("detector", "28m"))
        set_combo(self.device, opts.get("device", "auto"))
        self.pages.set_text(opts.get("pages", "all"))
