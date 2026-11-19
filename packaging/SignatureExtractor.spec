# -*- mode: python ; coding: utf-8 -*-
# Stage 6: PyInstaller onedir build of «Извлечение подписи / Signature Extractor» (Windows x64).
# Run through packaging/build.py (it writes build/version_info.txt first):
#     python packaging/build.py
# Result: dist/SignatureExtractor/SignatureExtractor.exe + _internal/ (assets, i18n, Python, libraries).
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
VERSION_FILE = ROOT / "build" / "version_info.txt"

datas = [
    (str(ROOT / "assets"), "assets"),            # icons, help pictures, app.ico
    (str(ROOT / "i18n"), "i18n"),                # strings_ru_en.csv
    (str(ROOT / "LICENSE"), "."),                # GNU GPLv3 next to the program files as well
]
datas += collect_data_files("customtkinter")     # themes (json) and fonts of CustomTkinter
datas += collect_data_files("ezdxf", excludes=["**/tests/**"])
# tkinterdnd2 brings its own PyInstaller hook (tkdnd DLL for the platform); pillow_heif — extension + libheif

hiddenimports = collect_submodules("pillow_heif") + ["tkinterdnd2", "darkdetect", "potrace",
                                                     "PIL.ImageTk", "PIL._tkinter_finder"]   # PhotoImage

excludes = [
    "pytest", "_pytest", "pluggy", "tests",
    "tkinter.test", "idlelib", "lib2to3", "pydoc_data",
    "matplotlib", "scipy", "pandas", "IPython", "PyQt5", "PySide2", "PySide6", "PyQt6",
    "onnxruntime", "torch",                       # no AI model in v1.0 (remark 78)
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SignatureExtractor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                                    # UPX raises antivirus false positives
    console=False,                                # windowed app
    disable_windowed_traceback=False,
    icon=str(ROOT / "assets" / "app.ico"),
    version=str(VERSION_FILE) if VERSION_FILE.exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SignatureExtractor",
)
