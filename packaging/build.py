"""Stage 6: build the Windows installer (PyInstaller onedir + Inno Setup 6) and its SHA-256.

    python packaging/build.py                     # version from core/version.py
    python packaging/build.py --version 1.0.1     # test build of another version (rewrites core/version.py!)
    python packaging/build.py --skip-inno         # only dist/SignatureExtractor/

Result (Windows x64):
    dist/SignatureExtractor/                       onedir: SignatureExtractor.exe + _internal/
    dist/SignatureExtractor-<ver>-setup.exe        per-user installer
    dist/SignatureExtractor-<ver>-setup.exe.sha256 «<sha256>  SignatureExtractor-<ver>-setup.exe»
The .sha256 file and the line «SHA-256: …» of the release notes are what the update check of the app
compares with the downloaded installer (core/updater.expected_sha256).  The GitHub Actions workflow
.github/workflows/build-installer.yml runs exactly this script."""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PY = ROOT / "core" / "version.py"
SPEC = ROOT / "packaging" / "SignatureExtractor.spec"
ISS = ROOT / "packaging" / "installer.iss"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
VERSION_RE = re.compile(r'^VERSION\s*=\s*"([^"]+)"', re.M)
VALID_VERSION = re.compile(r"^\d+(\.\d+){1,3}$")


def read_version(path: Path = VERSION_PY) -> str:
    m = VERSION_RE.search(path.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"no VERSION in {path}")
    return m.group(1)


def write_version(version: str, path: Path = VERSION_PY) -> None:
    if not VALID_VERSION.match(version):
        raise SystemExit(f"bad version {version!r} (expected 1.0, 1.0.1, 1.1 …)")
    text = path.read_text(encoding="utf-8")
    path.write_text(VERSION_RE.sub(f'VERSION = "{version}"', text, count=1), encoding="utf-8")


def num_version(version: str) -> tuple:
    """«1.0» → (1, 0, 0, 0) for the Windows version resources."""
    parts = [int(p) for p in version.split(".")][:4]
    return tuple(parts + [0] * (4 - len(parts)))


def installer_name(version: str) -> str:
    return f"SignatureExtractor-{version}-setup.exe"


def version_info_text(version: str) -> str:
    """PyInstaller version resource of SignatureExtractor.exe (File Explorer › Properties › Details)."""
    nv = num_version(version)
    dotted = ".".join(map(str, nv))
    strings = [("CompanyName", "Stanislau Salavei"),
               ("FileDescription", "Signature Extractor"),
               ("FileVersion", dotted),
               ("InternalName", "SignatureExtractor"),
               ("LegalCopyright", "© 2026 Stanislau Salavei. GNU GPLv3"),
               ("OriginalFilename", "SignatureExtractor.exe"),
               ("ProductName", "Signature Extractor"),
               ("ProductVersion", version)]
    body = ",\n            ".join(f"StringStruct({k!r}, {v!r})" for k, v in strings)
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers={nv}, prodvers={nv}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
            {body}])]),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200, 0x0419, 1200])])
  ]
)
"""


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha_line(digest: str, name: str) -> str:
    """Same format as ``sha256sum`` (read by core/updater.sha_from_text)."""
    return f"{digest}  {name}\n"


def find_iscc(explicit: str = None) -> str:
    cands = [explicit, os.environ.get("ISCC"), shutil.which("iscc"), shutil.which("ISCC"),
             r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe",
             str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe")]
    for c in cands:
        if c and Path(c).exists():
            return str(c)
    raise SystemExit("ISCC.exe (Inno Setup 6) not found; install it or pass --iscc")


def dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def run(cmd) -> None:
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", help="build another version (test builds; rewrites core/version.py)")
    ap.add_argument("--skip-pyinstaller", action="store_true")
    ap.add_argument("--skip-inno", action="store_true")
    ap.add_argument("--iscc")
    a = ap.parse_args(argv)
    if a.version:
        write_version(a.version)
    version = read_version()
    BUILD.mkdir(exist_ok=True)
    (BUILD / "version_info.txt").write_text(version_info_text(version), encoding="utf-8")
    if not a.skip_pyinstaller:
        run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
             "--distpath", DIST, "--workpath", BUILD / "pyinstaller", SPEC])
        onedir = DIST / "SignatureExtractor"
        print(f"onedir: {onedir}  {dir_size(onedir) / 1e6:.1f} MB", flush=True)
    if a.skip_inno:
        return 0
    run([find_iscc(a.iscc), f"/DAppVersion={version}", f"/DAppNumVersion={'.'.join(map(str, num_version(version)))}",
         ISS])
    setup = DIST / installer_name(version)
    digest = sha256_of(setup)
    (DIST / (setup.name + ".sha256")).write_text(sha_line(digest, setup.name), encoding="utf-8", newline="\n")
    print(f"installer: {setup}  {setup.stat().st_size / 1e6:.1f} MB\nSHA-256: {digest}", flush=True)
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"version={version}\ninstaller={setup.name}\nsha256={digest}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
