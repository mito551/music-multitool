#!/usr/bin/env bash
# Builds dist/MusicMultitool-x86_64.AppImage. It holds the bundled Qt build and the app's plain-Python source; at start AppRun
# uses the system's GTK interface when python3 has GTK4 + libadwaita >= 1.5 (or the settings/--ui say Qt, or the desktop
# is KDE-like), otherwise the bundled Qt build. Build on an old distribution (CI: Ubuntu 22.04) so the Qt part runs on newer ones.
# Needs pyinstaller and PySide6 in the active Python.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ATK_ONEDIR=1 python3 -m PyInstaller --noconfirm --distpath dist --workpath build packaging/musicmultitool.spec

app=build/AppDir
mkdir -p "$app/usr/bin" "$app/usr/lib/python"
cp -r dist/MusicMultitool "$app/usr/bin/"
cp -r src/musicmultitool "$app/usr/lib/python/"
cp src/musicmultitool/music-multitool.svg "$app/music-multitool.svg"
cp src/musicmultitool/music-multitool.svg "$app/.DirIcon"
sed 's|@EXEC@|MusicMultitool|' src/musicmultitool/io.github.mito551.MusicMultitool.desktop > "$app/io.github.mito551.MusicMultitool.desktop"
cat > "$app/AppRun" <<'EOS'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
PYSRC="$HERE/usr/lib/python${PYTHONPATH:+:$PYTHONPATH}"
ui=$(PYTHONPATH="$PYSRC" python3 -m musicmultitool --which-ui "$@" 2>/dev/null) || ui=qt
if [ "$ui" = gtk ]; then
  PYTHONPATH="$PYSRC" exec python3 -m musicmultitool --ui gtk "$@"
fi
exec "$HERE/usr/bin/MusicMultitool/MusicMultitool" "$@"
EOS
chmod +x "$app/AppRun"

tool=build/appimagetool
[ -x "$tool" ] || { curl -fsSL -o "$tool" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage; chmod +x "$tool"; }
ARCH=x86_64 "$tool" --appimage-extract-and-run "$app" dist/MusicMultitool-x86_64.AppImage
ls -lh dist/MusicMultitool-x86_64.AppImage
