# PyInstaller: one windowed exe with the Qt UI. torch, demucs, ... are downloaded by the app on first use; the plain-Python
# package is also shipped as data because the worker (a separate Python) imports it.
import os
from pathlib import Path

ROOT = Path(SPECPATH).parent
SRC = ROOT / "src" / "musicmultitool"
SHIPPED = ["core", "worker", "presets"]  # what the worker and the presets need; the UIs are inside the exe proper

datas = [(str(SRC / "__init__.py"), "musicmultitool_src/musicmultitool"),
         (str(SRC / "music-multitool.png"), "musicmultitool")]  # the window icon, read by the Qt UI itself
for part in SHIPPED:
    for f in (SRC / part).rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts:
            datas.append((str(f), f"musicmultitool_src/musicmultitool/{f.parent.relative_to(SRC)}"))

UNUSED_QT = ["QtWebEngineCore", "QtWebEngineWidgets", "QtWebEngineQuick", "QtQuick", "QtQml", "QtQuickWidgets", "Qt3DCore",
             "QtMultimedia", "QtMultimediaWidgets", "QtPdf", "QtPdfWidgets", "QtCharts", "QtDataVisualization", "QtSql",
             "QtNetwork", "QtBluetooth", "QtSensors", "QtPositioning", "QtDesigner", "QtTest", "QtOpenGL", "QtSvg",
             "QtQuick3D", "QtGraphs", "QtRemoteObjects", "QtScxml", "QtSerialPort", "QtWebSockets", "QtHelp"]

a = Analysis([str(Path(SPECPATH) / "qt_entry.py")], pathex=[str(ROOT / "src")], datas=datas, hiddenimports=[],
             excludes=["gi", "tkinter", "numpy", "torch", *[f"PySide6.{m}" for m in UNUSED_QT]])
pyz = PYZ(a.pure)
icon = Path(SPECPATH) / "music-multitool.ico"
if os.environ.get("ATK_ONEDIR"):  # AppImage: the squashfs is mounted, so nothing needs unpacking on each start
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="MusicMultitool", console=False, upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="MusicMultitool")
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="MusicMultitool", console=False, upx=False,
              icon=str(icon) if icon.is_file() else None)
