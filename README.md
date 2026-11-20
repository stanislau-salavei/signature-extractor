# signature-extractor

«Извлечение подписи» / Signature Extractor 1.0 is a Windows program that turns a photo or scan of a signature into clean PNG, SVG and DXF files. License: GNU GPLv3.

- Run from source: `pip install -r requirements.txt`, `python main.py`.
- Tests: `pip install -r requirements-dev.txt`, `python -m pytest -q tests` (tests that need personal photos are skipped without them).
- Installer (Windows x64): `pip install -r requirements.txt -r packaging/requirements-build.txt -c packaging/constraints-win.txt` (exact build versions), install Inno Setup 6, `python packaging/build.py` → `dist/SignatureExtractor-<ver>-setup.exe` and `.sha256`. GitHub Actions does the same (`.github/workflows/build-installer.yml`).
