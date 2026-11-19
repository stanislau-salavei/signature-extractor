# signature-extractor

«Извлечение подписи» / Signature Extractor 1.0 — Windows-программа, которая из фото или скана подписи делает чистые PNG, SVG и DXF. Лицензия GNU GPLv3.

- Запуск из исходников: `pip install -r requirements.txt`, `python main.py`.
- Тесты: `python -m pytest -q tests` (тесты с личными фото без них пропускаются).
- Установщик (Windows x64): `pip install -r requirements.txt -r packaging/requirements-build.txt`, установить Inno Setup 6, `python packaging/build.py` → `dist/SignatureExtractor-<ver>-setup.exe` и `.sha256`. То же делает GitHub Actions (`.github/workflows/build-installer.yml`).
