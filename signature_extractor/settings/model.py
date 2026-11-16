"""Settings stored in ``settings.json`` and their defaults.

The values match mockup 27. Lists of custom sizes and colors, and the last
export choices, are stored now so later stages can fill them without a
second file format. Stage 1 does not edit custom sizes or colors.
"""

from __future__ import annotations

import copy
from typing import Any

THEME_VALUES = ("system", "light", "dark")
LANGUAGE_VALUES = ("system", "ru", "en")
FORMAT_VALUES = ("png", "svg", "dxf")
COLOR_VALUES = ("as_photo", "black", "blue", "ink_blue", "bright_blue")
DPI_VALUES = (150, 300, 600)
IF_EXISTS_VALUES = ("add_number", "replace", "ask")
BUILTIN_SIZE_IDS = ("original", "15x5")

DEFAULT_FORMATS = ["png", "dxf"]
DEFAULT_SIZE_ID = "15x5"
DEFAULT_COLOR = "blue"
DEFAULT_DPI = 600
DEFAULT_MARGIN_MM = 2.0


def default_settings() -> dict[str, Any]:
    return {
        "theme": "system",
        "language": "system",
        "ai_default": False,
        "gpu_acceleration": True,
        "formats": list(DEFAULT_FORMATS),
        "default_size_id": DEFAULT_SIZE_ID,
        "custom_sizes": [],
        "frame_margin_mm": DEFAULT_MARGIN_MM,
        "default_color": DEFAULT_COLOR,
        "custom_colors": [],
        "png_dpi": DEFAULT_DPI,
        "save_folder": None,
        "name_template": None,
        "if_exists": "add_number",
        "check_updates": True,
        "last_export": {
            "formats": list(DEFAULT_FORMATS),
            "size_id": DEFAULT_SIZE_ID,
            "png_dpi": DEFAULT_DPI,
        },
    }


def coerce_settings(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge a JSON object onto the defaults.

    Returns ``(settings, extra)``. Unknown keys are returned separately so
    a future version's fields are not deleted on save. Invalid values for
    known keys fall back to the default for that key.
    """
    settings = default_settings()
    extra: dict[str, Any] = {}
    known = set(settings)
    for key, value in raw.items():
        if key not in known:
            extra[key] = value
    settings["theme"] = _choice(raw.get("theme"), THEME_VALUES, settings["theme"])
    settings["language"] = _choice(raw.get("language"), LANGUAGE_VALUES, settings["language"])
    settings["ai_default"] = _bool(raw.get("ai_default"), settings["ai_default"])
    settings["gpu_acceleration"] = _bool(raw.get("gpu_acceleration"), settings["gpu_acceleration"])
    settings["formats"] = _formats(raw.get("formats"), settings["formats"])
    settings["custom_sizes"] = _custom_sizes(raw.get("custom_sizes"))
    settings["default_size_id"] = _size_id(
        raw.get("default_size_id"), settings["custom_sizes"], settings["default_size_id"]
    )
    settings["frame_margin_mm"] = _margin(raw.get("frame_margin_mm"), settings["frame_margin_mm"])
    settings["custom_colors"] = _custom_colors(raw.get("custom_colors"))
    settings["default_color"] = _color(
        raw.get("default_color"), settings["custom_colors"], settings["default_color"]
    )
    settings["png_dpi"] = _dpi(raw.get("png_dpi"), settings["png_dpi"])
    settings["save_folder"] = _optional_str(raw.get("save_folder"))
    settings["name_template"] = _optional_str(raw.get("name_template"))
    settings["if_exists"] = _choice(raw.get("if_exists"), IF_EXISTS_VALUES, settings["if_exists"])
    settings["check_updates"] = _bool(raw.get("check_updates"), settings["check_updates"])
    settings["last_export"] = _last_export(raw.get("last_export"), settings["last_export"], settings["custom_sizes"])
    return settings, extra


def merge_for_save(settings: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    """Known settings plus preserved unknown keys. Known keys win."""
    coerced, _ignored = coerce_settings(settings)
    payload = copy.deepcopy(extra)
    payload.update(coerced)
    return payload


def _choice(value: Any, allowed: tuple[str, ...], fallback: str) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    return fallback


def _bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    return fallback


def _formats(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(fallback)
    picked = [item for item in FORMAT_VALUES if item in value]
    if not picked:
        return list(fallback)
    return picked


def _margin(value: Any, fallback: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fallback
    if value < 0 or value > 100:
        return fallback
    return float(value)


def _dpi(value: Any, fallback: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fallback
    number = int(value)
    if number in DPI_VALUES:
        return number
    return fallback


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _size_id(value: Any, custom_sizes: list[dict[str, Any]], fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    if value in BUILTIN_SIZE_IDS:
        return value
    if any(item.get("id") == value for item in custom_sizes):
        return value
    return fallback


def _color(value: Any, custom_colors: list[dict[str, Any]], fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    if value in COLOR_VALUES:
        return value
    if any(item.get("id") == value for item in custom_colors):
        return value
    return fallback


def _custom_sizes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        identifier = item.get("id")
        name = item.get("name")
        width = item.get("width_mm")
        height = item.get("height_mm")
        if not isinstance(identifier, str) or not identifier.strip():
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        if isinstance(width, bool) or isinstance(height, bool):
            continue
        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
            continue
        if width <= 0 or height <= 0:
            continue
        cleaned.append(
            {
                "id": identifier,
                "name": name,
                "width_mm": float(width),
                "height_mm": float(height),
            }
        )
    return cleaned


def _custom_colors(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        identifier = item.get("id")
        name = item.get("name")
        hex_color = item.get("hex")
        if not isinstance(identifier, str) or not identifier.strip():
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(hex_color, str) or not _hex_color(hex_color):
            continue
        cleaned.append({"id": identifier, "name": name, "hex": hex_color.upper()})
    return cleaned


def _hex_color(value: str) -> bool:
    if len(value) != 7 or not value.startswith("#"):
        return False
    try:
        int(value[1:], 16)
    except ValueError:
        return False
    return True


def _last_export(value: Any, fallback: dict[str, Any], custom_sizes: list[dict[str, Any]]) -> dict[str, Any]:
    result = copy.deepcopy(fallback)
    if not isinstance(value, dict):
        return result
    if "formats" in value:
        result["formats"] = _formats(value.get("formats"), result["formats"])
    if "size_id" in value:
        result["size_id"] = _size_id(value.get("size_id"), custom_sizes, result["size_id"])
    if "png_dpi" in value:
        result["png_dpi"] = _dpi(value.get("png_dpi"), result["png_dpi"])
    return result
