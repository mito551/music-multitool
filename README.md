# Audio Toolkit

Batch-queue front end, in GTK4/libadwaita or Qt (PySide6), for stem separation (demucs), audio to MIDI (dettato), format
conversion (ffmpeg), lyrics (faster-whisper, optional SynthV note lyrics), sheet-music scanning (copisteria),
BPM/key detection, and chains of these.

The package contains only the UI and the worker code. torch, the three projects above and the audio libraries are
installed from inside the app.

## Install

Two interfaces share all the logic. `audio-toolkit` picks one: Qt on KDE, LXQt and similar desktops and on every
non-Linux system, GTK elsewhere. Override it with `--ui gtk|qt` or Settings → General → Interface. If the chosen
toolkit is missing, the other one is used.

System packages (Fedora; other distributions have equivalents):

    sudo dnf install ffmpeg poppler-utils
    sudo dnf install python3-gobject gtk4 libadwaita     # GTK interface
    sudo dnf install python3-pyside6                     # Qt interface (or: pip install audiotoolkit[qt])

Both need access to the system's Python packages, so install with:

    pipx install --system-site-packages audiotoolkit-0.1.0-py3-none-any.whl
    audio-toolkit --install-desktop      # launcher entry and icon under ~/.local/share

On Windows there is one file, `AudioToolkit.exe` (Qt interface only). Keep it anywhere; nothing is installed.
Settings and your chains live in `%APPDATA%\AudioToolkit`, everything downloaded in `%LOCALAPPDATA%\AudioToolkit`.
ffmpeg and poppler already on PATH are reused; otherwise they, uv and a Python 3.12 are downloaded there on first setup.
**Settings → Paths → Delete…** removes all of it again (optionally with your settings). Build it with the
`build` GitHub Actions workflow or `pyinstaller packaging/audiotoolkit.spec` on Windows.

On Linux there is also a single `AudioToolkit-x86_64.AppImage` (`chmod +x` and run). It uses the system's GTK interface
when `python3` has PyGObject, GTK4 and libadwaita 1.5 or newer, and the bundled Qt interface otherwise (also on KDE-like
desktops, or with `--ui qt`). The Qt part needs `libxcb-cursor0` (`xcb-util-cursor` on Fedora) on X11. Build it with
`packaging/appimage.sh` or the same `build` workflow.

## First run

Open **Settings → Repos**, enter for each tool a local checkout or a git URL (empty = that tool stays unavailable),
then press **Set up / update**. This builds `~/.local/share/audio-toolkit/venv` with torch, faster-whisper, librosa
and the repos (on Windows with an NVIDIA GPU, torch comes from PyTorch's CUDA index; without one it is the slower CPU build). URLs are cloned under `~/.local/share/audio-toolkit/repos`). **Settings → Models** downloads copisteria's
weights. **Settings → Paths** can point at another Python or extra PATH folders.

Settings live in `~/.config/audio-toolkit/settings.json`, your own chains in `~/.config/audio-toolkit/presets/`.

## Build a release

    packaging/build.sh        # dist/: wheel, sdist and audio-toolkit-<version>.tar.gz

## Develop

    python -m pytest          # fast tests; add -m slow for the real-model ones
    PYTHONPATH=src python3 -m audiotoolkit [--ui gtk|qt]
