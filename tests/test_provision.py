import os
import sys

from audiotoolkit.core import provision


def test_remove_data_only_touches_app_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(provision, "data_dir", lambda: tmp_path / "AudioToolkit")
    monkeypatch.setattr(provision, "config_dir", lambda: tmp_path / "cfg" / "AudioToolkit")
    (tmp_path / "AudioToolkit" / "venv").mkdir(parents=True)
    (tmp_path / "AudioToolkit" / "venv" / "f").write_text("x")
    (tmp_path / "cfg" / "AudioToolkit").mkdir(parents=True)
    assert provision.data_size() == 1
    assert provision.remove_data() == [str(tmp_path / "AudioToolkit")]
    assert (tmp_path / "cfg" / "AudioToolkit").is_dir()  # settings kept by default
    assert provision.remove_data(include_settings=True) == [str(tmp_path / "cfg" / "AudioToolkit")]


def test_remove_data_refuses_other_folders(tmp_path, monkeypatch):
    (tmp_path / "Documents").mkdir()
    monkeypatch.setattr(provision, "data_dir", lambda: tmp_path / "Documents")
    assert provision.remove_data() == [] and (tmp_path / "Documents").is_dir()


def test_tool_path_reuses_path_then_downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(provision, "data_dir", lambda: tmp_path / "AudioToolkit")
    monkeypatch.setenv("PATH", str(tmp_path / "none"))
    assert provision.tool_path("ffmpeg") is None
    exe = tmp_path / "AudioToolkit" / "bin" / "ffmpeg" / "x" / "bin" / provision._exe("ffmpeg")
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    assert provision.tool_path("ffmpeg") == str(exe) and provision.tool_dirs() == [str(exe.parent)]
    other = tmp_path / "mine"
    other.mkdir()
    (other / provision._exe("ffmpeg")).write_text("")
    os.chmod(other / provision._exe("ffmpeg"), 0o755)
    assert provision.tool_path("ffmpeg", str(other)) == str(other / provision._exe("ffmpeg"))  # the user's own wins


def test_frozen_worker_src_is_copied_once_per_exe(tmp_path, monkeypatch):
    bundle = tmp_path / "meipass" / "audiotoolkit_src" / "audiotoolkit"
    bundle.mkdir(parents=True)
    (bundle / "m.py").write_text("v1")
    exe = tmp_path / "app.exe"
    exe.write_text("")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "meipass"), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(provision, "data_dir", lambda: tmp_path / "data")
    target = provision.worker_src()
    assert (target / "audiotoolkit" / "m.py").read_text() == "v1"
    (bundle / "m.py").write_text("v2")
    provision.worker_src()  # same exe: not copied again
    assert (target / "audiotoolkit" / "m.py").read_text() == "v1"
    os.utime(exe, ns=(1, 1))  # a new exe
    provision.worker_src()
    assert (target / "audiotoolkit" / "m.py").read_text() == "v2"
