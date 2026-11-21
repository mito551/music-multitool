# Audio Toolkit

GTK4/libadwaita front end with a batch queue for: stem separation (demucs), audio to MIDI (dettato), format
conversion (ffmpeg), lyrics (faster-whisper, optional SynthV note lyrics), sheet-music scanning (copisteria),
BPM/key detection, and chains of these.

The package contains only the UI and the worker code. torch, the three projects above and the audio libraries are
installed from inside the app.

## Install

System packages (Fedora; other distributions have equivalents):

    sudo dnf install python3-gobject gtk4 libadwaita ffmpeg poppler-utils

The app needs the system's GTK bindings, so install it with access to them:

    pipx install --system-site-packages audiotoolkit-0.1.0-py3-none-any.whl
    audio-toolkit --install-desktop      # launcher entry and icon under ~/.local/share

## First run

Open **Settings → Repos**, enter for each tool a local checkout or a git URL (empty = that tool stays unavailable),
then press **Set up / update**. This builds `~/.local/share/audio-toolkit/venv` with torch, faster-whisper, librosa
and the repos (URLs are cloned under `~/.local/share/audio-toolkit/repos`). **Settings → Models** downloads copisteria's
weights. **Settings → Paths** can point at another Python or extra PATH folders.

Settings live in `~/.config/audio-toolkit/settings.json`, your own chains in `~/.config/audio-toolkit/presets/`.

## Build a release

    packaging/build.sh        # dist/: wheel, sdist and audio-toolkit-<version>.tar.gz

## Develop

    python -m pytest          # fast tests; add -m slow for the real-model ones
    PYTHONPATH=src python3 -m audiotoolkit.ui
