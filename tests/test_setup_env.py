from pathlib import Path

from musicmultitool.core import components, provision
from musicmultitool.core.settings import Settings
from musicmultitool.core.setup_env import checkout_dir, local_checkout, plan, run_plan

REPOS = {"demucs": "/r/demucs", "dettato": "/r/dettato", "copisteria": "/r/copisteria"}


def labels(steps):
    return [label for label, _ in steps]


def make(tmp_path, ids=None, repos=REPOS, **kw):
    kw.setdefault("windows", False)
    kw.setdefault("nvidia", True)
    return plan(Settings(repos=dict(repos)), ids, "/usr/bin/python3", tmp_path / "venv", **kw)


def test_nothing_chosen_means_nothing_happens(tmp_path):
    assert make(tmp_path, []) == []


def test_only_the_chosen_components_are_installed(tmp_path):
    steps = make(tmp_path, ["analyze"], repos={})
    assert labels(steps) == ["Creating the environment", "Updating pip", "Installing libraries", "Recording what is installed"]
    assert dict(steps)["Installing libraries"][-2:] == ["librosa", "soundfile"]  # no torch, no repos, no whisper


def test_torch_only_when_a_component_needs_it(tmp_path):
    assert not any("PyTorch" in n for n in labels(make(tmp_path, ["convert", "analyze", "lyrics"])))
    steps = dict(make(tmp_path, ["midi"]))
    assert "Installing PyTorch (CUDA)" in steps and "Installing dettato" in steps and "Installing demucs" not in steps


def test_cpu_choice_uses_the_cpu_index(tmp_path):
    steps = dict(plan(Settings(repos=REPOS, use_gpu=False), ["separate"], "x", tmp_path / "v", windows=False, nvidia=True))
    assert steps["Installing PyTorch (CPU only)"][-1].endswith("/whl/cpu")
    steps = dict(make(tmp_path, ["separate"], nvidia=False))
    assert "Installing PyTorch (CPU only)" in steps


def test_cuda_libraries_for_lyrics_only_with_gpu(tmp_path):
    with_gpu = dict(make(tmp_path, ["lyrics"]))["Installing libraries"]
    assert any("nvidia-cublas" in p for p in with_gpu) and "faster-whisper" in with_gpu
    cpu = dict(make(tmp_path, ["lyrics"], nvidia=False))["Installing libraries"]
    assert not any("nvidia" in p for p in cpu)
    assert labels(make(tmp_path, ["lyrics"]))[-2] == "Pinning PyAV"


def test_missing_repo_stops_before_any_download(tmp_path):
    steps = make(tmp_path, ["separate", "score"], repos={"demucs": "/x"})
    assert len(steps) == 1 and "copisteria" in steps[0][0]
    assert run_plan(steps, lambda _l: None) == f"{steps[0][0]}: repo not set"


def test_plan_skips_venv_when_it_exists(tmp_path):
    py = tmp_path / "venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.touch()
    assert "Creating the environment" not in labels(make(tmp_path, ["analyze"]))


def test_local_repo_editable_and_url_cloned(tmp_path):
    s = Settings(repos={"demucs": str(tmp_path / "d"), "dettato": "https://example.org/dettato.git"})
    steps = dict(plan(s, ["separate", "midi"], "x", tmp_path / "venv", windows=False, nvidia=True))
    assert steps["Installing demucs"][-2:] == ["-e", str(tmp_path / "d")]
    assert steps["Cloning dettato"][:2] == ["git", "clone"] and steps["Cloning dettato"][-1] == str(checkout_dir("dettato"))
    assert steps["Installing dettato"][-1] == str(checkout_dir("dettato"))


def test_local_checkout():
    assert local_checkout(Settings(), "demucs") is None
    assert local_checkout(Settings(repos={"demucs": "/x/d"}), "demucs") == Path("/x/d")
    assert local_checkout(Settings(repos={"demucs": "https://h/d.git"}), "demucs") == checkout_dir("demucs")


def test_windows_cuda_and_cpu(tmp_path):
    cuda = dict(make(tmp_path, ["separate"], windows=True))
    assert "--index-url" in cuda["Installing PyTorch (CUDA)"] and "cu126" in cuda["Installing PyTorch (CUDA)"][-1]
    assert not any("PyTorch (CUDA)" in n for n in labels(make(tmp_path, ["separate"], windows=True, nvidia=False)))


def test_windows_plan_uses_uv_and_fetches_tools(tmp_path):
    steps = dict(make(tmp_path, ["separate", "score"], windows=True))
    assert {"Fetching uv", "Fetching ffmpeg", "Fetching poppler"} <= set(steps)
    assert all(callable(steps[k]) for k in ("Fetching uv", "Fetching ffmpeg"))
    create = steps["Creating the environment"]
    assert create[1:3] == ["venv", "--python"] and Path(create[0]).stem == "uv"
    assert "Updating pip" not in steps
    assert "Fetching poppler" not in dict(make(tmp_path, ["separate"], windows=True))  # only the score scan needs it


def test_frozen_linux_uses_uv_without_windows_tools(tmp_path, monkeypatch):
    monkeypatch.setattr(provision, "frozen", lambda: True)
    steps = dict(make(tmp_path, ["separate"]))
    assert "Fetching uv" in steps and "Fetching ffmpeg" not in steps and "Updating pip" not in steps


def test_recording_what_is_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(components, "data_dir", lambda: tmp_path)
    assert components.installed() == []
    components.mark_installed(["analyze"])
    components.mark_installed(["lyrics"])
    assert components.installed() == ["analyze", "lyrics"]


def test_estimates_count_torch_once_and_follow_the_gpu_choice():
    assert components.estimate_mb(["convert"], gpu=True, windows=False) == 20
    both = components.estimate_mb(["separate", "midi"], gpu=False, windows=False)
    assert both == 120 + 250 + components.TORCH_MB["cpu"]
    assert components.estimate_mb(["lyrics"], True, False) == 250 + components.CUDA_LIBS_MB
    assert components.estimate_mb(["convert"], False, True) == 20 + components.FFMPEG_MB_WINDOWS
    assert components.human(6500) == "6.5 GB" and components.human(120) == "120 MB"


def test_run_plan_stops_at_first_failure():
    seen = []
    err = run_plan([("ok", ["true"]), ("bad", ["sh", "-c", "echo boom >&2; exit 3"]), ("never", ["true"])], seen.append)
    assert err == "bad: boom" and seen == ["ok", "bad"]
    assert run_plan([("ok", ["true"])], seen.append) is None


def test_run_plan_runs_callables_and_reports_their_errors():
    seen = []

    def boom():
        raise RuntimeError("no network")

    assert run_plan([("a", lambda: seen.append(1)), ("b", boom), ("c", lambda: seen.append(2))], lambda _l: None) \
        == "b: no network" and seen == [1]
