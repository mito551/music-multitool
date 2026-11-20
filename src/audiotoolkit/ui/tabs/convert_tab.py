from __future__ import annotations

from .base import ToolTab, combo, combo_value, set_combo, spin, switch


class ConvertTab(ToolTab):
    kind = "convert"
    title = "Convert / Trim"

    def build(self, group) -> None:
        self.format = combo("Format", ["wav", "flac", "mp3", "alac", "m4a"])
        self.rate = combo("Sample rate", ["keep", "22050", "32000", "44100", "48000"])
        self.channels = combo("Channels", ["keep", "mono", "stereo"])
        self.loud = switch("Normalize loudness")
        self.lufs = spin("Target LUFS", -30, -5, 1, -14)
        self.trim = switch("Trim silence at start and end")
        self.start = spin("Start (s, 0 = beginning)", 0, 36000, 0.5, 0, 1)
        self.end = spin("End (s, 0 = end of file)", 0, 36000, 0.5, 0, 1)
        for row in (self.format, self.rate, self.channels, self.loud, self.lufs, self.trim, self.start, self.end):
            group.add(row)
        self.add_buttons()

    def get_opts(self) -> dict:
        opts: dict = {"format": combo_value(self.format)}
        if combo_value(self.rate) != "keep":
            opts["sample_rate"] = int(combo_value(self.rate))
        if combo_value(self.channels) != "keep":
            opts["channels"] = 1 if combo_value(self.channels) == "mono" else 2
        if self.loud.get_active():
            opts["loudnorm"] = int(self.lufs.get_value())
        if self.trim.get_active():
            opts["trim_silence"] = True
        if self.start.get_value() > 0:
            opts["start"] = self.start.get_value()
        if self.end.get_value() > 0:
            opts["end"] = self.end.get_value()
        return opts

    def set_opts(self, opts: dict) -> None:
        set_combo(self.format, opts.get("format", "wav"))
        set_combo(self.rate, opts.get("sample_rate", "keep"))
        set_combo(self.channels, {1: "mono", 2: "stereo"}.get(opts.get("channels"), "keep"))
        self.loud.set_active("loudnorm" in opts)
        self.lufs.set_value(opts.get("loudnorm", -14))
        self.trim.set_active(bool(opts.get("trim_silence")))
        self.start.set_value(opts.get("start") or 0)
        self.end.set_value(opts.get("end") or 0)
