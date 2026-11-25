"""`music-multitool`: picks the toolkit (Qt on KDE-like desktops and anywhere but Linux, GTK elsewhere) and starts it."""
from __future__ import annotations

import os
import sys

QT_DESKTOPS = {"kde", "lxqt", "razor", "lxde", "trinity", "cutefish", "deepin"}


def desktops(env=None) -> set[str]:
    env = os.environ if env is None else env
    return {d.lower() for d in env.get("XDG_CURRENT_DESKTOP", "").split(":") if d}


def preferred(platform: str = sys.platform, env=None, setting: str = "auto") -> str:
    if setting in ("gtk", "qt"):
        return setting
    if not platform.startswith("linux"):
        return "qt"
    return "qt" if desktops(env) & QT_DESKTOPS else "gtk"


def available(toolkit: str) -> bool:
    if toolkit == "qt":
        import importlib.util

        return importlib.util.find_spec("PySide6") is not None
    try:  # the GTK interface uses Adw.Dialog and friends, which need libadwaita 1.5
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw

        return (Adw.get_major_version(), Adw.get_minor_version()) >= (1, 5)
    except (ImportError, ValueError):
        return False


def choose(argv: list[str], setting: str = "auto", platform: str = sys.platform, env=None,
           have=available) -> tuple[str, str]:
    """(toolkit, note). `--ui gtk|qt` beats the setting; a missing toolkit falls back to the other one."""
    want = next((a.split("=", 1)[1] for a in argv if a.startswith("--ui=")), None)
    if want is None and "--ui" in argv and argv.index("--ui") + 1 < len(argv):
        want = argv[argv.index("--ui") + 1]
    first = preferred(platform, env, want if want in ("gtk", "qt") else setting)
    other = "gtk" if first == "qt" else "qt"
    if have(first):
        return first, ""
    if have(other):
        return other, f"{first.upper()} is not installed, using {other.upper()}."
    raise SystemExit("Neither PySide6 (Qt) nor PyGObject (GTK4) is installed.")


def _strip_ui(argv: list[str]) -> list[str]:
    out, skip = [], False
    for i, a in enumerate(argv):
        if skip:
            skip = False
        elif a == "--ui":
            skip = True
        elif not a.startswith("--ui="):
            out.append(a)
    return out


def main() -> None:
    if "--install-desktop" in sys.argv:
        from .desktop import install

        print("Installed", install())
        return
    from .core.settings import load_settings

    if "--which-ui" in sys.argv:  # for the AppImage's AppRun: the Qt build is bundled, GTK must come from the system
        print(choose(sys.argv, load_settings().frontend, have=lambda t: t == "qt" or available(t))[0])
        return
    toolkit, note = choose(sys.argv, load_settings().frontend)
    if note:
        print(note, file=sys.stderr)
    argv = _strip_ui(sys.argv)
    if toolkit == "qt":
        from .qt.app import main as run
    else:
        from .ui.app import main as run
    sys.exit(run(argv))
