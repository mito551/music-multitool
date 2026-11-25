import pytest

from musicmultitool.launch import choose, preferred


def test_preferred_by_desktop():
    assert preferred("linux", {"XDG_CURRENT_DESKTOP": "KDE"}) == "qt"
    assert preferred("linux", {"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}) == "gtk"
    assert preferred("linux", {"XDG_CURRENT_DESKTOP": "X-Cinnamon"}) == "gtk"
    assert preferred("linux", {}) == "gtk"


def test_not_linux_is_qt():
    assert preferred("win32", {}) == "qt" and preferred("darwin", {}) == "qt"


def test_setting_and_flag_override():
    kde = {"XDG_CURRENT_DESKTOP": "KDE"}
    both = lambda _t: True  # noqa: E731
    assert choose([], "gtk", "linux", kde, both) == ("gtk", "")
    assert choose(["x", "--ui", "gtk"], "auto", "linux", kde, both) == ("gtk", "")
    assert choose(["x", "--ui=qt"], "auto", "linux", {}, both) == ("qt", "")


def test_missing_toolkit_falls_back_with_note():
    toolkit, note = choose([], "auto", "linux", {"XDG_CURRENT_DESKTOP": "KDE"}, lambda t: t == "gtk")
    assert toolkit == "gtk" and "QT" in note


def test_none_installed_exits():
    with pytest.raises(SystemExit):
        choose([], "auto", "linux", {}, lambda _t: False)
