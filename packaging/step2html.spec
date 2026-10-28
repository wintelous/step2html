# -*- mode: python -*-
# PyInstaller spec for the Step2HTML desktop app: a folder bundle on Linux, Step2HTML.app on macOS.
# Build via packaging/build_macos.sh or packaging/build_linux.sh (they render the icons first).
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ICONS = os.path.join(ROOT, "build", "icons")
with open(os.path.join(ROOT, "step2html.py"), encoding="utf-8") as f:
    VERSION = re.search(r'__version__ = "([^"]+)"', f.read()).group(1)

# cadquery-ocp pulls these in as dependencies, but the converter never loads them
EXCLUDES = ["vtk", "vtkmodules", "matplotlib", "numpy", "PIL", "tkinter", "contourpy", "kiwisolver",
            "fontTools", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtOpenGL"]
WIN = sys.platform == "win32"
ICON = os.path.join(ICONS, "step2html.icns" if sys.platform == "darwin" else
                    "step2html.ico" if WIN else "step2html.png")

a = Analysis(
    [os.path.join(ROOT, "step2html_gui.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "lib"), "lib")],
    hiddenimports=["step2html"],
    excludes=EXCLUDES,
    noarchive=False,
)
if sys.platform.startswith("linux"):
    # Use the system's font libraries: a bundled (older) fontconfig can't parse newer distros' configs.
    # cadquery-ocp keeps its own privately-named copies, which are unaffected.
    SYSTEM_LIBS = {"libfontconfig.so.1", "libfreetype.so.6"}
    a.binaries = [b for b in a.binaries if os.path.basename(b[0]) not in SYSTEM_LIBS]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Step2HTML" if (sys.platform == "darwin" or WIN) else "step2html-gui",
    console=False,
    strip=False,
    upx=False,
    icon=ICON,
)
extra = []
if WIN:
    # Windows: a windowed exe has no console, so the converter is a separate console program,
    # step2html-cli.exe, next to Step2HTML.exe (the app runs it hidden; it doubles as the CLI).
    # (Not "step2html.exe": Windows file names are case-insensitive, it would overwrite Step2HTML.exe.)
    b = Analysis([os.path.join(ROOT, "packaging", "step2html_cli.py")], pathex=[ROOT],
                 datas=[(os.path.join(ROOT, "lib"), "lib")], excludes=EXCLUDES + ["PySide6", "shiboken6"])
    exe_cli = EXE(PYZ(b.pure), b.scripts, [], exclude_binaries=True, name="step2html-cli", console=True,
                  strip=False, upx=False, icon=ICON)
    extra = [exe_cli, b.binaries, b.datas]
coll = COLLECT(exe, a.binaries, a.datas, *extra, strip=False, upx=False, name="Step2HTML")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Step2HTML.app",
        icon=os.path.join(ICONS, "step2html.icns"),
        bundle_identifier="app.step2html.desktop",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "Step2HTML",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,      # follow light/dark mode
            # lets you drop a STEP file on the app / Dock icon, or use "Open With"
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "STEP CAD model",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "CFBundleTypeExtensions": ["step", "stp", "STEP", "STP", "stpz", "p21"],
            }],
        },
    )
