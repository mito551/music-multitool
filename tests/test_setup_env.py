from pathlib import Path

from audiotoolkit.core.settings import Settings
from audiotoolkit.core.setup_env import checkout_dir, local_checkout, plan, run_plan


def labels(steps):
    return [label for label, _ in steps]


def test_plan_without_repos_builds_env_and_installs_base(tmp_path):
    steps = plan(Settings(), "/usr/bin/python3", tmp_path / "venv", windows=False)
    assert labels(steps)[0] == "Creating the environment" and steps[0][1][:3] == ["/usr/bin/python3", "-m", "venv"]
    assert not any(label.startswith(("Installing demucs", "Cloning")) for label in labels(steps))
    assert labels(steps)[-1] == "Pinning PyAV"


def test_plan_skips_venv_when_it_exists(tmp_path):
    py = tmp_path / "venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.touch()
    assert "Creating the environment" not in labels(plan(Settings(), "x", tmp_path / "venv"))


def test_plan_installs_local_repo_editable_and_clones_urls(tmp_path):
    s = Settings(repos={"demucs": str(tmp_path / "d"), "dettato": "https://example.org/dettato.git", "copisteria": " "})
    steps = dict(plan(s, "x", tmp_path / "venv"))
    assert steps["Installing demucs"][-2:] == ["-e", str(tmp_path / "d")]
    assert steps["Cloning dettato"][:2] == ["git", "clone"] and steps["Cloning dettato"][-1] == str(checkout_dir("dettato"))
    assert steps["Installing dettato"][-1] == str(checkout_dir("dettato"))
    assert "Installing copisteria" not in steps


def test_local_checkout():
    assert local_checkout(Settings(), "demucs") is None
    assert local_checkout(Settings(repos={"demucs": "/x/d"}), "demucs") == Path("/x/d")
    assert local_checkout(Settings(repos={"demucs": "https://h/d.git"}), "demucs") == checkout_dir("demucs")


def test_run_plan_stops_at_first_failure():
    seen = []
    err = run_plan([("ok", ["true"]), ("bad", ["sh", "-c", "echo boom >&2; exit 3"]), ("never", ["true"])], seen.append)
    assert err == "bad: boom" and seen == ["ok", "bad"]
    assert run_plan([("ok", ["true"])], seen.append) is None


def test_windows_with_nvidia_gets_cuda_torch(tmp_path):
    steps = dict(plan(Settings(), "x", tmp_path / "v", windows=True, nvidia=True))
    assert "--index-url" in steps["Installing torch (CUDA)"] and "cu126" in steps["Installing torch (CUDA)"][-1]


def test_windows_without_nvidia_says_cpu(tmp_path):
    names = labels(plan(Settings(), "x", tmp_path / "v", windows=True, nvidia=False))
    assert any("CPU only" in n for n in names) and not any("(CUDA)" in n for n in names)


def test_linux_has_no_separate_torch_step(tmp_path):
    assert not any("torch (" in n for n in labels(plan(Settings(), "x", tmp_path / "v", windows=False, nvidia=True)))


def test_windows_plan_uses_uv_and_fetches_tools(tmp_path):
    steps = dict(plan(Settings(), "x", tmp_path / "v", windows=True, nvidia=True))
    assert {"Fetching uv", "Fetching ffmpeg", "Fetching poppler"} <= set(steps)
    assert all(callable(steps[k]) for k in ("Fetching uv", "Fetching ffmpeg"))
    create = steps["Creating the environment"]
    assert create[1:3] == ["venv", "--python"] and Path(create[0]).stem == "uv"
    assert steps["Installing torch (CUDA)"][1:3] == ["pip", "install"] and "Updating pip" not in steps


def test_run_plan_runs_callables_and_reports_their_errors():
    seen = []

    def boom():
        raise RuntimeError("no network")

    assert run_plan([("a", lambda: seen.append(1)), ("b", boom), ("c", lambda: seen.append(2))], lambda _l: None) \
        == "b: no network" and seen == [1]
