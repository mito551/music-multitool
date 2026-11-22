import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from musicmultitool.qt.tabs import TABS  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("kind,opts", [
    ("convert", {"format": "flac", "sample_rate": 44100, "channels": 2, "loudnorm": -16, "trim_silence": True, "start": 1.5}),
    ("separate", {"model": "htdemucs_ft", "shifts": 2, "stems": "vocals", "format": "mp3"}),
    ("midi", {"device": "cpu"}),
    ("lyrics", {"model_size": "small", "device": "cpu", "language": "en", "synthv": True, "midi": "/x/a.mid"}),
    ("score", {"detector": "2m", "device": "cuda", "pages": "2-5"}),
    ("voices", {"voices": 3, "mode": "performance"}),
])
def test_tab_opts_roundtrip(app, kind, opts):
    tab = TABS[kind]()
    tab.set_opts(opts)
    assert tab.get_opts() == opts


def test_hidden_and_chainable_flags(app):
    assert TABS["analyze"].hidden and not TABS["score"].chainable and TABS["convert"].chainable


def test_window_builds_and_blocks_unsaved_chain(app, tmp_path, monkeypatch):
    from musicmultitool.core.settings import Settings
    from musicmultitool.qt.window import MainWindow
    monkeypatch.setenv("HOME", str(tmp_path))
    win = MainWindow(Settings(out_root=str(tmp_path)))
    assert win.sidebar.list.count() == 8  # seven tools incl. chains + settings, analyze hidden
    assert win.chains.status.text() == "Ready"
    win.close()
