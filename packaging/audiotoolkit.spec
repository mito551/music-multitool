# PyInstaller: one windowed exe with the Qt UI. torch, demucs, ... are downloaded by the app on first use; the plain-Python
# package is also shipped as data because the worker (a separate Python) imports it.
from pathlib import Path

ROOT = Path(SPECPATH).parent
SRC = ROOT / "src" / "audiotoolkit"
SHIPPED = ["core", "worker", "presets"]  # what the worker and the presets need; the UIs are inside the exe proper

datas = [(str(SRC / "__init__.py"), "audiotoolkit_src/audiotoolkit")]
for part in SHIPPED:
    for f in (SRC / part).rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts:
            datas.append((str(f), f"audiotoolkit_src/audiotoolkit/{f.parent.relative_to(SRC)}"))

UNUSED_QT = ["QtWebEngineCore", "QtWebEngineWidgets", "QtWebEngineQuick", "QtQuick", "QtQml", "QtQuickWidgets", "Qt3DCore",
             "QtMultimedia", "QtMultimediaWidgets", "QtPdf", "QtPdfWidgets", "QtCharts", "QtDataVisualization", "QtSql",
             "QtNetwork", "QtBluetooth", "QtSensors", "QtPositioning", "QtDesigner", "QtTest", "QtOpenGL", "QtSvg",
             "QtQuick3D", "QtGraphs", "QtRemoteObjects", "QtScxml", "QtSerialPort", "QtWebSockets", "QtHelp"]

a = Analysis([str(Path(SPECPATH) / "windows_entry.py")], pathex=[str(ROOT / "src")], datas=datas, hiddenimports=[],
             excludes=["gi", "tkinter", "numpy", "torch", *[f"PySide6.{m}" for m in UNUSED_QT]])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="AudioToolkit", console=False, upx=False,
          icon=str(Path(SPECPATH) / "audio-toolkit.ico") if (Path(SPECPATH) / "audio-toolkit.ico").is_file() else None)
