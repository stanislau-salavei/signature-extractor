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
# remark 104: no C/Cython sources and type stubs of ezdxf (≈ 8.8 MB), only its resources
datas += collect_data_files("ezdxf", excludes=["**/tests/**", "**/*.c", "**/*.pyx", "**/*.pxd", "**/*.pyi", "**/*.h"])
# tkinterdnd2 brings its own PyInstaller hook (tkdnd DLL for the platform); pi_heif — extension + libheif (decoder only, remark 99)

hiddenimports = collect_submodules("pi_heif") + ["tkinterdnd2", "darkdetect", "potrace",
                                                     "PIL.ImageTk", "PIL._tkinter_finder"]   # PhotoImage

excludes = [
    "pytest", "_pytest", "pluggy", "tests",
    "tkinter.test", "idlelib", "lib2to3", "pydoc_data",
    "matplotlib", "scipy", "pandas", "IPython", "PyQt5", "PySide2", "PySide6", "PyQt6",
    "onnxruntime", "torch",                       # large optional libraries, never bundled
    "PIL.AvifImagePlugin", "PIL._avif",           # remark 105: AVIF is not a supported format (≈ 7.9 MB)
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
# remark 98: the cv2 hook adds the video-input DLL (opencv_videoio_ffmpeg*.dll, ≈ 41 MB); the program reads
# no video (imdecode / imencode do not use it)
a.binaries = [b for b in a.binaries if "opencv_videoio_ffmpeg" not in b[0].lower()]
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
