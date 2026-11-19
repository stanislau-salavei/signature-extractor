import importlib

import pytest


@pytest.fixture()
def settings_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import core.settings as mod
    return importlib.reload(mod)


def test_last_export_survives_reload(settings_mod):
    s = settings_mod.SettingsManager([])
    s.set("last_export", {"formats": ["SVG"], "size": "original", "png_dpi": 150})
    s2 = settings_mod.SettingsManager([])
    assert s2.get("last_export")["png_dpi"] == 150


def test_settings_default_resets_remembered_value(settings_mod):
    s = settings_mod.SettingsManager([])
    s.set("last_export", {"formats": ["SVG"], "size": "custom", "png_dpi": 150, "custom_w": 30, "custom_h": 9})
    s.set_export_default("png_resolution", 300)
    last = s.get("last_export")
    assert "png_dpi" not in last and last["formats"] == ["SVG"] and last["size"] == "custom"
    s.set_export_default("default_formats", ["PNG"])
    assert "formats" not in s.get("last_export")
    s.set_export_default("default_size", "15x5")
    assert s.get("last_export") == {}
    # persisted
    s2 = settings_mod.SettingsManager([])
    assert s2.get("png_resolution") == 300 and s2.get("last_export") == {}


def test_unlinked_setting_keeps_last_export(settings_mod):
    s = settings_mod.SettingsManager([])
    s.set("last_export", {"png_dpi": 150})
    s.set_export_default("default_color", "black")
    assert s.get("last_export") == {"png_dpi": 150}


def test_new_defaults(settings_mod):
    s = settings_mod.SettingsManager([])
    assert s.get("crop_margin_mm") == 0.5
    assert s.get("dxf_line_mm") == 0.18


def test_old_margin_default_migrates(settings_mod, tmp_path):
    import json
    d = tmp_path / "Signature Extractor"
    d.mkdir(exist_ok=True)
    (d / "settings.json").write_text(json.dumps({"crop_margin_mm": 2.0, "theme": "dark"}), encoding="utf-8")
    s = settings_mod.SettingsManager([])
    assert s.get("crop_margin_mm") == 0.5 and s.get("theme") == "dark"
    assert json.loads((d / "settings.json").read_text(encoding="utf-8"))["settings_version"] == settings_mod.SETTINGS_VERSION
    s.set("crop_margin_mm", 2.0)          # a deliberate 2 mm after the migration is kept
    assert settings_mod.SettingsManager([]).get("crop_margin_mm") == 2.0


def test_dxf_line_validation(settings_mod, tmp_path):
    import json
    d = tmp_path / "Signature Extractor"
    d.mkdir(exist_ok=True)
    (d / "settings.json").write_text(json.dumps({"dxf_line_mm": 99, "settings_version": 2}), encoding="utf-8")
    assert settings_mod.SettingsManager([]).get("dxf_line_mm") == 0.18
    (d / "settings.json").write_text(json.dumps({"dxf_line_mm": 0.35, "settings_version": 2}), encoding="utf-8")
    assert settings_mod.SettingsManager([]).get("dxf_line_mm") == 0.35
