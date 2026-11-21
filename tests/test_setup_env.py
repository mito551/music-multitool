from pathlib import Path

from audiotoolkit.core.settings import Settings
from audiotoolkit.core.setup_env import checkout_dir, local_checkout, plan, run_plan


def labels(steps):
    return [label for label, _ in steps]


def test_plan_without_repos_builds_env_and_installs_base(tmp_path):
    steps = plan(Settings(), "/usr/bin/python3", tmp_path / "venv")
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
