"""The tool tabs (Qt twin of ui/tabs/*). TABS maps a job kind to its form."""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget

from musicmultitool.core.tools import DEVICES

from .rows import ToolTab, combo, set_combo, spin


class ConvertTab(ToolTab):
    kind, title, icon_name = "convert", "Convert / Trim", "view-refresh-symbolic"

    def build(self) -> None:
        self.format = self.row("Format", combo(["wav", "flac", "mp3", "alac", "m4a"]))
        self.rate = self.row("Sample rate", combo(["keep", "22050", "32000", "44100", "48000"]))
        self.channels = self.row("Channels", combo(["keep", "mono", "stereo"]))
        self.loud = self.row("", QCheckBox("Normalize loudness"))
        self.lufs = self.row("Target LUFS", spin(-30, -5, 1, -14))
        self.trim = self.row("", QCheckBox("Trim silence at start and end"))
        self.start = self.row("Start (s, 0 = beginning)", spin(0, 36000, 0.5, 0, 1))
        self.end = self.row("End (s, 0 = end of file)", spin(0, 36000, 0.5, 0, 1))

    def get_opts(self) -> dict:
        opts: dict = {"format": self.format.currentText()}
        if self.rate.currentText() != "keep":
            opts["sample_rate"] = int(self.rate.currentText())
        if self.channels.currentText() != "keep":
            opts["channels"] = 1 if self.channels.currentText() == "mono" else 2
        if self.loud.isChecked():
            opts["loudnorm"] = int(self.lufs.value())
        if self.trim.isChecked():
            opts["trim_silence"] = True
        if self.start.value() > 0:
            opts["start"] = self.start.value()
        if self.end.value() > 0:
            opts["end"] = self.end.value()
        return opts

    def set_opts(self, opts: dict) -> None:
        set_combo(self.format, opts.get("format", "wav"))
        set_combo(self.rate, opts.get("sample_rate", "keep"))
        set_combo(self.channels, {1: "mono", 2: "stereo"}.get(opts.get("channels"), "keep"))
        self.loud.setChecked("loudnorm" in opts)
        self.lufs.setValue(opts.get("loudnorm", -14))
        self.trim.setChecked(bool(opts.get("trim_silence")))
        self.start.setValue(opts.get("start") or 0)
        self.end.setValue(opts.get("end") or 0)


class SeparateTab(ToolTab):
    kind, title, icon_name = "separate", "Separate", "view-dual-symbolic"

    def build(self) -> None:
        self.model = self.row("Model", combo(["htdemucs", "htdemucs_ft", "htdemucs_6s", "mdx_extra"]))
        self.shifts = self.row("Shifts (higher = slower, slightly better)", spin(1, 5, 1, 1))
        self.stems = self.row("Stems", combo(["all", "vocals", "drums", "bass", "other"]))
        self.format = self.row("Format", combo(["wav", "flac", "mp3"]))

    def get_opts(self) -> dict:
        return {"model": self.model.currentText(), "shifts": int(self.shifts.value()),
                "stems": self.stems.currentText(), "format": self.format.currentText()}

    def set_opts(self, opts: dict) -> None:
        set_combo(self.model, opts.get("model", "htdemucs"))
        self.shifts.setValue(opts.get("shifts", 1))
        set_combo(self.stems, opts.get("stems", "all"))
        set_combo(self.format, opts.get("format", "wav"))


class MidiTab(ToolTab):
    kind, title, icon_name = "midi", "Transcribe", "audio-x-generic-symbolic"

    def build(self) -> None:
        self.device = self.row("Device", combo(DEVICES))

    def get_opts(self) -> dict:
        return {"device": self.device.currentText()}

    def set_opts(self, opts: dict) -> None:
        set_combo(self.device, opts.get("device", "auto"))


class AnalyzeTab(ToolTab):
    kind, title, icon_name = "analyze", "Analyze", "view-continuous-symbolic"
    has_opts, hidden = False, True

    def build(self) -> None:
        self.describe("Detects tempo (BPM) and musical key. Key is a best guess; BPM may read half or double.")

    def get_opts(self) -> dict:
        return {}

    def set_opts(self, opts: dict) -> None:
        pass


class LyricsTab(ToolTab):
    kind, title, icon_name = "lyrics", "Lyrics", "format-justify-left-symbolic"

    def build(self) -> None:
        self.size = self.row("Model size", combo(["tiny", "base", "small", "medium", "large-v3"]))
        self.language = self.row("Language code (empty = auto)", QLineEdit())
        self.device = self.row("Device", combo(DEVICES))
        self.synthv = self.row("", QCheckBox("SynthV lyrics (words on MIDI notes)"))
        self.midi = QLineEdit(placeholderText="empty = this song's own")
        pick = QPushButton("Choose…")
        pick.clicked.connect(self._pick_midi)
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.midi)
        lay.addWidget(pick)
        self.row("MIDI file", box)
        self.describe("Drop a .synthv.txt (with the original .txt beside it) to turn SynthV lyrics back into text.")

    def _pick_midi(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose MIDI", "", "MIDI (*.mid *.midi)")
        if path:
            self.midi.setText(path)

    def get_opts(self) -> dict:
        opts = {"model_size": self.size.currentText(), "device": self.device.currentText()}
        if self.synthv.isChecked():
            opts["synthv"] = True
            if self.midi.text().strip():
                opts["midi"] = self.midi.text().strip()
        if self.language.text().strip():
            opts["language"] = self.language.text().strip()
        return opts

    def set_opts(self, opts: dict) -> None:
        set_combo(self.size, opts.get("model_size", "medium"))
        self.language.setText(opts.get("language") or "")
        set_combo(self.device, opts.get("device", "auto"))
        self.synthv.setChecked(bool(opts.get("synthv")))
        self.midi.setText(opts.get("midi") or "")


class ScoreTab(ToolTab):
    kind, title, icon_name = "score", "Scan score", "document-edit-symbolic"
    chainable = False  # takes images and PDFs, not audio

    def build(self) -> None:
        self.describe("Reads scanned sheet music (images or PDFs) into MusicXML, one file per page.")
        self.detector = self.row("Detector", combo(["28m", "2m"]))
        self.device = self.row("Device", combo(DEVICES))
        self.pages = self.row("PDF pages (all, 3, or 2-5)", QLineEdit("all"))

    def get_opts(self) -> dict:
        return {"detector": self.detector.currentText(), "device": self.device.currentText(),
                "pages": self.pages.text().strip() or "all"}

    def set_opts(self, opts: dict) -> None:
        set_combo(self.detector, opts.get("detector", "28m"))
        set_combo(self.device, opts.get("device", "auto"))
        self.pages.setText(opts.get("pages", "all"))


TABS: dict[str, type[ToolTab]] = {t.kind: t for t in (ConvertTab, SeparateTab, MidiTab, AnalyzeTab, LyricsTab, ScoreTab)}
