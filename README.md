# Signature Extractor

Windows desktop app that turns a photo or scan of a signature into PNG, SVG, and DXF files.

Version **1.0**. License: **GNU GPLv3** (see `LICENSE`). The supported platform is **Windows 10 version 1809, 64-bit**, and newer. 32-bit Windows is not supported.

This repository currently contains **stage 1**: the window shell, navigation, light and dark themes, Russian and English strings, and the settings file. Opening a photo does not process it yet.

## Run on Windows

From the project folder:

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m signature_extractor
```

The window opens at 1280×800 and will not shrink below 1024×680. The title follows the interface language («Извлечение подписи» or Signature Extractor) and does not include the version number.

Settings are stored in `%APPDATA%\Signature Extractor\settings.json`. The file is written by saving a temporary file in that folder and then replacing the real file, so a crash mid-write does not leave a half-written document. Installing or removing the app (stage 6) does not touch this file.

### First-launch language

On the first start, when `settings.json` does not exist yet, the interface language can come from the installer (stage 6). The app looks for it in this order:

1. `--installer-language ru` or `--installer-language en`
2. The environment variable `SIGNATURE_EXTRACTOR_INSTALLER_LANGUAGE` (`ru`, `en`, `russian`, or `english`)
3. A text file `installer_language.txt` next to the program (one of those same tokens)

If none of those is set, the language mode is «Использовать язык системы» / Use system language. Russian Windows uses Russian; any other language uses English, because those are the only two catalogs. After that, the language and the theme are changed in Settings and remembered.

## Tests

```bat
python -m unittest discover -s tests
```

The tests do not open a window. They check the settings file and the string table.

## Project layout

- `signature_extractor/i18n/` — loads `strings_ru_en.csv` (the only source of UI strings) and applies plural forms
- `signature_extractor/settings/` — defaults and the atomic settings file
- `signature_extractor/controller/` — navigation and settings changes, without widgets
- `signature_extractor/ui/pages/` — screen 1, Settings, the help stub, and empty processing/export pages
- `signature_extractor/ui/widgets/` — stepper, ⋯ menu, dialogs
- `signature_extractor/core/` — empty background-worker entry point for later stages
- `signature_extractor/assets/app.ico` — the approved application icon
