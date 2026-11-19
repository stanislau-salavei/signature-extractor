"""Settings file: %APPDATA%\\Signature Extractor\\settings.json (JSON, atomic write).

The installer / uninstaller never touch this file.  A missing or damaged file is replaced
by defaults.  ``name_template`` = None means «language default» («подпись_{имя}» / ``signature_{name}``);
``save_folder`` = None is replaced at the start by Documents\\Подписи / Documents\\Signatures in the language of
that launch and then stays (remark 83).
"""
from __future__ import annotations

import copy
import json
import locale
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

APP_DIR_NAME = "Signature Extractor"


def get_app_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    target = base / APP_DIR_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target


def documents_dir() -> Path:
    """User «Documents» folder (Known Folder on Windows, ~/Documents elsewhere)."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_PERSONAL = 5
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                return Path(buf.value)
        except Exception:
            log.debug("SHGetFolderPathW failed", exc_info=True)
    return Path.home() / "Documents"


DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "system",            # system | light | dark
    "language": "system",         # system | ru | en
    "default_formats": ["PNG", "DXF"],
    "default_size": "15x5",
    "crop_margin_mm": 0.5,        # «Поле рамки», every size mode (remark 7)
    "dxf_line_mm": 0.18,          # DXF centreline thickness (remark 9)
    "svg_mode": "original",       # SVG thickness: original (filled outline) | stroke (remark 22)
    "svg_line_mm": 0.18,          # SVG «Заданная толщина», separate from DXF
    "default_color": "blue",
    "png_resolution": 1200,       # remark 36: 300 | 600 | 1200 (150 removed)
    "save_folder": None,          # fixed at the first launch: Documents\<export.default_folder> (remark 83)
    "name_template": None,        # None = settings.name_template.value of the UI language
    "if_exists": "ask",           # add_number | replace | ask — remark 43: «Спрашивать» by default
    "check_updates": True,
    "last_update_check": None,    # stage 5: ISO time of the last silent check / «Позже» (once a day)
    "custom_sizes": [],
    "custom_colors": [],
    "window": None,               # remark 92: {"w", "h", "maximized"} — normal client size in logical px
    "last_export": {},            # formats, size, custom_w/h, png_dpi, color, svg_mode — kept after «Готово»
    "settings_version": 3,
}
SETTINGS_VERSION = 3
OLD_MARGIN_DEFAULT = 2.0          # v1 default; v2 makes 0.5 mm the default in every mode
PNG_DPI_VALUES = (300, 600, 1200)

# An export default changed in Settings resets the remembered last-export value (stage 3 decision).
LAST_EXPORT_LINKS: Dict[str, tuple] = {
    "default_formats": ("formats",),
    "default_size": ("size", "custom_w", "custom_h"),
    "png_resolution": ("png_dpi",),
    "default_color": ("color",),
    "svg_mode": ("svg_mode",),      # remark 29: Settings › Default formats › SVG thickness
    "svg_line_mm": ("svg_line_mm",),  # remark 32: Settings › «Толщина SVG» › «Толщина линии»
    "dxf_line_mm": ("dxf_line_mm",),  # remark 50: Settings › «Толщина DXF»
}


def read_installer_language(argv: List[str]) -> Optional[str]:
    """Only the launch argument ``--installer-language ru|en`` (no file, no environment variable)."""
    for i, arg in enumerate(argv):
        val = None
        if arg == "--installer-language" and i + 1 < len(argv):
            val = argv[i + 1]
        elif arg.startswith("--installer-language="):
            val = arg.split("=", 1)[1]
        if val is not None:
            val = val.strip().lower()
            return val if val in ("ru", "en") else None
    return None


def resolve_system_language() -> str:
    """Windows UI language -> ru / en (anything else -> en)."""
    try:
        if sys.platform.startswith("win"):
            import ctypes

            lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "ru" if (lid & 0x3FF) == 0x19 else "en"
        lang = os.environ.get("LANG") or locale.getlocale()[0] or ""
        return "ru" if lang and lang.lower().startswith("ru") else "en"
    except Exception:
        log.debug("resolve_system_language: Exception caught", exc_info=True)   # remark 81
        return "en"


def _valid(key: str, value: Any) -> bool:
    d = DEFAULT_SETTINGS[key]
    if key in ("save_folder", "name_template", "last_update_check"):
        return value is None or isinstance(value, str)
    if key == "window":
        return value is None or isinstance(value, dict)
    if key == "theme":
        return value in ("system", "light", "dark")
    if key == "language":
        return value in ("system", "ru", "en")
    if key == "if_exists":
        return value in ("add_number", "replace", "ask")
    if key == "png_resolution":
        return value in PNG_DPI_VALUES and not isinstance(value, bool)
    if key == "default_formats":
        return isinstance(value, list) and all(v in ("PNG", "SVG", "DXF") for v in value)
    if key == "crop_margin_mm":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 100
    if key == "svg_mode":
        return value in ("original", "stroke")
    if key in ("dxf_line_mm", "svg_line_mm"):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and 0.01 <= value <= 5
    if key == "settings_version":
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(d, bool):
        return isinstance(value, bool)
    if isinstance(d, list):
        return isinstance(value, list)
    if isinstance(d, dict):
        return isinstance(value, dict)
    return isinstance(value, type(d))


class SettingsManager:
    def __init__(self, argv: Optional[List[str]] = None):
        self.path = get_app_data_dir() / "settings.json"
        self.data: Dict[str, Any] = copy.deepcopy(DEFAULT_SETTINGS)
        self.first_run = False          # test hook (remark 108): no settings.json before this start
        self._load(list(argv) if argv is not None else sys.argv[1:])

    def _load(self, argv: List[str]) -> None:
        if not self.path.exists():
            self.first_run = True
            lang = read_installer_language(argv)
            if lang:
                self.data["language"] = lang
            self._safe_save()
            return
        try:
            parsed = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("settings root is not an object")
            for k in DEFAULT_SETTINGS:
                if k in parsed and _valid(k, parsed[k]):
                    self.data[k] = parsed[k]
            ver = parsed.get("settings_version")
            if not isinstance(ver, int) or ver < SETTINGS_VERSION:
                ver = ver if isinstance(ver, int) else 1
                # v1 saved every default, so 2.0 there is the old default, not a user choice
                if ver < 2 and parsed.get("crop_margin_mm") == OLD_MARGIN_DEFAULT:
                    self.data["crop_margin_mm"] = DEFAULT_SETTINGS["crop_margin_mm"]
                if ver < 3:
                    self._migrate_png_dpi(parsed)
                self.data["settings_version"] = SETTINGS_VERSION
                self._safe_save()
        except Exception:
            log.warning("settings file damaged, defaults restored", exc_info=True)
            self.data = copy.deepcopy(DEFAULT_SETTINGS)
            self._safe_save()

    def _migrate_png_dpi(self, parsed: Dict[str, Any]) -> None:
        """Remark 36 (once, v2 → v3): only the no-longer-offered 150 DPI becomes 300 (Settings and the
        remembered last export).  Any other saved DPI — 600 included — is the user's choice and stays
        (user decision 2026-11-17: an auto-saved old default can't be told from a deliberate 600, so 600 is
        never migrated).  A missing value keeps the new default 1200."""
        if parsed.get("png_resolution") == 150:
            self.data["png_resolution"] = 300
        last = self.data.get("last_export")
        if isinstance(last, dict) and last.get("png_dpi") == 150:
            last = dict(last)
            last["png_dpi"] = 300
            self.data["last_export"] = last

    def _safe_save(self) -> None:
        try:
            self.save()
        except OSError:
            log.exception("cannot write settings")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix="settings_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                log.debug("SettingsManager.save: OSError caught", exc_info=True)   # remark 81
            raise

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self._safe_save()

    def set_export_default(self, key: str, value: Any) -> None:
        """Set an export default from Settings and forget the remembered last-export value for it."""
        self.data[key] = value
        last = dict(self.data.get("last_export") or {})
        for field in LAST_EXPORT_LINKS.get(key, ()):
            last.pop(field, None)
        self.data["last_export"] = last
        self._safe_save()

    def delete_custom_color(self, key: str) -> str:
        """Stage 5: one action for screen 3 and Settings — remove an own colour; a deleted default
        colour gives «Синий» back; a remembered last-export colour is forgotten.  Returns the default."""
        from core import export as ex
        cid = key[len(ex.CUSTOM_COLOR_PREFIX):] if key.startswith(ex.CUSTOM_COLOR_PREFIX) else key
        left, new_default = ex.remove_custom_color(list(self.data.get("custom_colors") or []), cid,
                                                   self.data.get("default_color", ex.DEFAULT_COLOR_KEY))
        self.data["custom_colors"] = left
        self.data["default_color"] = new_default
        last = dict(self.data.get("last_export") or {})
        if last.get("color") == ex.CUSTOM_COLOR_PREFIX + cid:
            last.pop("color", None)
            self.data["last_export"] = last
        self._safe_save()
        return new_default

    # remark 37: «Восстановить параметры по умолчанию» keeps the user's own size templates and colours
    KEEP_ON_RESET = ("custom_sizes", "custom_colors", "settings_version", "last_update_check",
                     "window")                   # remark 92: the window size is not a setting

    def reset_to_defaults(self) -> None:
        """All settings back to DEFAULT_SETTINGS (last_export forgotten too), except KEEP_ON_RESET."""
        keep = {k: copy.deepcopy(self.data.get(k, DEFAULT_SETTINGS[k])) for k in self.KEEP_ON_RESET}
        self.data = copy.deepcopy(DEFAULT_SETTINGS)
        self.data.update(keep)
        self.data["settings_version"] = SETTINGS_VERSION
        self._safe_save()

    def effective_language(self) -> str:
        lang = self.data.get("language", "system")
        return lang if lang in ("ru", "en") else resolve_system_language()

    def save_folder(self, folder_name: str) -> Path:
        v = self.data.get("save_folder")
        return Path(v) if v else documents_dir() / folder_name

    def fix_save_folder(self, folder_name: str) -> Path:
        """Remark 83: the default save folder (Documents\\Подписи or Documents\\Signatures, the name from the
        table in the language of that launch) is chosen once — at the first launch or after «Сбросить» — and
        saved, so a later language change does not move the files to another folder.  A folder the user
        already has is used as it is (nothing is renamed or created here)."""
        if not self.data.get("save_folder"):
            self.data["save_folder"] = str(documents_dir() / folder_name)
            self._safe_save()
        return Path(self.data["save_folder"])

    def name_template(self, default_value: str) -> str:
        return self.data.get("name_template") or default_value
