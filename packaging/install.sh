#!/usr/bin/env bash
# Idempotent: builds the worker venv, then installs the launcher entry and icon under ~/.local.
set -euo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$HOME/.pyenv/versions/3.12.13/bin/python}"
ID=local.audiotoolkit.AudioToolkit

[ -x "$APP/.venv/bin/python" ] || "$PYTHON" -m venv "$APP/.venv"
PIP="$APP/.venv/bin/pip"
$PIP install -q -U pip
$PIP install -q torch torchaudio faster-whisper librosa soundfile pytest nvidia-cublas-cu12 nvidia-cudnn-cu12
$PIP install -q -e "$APP/../demucs" -e "$APP/../dettato" -e "$APP/../copisteria" -e "$APP"
$PIP install -q "av>=14,<17"  # faster-whisper breaks on PyAV >= 17; last, so nothing above re-upgrades it

# copisteria's weights are not in its repository; one download per detector size
for repo in copista-28m copista-2m; do
  "$APP/.venv/bin/hf" download "kobimusic/$repo" --include "*.pt" --local-dir "$APP/../copisteria/models" >/dev/null
done
command -v pdftoppm >/dev/null || echo "PDF scores need poppler-utils. Run: sudo dnf install poppler-utils" >&2

if ! /usr/bin/python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1')" 2>/dev/null; then
  echo "GTK4/libadwaita for the system Python are missing. Run: sudo dnf install python3-gobject gtk4 libadwaita" >&2
  exit 1
fi

mkdir -p "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/scalable/apps"
sed "s|@APP@|$APP|g" "$APP/packaging/$ID.desktop" > "$HOME/.local/share/applications/$ID.desktop"
cp "$APP/packaging/audio-toolkit.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/audio-toolkit.svg"
command -v update-desktop-database >/dev/null && update-desktop-database "$HOME/.local/share/applications" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" || true
echo "Installed. Look for 'Audio Toolkit' in your app launcher."
