"""Stage 6 (2026-11-19): installer and release files, update flags, test-repository override, version in one
place; remark 92: the window keeps its size and maximized state (not its position), fitted to the screen.
Tests named ``test_ui_*`` need an X display (they are skipped without one)."""
import importlib
import json
import os
import re
import time
from pathlib import Path

import pytest

from core import updater as U
from core import window_geom as WG

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "packaging"
ISS = PKG / "installer.iss"
# The workflow lives in .github/workflows; until the box's GitHub token has the «workflow» scope it waits in
# packaging/ci/ (same file, moved by one commit) — the tests check whichever is there.
WF = next((p for p in (ROOT / ".github" / "workflows" / "build-installer.yml",
                       ROOT / "packaging" / "ci" / "build-installer.yml") if p.exists()),
          ROOT / ".github" / "workflows" / "build-installer.yml")


def iss_text():
    raw = ISS.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "Inno Setup needs UTF-8 with BOM for the Russian texts"
    return raw.decode("utf-8-sig").replace("\r\n", "\n")


def iss_setup():
    out, sect = {}, None
    for line in iss_text().splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            sect = s
        elif sect == "[Setup]" and "=" in s and not s.startswith(";"):
            k, v = s.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def build_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("se_build", PKG / "build.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ================================================================== version (one place)
def test_version_one_place():
    from core import version as V
    assert V.VERSION == "1.0.1" and V.RELEASE_TAG == "v1.0.1"
    b = build_mod()
    assert b.read_version() == "1.0.1"
    for p in ("ui/app.py", "ui/pages/settings_page.py"):
        src = (ROOT / p).read_text(encoding="utf-8")
        assert "from core.version import" in src
        assert not re.search(r'^(VERSION|RELEASE_TAG)\s*=\s*"', src, re.M), p


def test_build_helpers(tmp_path):
    b = build_mod()
    assert b.num_version("1.0") == (1, 0, 0, 0) and b.num_version("1.0.1") == (1, 0, 1, 0)
    assert b.installer_name("1.0") == "SignatureExtractor-1.0-setup.exe"
    vi = b.version_info_text("1.0.1")
    assert "filevers=(1, 0, 1, 0)" in vi and "'ProductVersion', '1.0.1'" in vi and "Stanislau Salavei" in vi
    f = tmp_path / "version.py"
    f.write_text('"""doc"""\nVERSION = "1.0"\nRELEASE_TAG = "v" + VERSION\n', encoding="utf-8")
    b.write_version("1.0.1", f)
    assert b.read_version(f) == "1.0.1" and 'RELEASE_TAG = "v" + VERSION' in f.read_text()
    with pytest.raises(SystemExit):
        b.write_version("1.0-beta", f)


def test_sha_file_is_what_the_updater_reads(tmp_path):
    b = build_mod()
    exe = tmp_path / "SignatureExtractor-1.0-setup.exe"
    exe.write_bytes(b"installer" * 1000)
    digest = b.sha256_of(exe)
    line = b.sha_line(digest, exe.name)
    assert line == f"{digest}  {exe.name}\n"
    assert U.sha_from_text(line) == digest == U.file_sha256(exe)


# ================================================================== installer
def test_iss_per_user_no_uac_and_paths():
    s = iss_setup()
    assert s["PrivilegesRequired"] == "lowest" and "PrivilegesRequiredOverridesAllowed" not in s
    assert s["DefaultDirName"] == r"{localappdata}\Programs\Signature Extractor"
    assert s["DisableDirPage"] == "yes"
    assert s["OutputBaseFilename"] == "SignatureExtractor-{#AppVersion}-setup"
    assert s["SetupIconFile"] == r"..\assets\app.ico"
    assert s["AppId"].startswith("{{") and len(s["AppId"]) == 39 and s["AppId"].endswith("}")


def test_iss_windows_10_1809_x64_only():
    s = iss_setup()
    assert s["MinVersion"] == "10.0.17763"
    assert s["ArchitecturesAllowed"] == "x64compatible"
    assert s["ArchitecturesInstallIn64BitMode"] == "x64compatible"


def test_iss_name_in_installed_apps_d9():
    t = iss_text()
    assert '#define AppTitle "Извлечение подписи (Signature Extractor)"' in t
    s = iss_setup()
    assert s["AppName"] == s["UninstallDisplayName"] == "{#AppTitle}"


def test_iss_languages_shortcuts_and_language_argument():
    t = iss_text()
    langs = re.findall(r'^Name: "(\w+)"; MessagesFile: "([^"]+)"', t, re.M)
    assert langs == [("en", "compiler:Default.isl"), ("ru", r"compiler:Languages\Russian.isl")]  # English first
    s = iss_setup()
    assert s["ShowLanguageDialog"] == "no" and s["LanguageDetectionMethod"] == "uilanguage"
    assert "en.ShortcutName=Signature Extractor" in t and "ru.ShortcutName=Извлечение подписи" in t
    assert "en.LangArg=en" in t and "ru.LangArg=ru" in t
    icons = [l for l in t.splitlines() if l.startswith("Name: \"{auto")]
    start = [l for l in icons if "{autoprograms}" in l]
    desk = [l for l in icons if "{autodesktop}" in l]
    assert len(start) == 1 and "Tasks:" not in start[0]                   # Start menu — always
    assert len(desk) == 1 and "Tasks: desktopicon" in desk[0]               # desktop — by the check box
    for l in start + desk:
        assert 'Parameters: "--installer-language {cm:LangArg}"' in l
    assert re.search(r'^Name: "desktopicon";.*Flags: unchecked$', t, re.M)  # off by default
    assert "installer_language.txt" not in t and "[Registry]" not in t and "SetEnvironmentVariable" not in t


def test_iss_run_after_install_also_silent():
    t = iss_text()
    run = t.split("[Run]", 1)[1].strip().splitlines()
    entry = [l for l in run if l.startswith("Filename:")]
    assert len(entry) == 1
    assert "--installer-language {cm:LangArg}" in entry[0] and "postinstall" in entry[0]
    assert "skipifsilent" not in entry[0]           # D5: the new version opens after /SILENT


def test_iss_running_app_and_settings_untouched():
    from ui import platform_win as PW
    s = iss_setup()
    t = iss_text()
    assert f'#define AppMutexName "{PW.INSTANCE_MUTEX}"' in t and s["AppMutex"] == "{#AppMutexName}"
    assert s["CloseApplications"] == "yes"
    assert "[UninstallDelete]" not in t
    assert "{userappdata}" not in t and "{app}\\..\\" not in t
    low = t.lower()
    assert "settings.json" not in low.replace("; %appdata%\\signature extractor (settings.json, log) is never touched (no uninstall-delete entries)", "")


def test_iss_license_note_with_link_no_license_page():
    """Installer polish (2026-11-20): no full licence page, a short note with a clickable link on the Welcome page."""
    s = iss_setup()
    assert "InfoBeforeFile" not in s and "LicenseFile" not in s
    assert "GNU GENERAL PUBLIC LICENSE" in (ROOT / "LICENSE").read_text(encoding="utf-8")[:200]
    t = iss_text()
    assert 'Source: "..\\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"' in t
    assert 'Source: "..\\dist\\SignatureExtractor\\*"' in t
    assert '#define LicenseUrl "https://www.gnu.org/licenses/gpl-3.0.html"' in t
    assert ("ru.LicenseNote=«Извлечение подписи» — свободная программа под лицензией GNU GPL версии 3. "
            "Полный текст: %1 и файл LICENSE в папке программы.") in t
    assert "en.LicenseNote=Signature Extractor is free software under the GNU GPL, version 3." in t
    code = t.split("[Code]", 1)[1]
    assert "TNewLinkLabel.Create" in code and "OnLinkClick := @LicenseLinkClick" in code
    assert '<a href="{#LicenseUrl}">{#LicenseUrl}</a>' in code and "ShellExecAsOriginalUser('open', Link" in code


def test_iss_wizard_pages_and_texts():
    s = iss_setup()
    t = iss_text()
    assert s["WizardStyle"] == "modern"
    assert s["DisableWelcomePage"] == "no" and s["DisableReadyPage"] == "no"
    assert s["DisableDirPage"] == "yes" and s["AlwaysShowDirOnReadyPage"] == "yes"
    assert s["AppComments"] == "{cm:AppComments}" and "ru.AppComments=" in t and "en.AppComments=" in t
    nb = "\u00a0"
    for line in ("ru.WelcomeLabel1=Установка программы «Извлечение" + nb + "подписи»",
                 "ru.WelcomeLabel2=Программа делает из фото или скана подписи чистые файлы PNG, SVG и DXF. "
                 "Всё обрабатывается на вашем компьютере.%n%nПрава администратора не нужны: "
                 "программа ставится только для вашей учётной записи.",
                 "ru.ClickNext=Нажмите «Далее», чтобы продолжить.",
                 "ru.FinishedHeadingLabel=Установка завершена",
                 "ru.FinishedLabel=Программа «Извлечение подписи» установлена. Её можно открыть из меню «Пуск».",
                 "ru.ClickFinish=Нажмите «Завершить», чтобы закрыть мастер установки.",
                 "ru.LaunchApp=Запустить программу", "en.LaunchApp=Launch the program",
                 "en.FinishedHeadingLabel=Setup is complete"):
        assert line in t.splitlines(), line
    # page texts use the short name, the window title keeps the full one with the version
    msgs = t.split("[Messages]", 1)[1].split("[CustomMessages]", 1)[0]
    assert "(Signature Extractor)" not in msgs and "[name" not in msgs
    assert "WizardForm.Caption := FmtMessage(SetupMessage(msgSetupWindowTitle), ['{#AppTitle} {#AppVersion}'])" in t
    run = [l for l in t.split("[Run]", 1)[1].splitlines() if l.startswith("Filename:")][0]
    assert 'Description: "{cm:LaunchApp}"' in run and "unchecked" not in run       # ticked by default


def test_iss_wizard_images_all_dpi_sizes():
    from PIL import Image
    s = iss_setup()
    assert s["WizardImageFile"] == r"installer\wizard_image_ru_*.png"
    assert s["WizardSmallImageFile"] == r"installer\wizard_small_*.png"
    assert 'Source: "installer\\wizard_image_en_*.png"; Flags: dontcopy' in iss_text()
    d = PKG / "installer"
    wide = [(202, 386), (269, 515), (336, 643), (403, 772), (430, 824), (498, 953), (551, 1055)]  # Inno 6.6 table
    for lang in ("ru", "en"):
        for w, h in wide:
            with Image.open(d / f"wizard_image_{lang}_{w}x{h}.png") as im:
                assert im.format == "PNG" and im.size == (w, h)
    for n in (58, 77, 97, 116, 124, 143, 159):
        with Image.open(d / f"wizard_small_{n}x{n}.png") as im:
            assert im.format == "PNG" and im.size == (n, n) and im.mode == "RGBA"
            assert im.getpixel((0, 0))[3] == 0                    # transparent margin around the icon
    names = sorted(p.name for p in d.iterdir())
    assert len(names) == 21 and all(n.endswith(".png") for n in names)   # no mockups or other files
    for n in ('if Width <= 202', "'551x1055'"):
        assert n in iss_text()


def test_spec_onedir_icon_no_upx_no_ai():
    t = (PKG / "SignatureExtractor.spec").read_text(encoding="utf-8")
    assert "COLLECT(" in t and "exclude_binaries=True" in t           # onedir
    assert 'name="SignatureExtractor"' in t and "console=False" in t
    assert t.count("upx=False") == 2 and '"assets" / "app.ico"' in t
    assert '"i18n"' in t and '"assets"' in t and "customtkinter" in t
    assert "onnx" not in t.replace('"onnxruntime", "torch",', "")       # remark 78: no AI model
    assert "isnet" not in t.lower() and "is-net" not in t.lower()


# ================================================================== workflow (never publishes)
def test_workflow_builds_on_windows_and_only_drafts():
    t = WF.read_text(encoding="utf-8")
    assert "runs-on: windows-latest" in t and "workflow_dispatch:" in t and "pull_request:" in t
    assert "python packaging/build.py" in t and "actions/upload-artifact@v4" in t
    assert "SE_SMOKE_REPORT" in t
    creates = [l for l in t.splitlines() if "gh release" in l]
    assert creates and all("--draft" in l for l in creates if "create" in l)
    assert "gh release edit" not in t and "--draft=false" not in t and "publish" not in t.replace(
        "never publishes", "").replace("Nothing is published", "").replace("presses «Publish»", "").lower()
    assert "branches: [stage-6]" not in t            # no double runs; pushes only for tags
    assert re.search(r"^permissions:\n  contents: read", t, re.M)


def test_release_notes_draft():
    t = (ROOT / "docs" / "release_notes" / "v1.0.md").read_text(encoding="utf-8")
    assert t.startswith("## Извлечение подписи 1.0\n") and "<!--" not in t      # approved, no draft marker
    assert "## Signature Extractor 1.0" in t
    assert "SignatureExtractor-1.0-setup.exe" in t and "SmartScreen" in t
    assert not re.search(r"\b[0-9a-f]{64}\b", t)     # the checksum is added by the workflow
    assert "AI" not in t.replace("AutoCAD", "") and "DirectX" not in t



def test_release_notes_v101():
    t = (ROOT / "docs" / "release_notes" / "v1.0.1.md").read_text(encoding="utf-8")
    assert t.startswith("## Извлечение подписи 1.0.1\n") and "<!--" not in t
    assert "## Signature Extractor 1.0.1" in t
    assert "SignatureExtractor-1.0.1-setup.exe" in t and "SmartScreen" in t
    assert not re.search(r"\b[0-9a-f]{64}\b", t)
    assert "AI" not in t.replace("AutoCAD", "")

# ================================================================== update from the app
def test_update_installer_flags_d5(tmp_path):
    from ui import platform_win as PW
    cmd = PW.installer_command(tmp_path / "SignatureExtractor-1.1-setup.exe")
    assert cmd[0].endswith("SignatureExtractor-1.1-setup.exe")
    assert cmd[1:] == ["/SILENT", "/SP-", "/CLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS"]
    assert "/VERYSILENT" not in cmd


def test_update_api_env_override(monkeypatch):
    monkeypatch.delenv(U.API_ENV, raising=False)
    assert U.api_url() == U.API_LATEST == "https://api.github.com/repos/stanislau-salavei/signature-extractor/releases/latest"
    test = "https://api.github.com/repos/someone/se-update-test/releases/latest"
    monkeypatch.setenv(U.API_ENV, test)
    assert U.api_url() == test
    monkeypatch.setenv(U.API_ENV, "file:///etc/passwd")
    assert U.api_url() == U.API_LATEST


def test_release_tag_and_asset_names_match_updater():
    data = {"tag_name": "v1.0.1", "body": "",
            "assets": [{"name": "SignatureExtractor-1.0.1-setup.exe", "browser_download_url": "https://x/a.exe"},
                       {"name": "SignatureExtractor-1.0.1-setup.exe.sha256", "browser_download_url": "https://x/a.sha"}]}
    r = U.parse_release(data)
    assert r.installer_url == "https://x/a.exe" and r.sha_url == "https://x/a.sha"
    assert U.is_newer("v1.0.1", "1.0") and U.is_newer("v1.1", "1.0.1") and not U.is_newer("v1.0", "1.0")


# ================================================================== remark 92: pure logic
AREA = (0, 0, 1920, 1040)      # 1080p minus the taskbar


def test_r92_default_size_centred():
    w, h, x, y, maxi, mw, mh = WG.initial_geometry(None, AREA, (16, 39), 1.0)
    assert (w, h, maxi) == (1280, 768, False) and (mw, mh) == (1024, 648)
    assert x == (1920 - 1296) // 2 and y == (1040 - 807) // 2


def test_r92_saved_size_and_maximized_kept():
    saved = WG.to_saved(1500.4, 900.6, True)
    assert saved == {"w": 1500, "h": 901, "maximized": True}
    w, h, x, y, maxi, *_ = WG.initial_geometry(saved, AREA, (0, 0), 1.0)
    assert (w, h, maxi) == (1500, 901, True)


def test_r92_position_not_remembered():
    a = WG.initial_geometry({"w": 1100, "h": 700, "x": 5, "y": 5}, (1920, 0, 2560, 1400), (0, 0), 1.0)
    assert a[2] == 1920 + (2560 - 1100) // 2 and a[3] == (1400 - 700) // 2     # centred on that work area


def test_r92_clamped_to_screen_and_scale():
    # remembered on a 2560 × 1440 monitor, now 1366 × 728 work area at 100 %
    w, h, x, y, *_ = WG.initial_geometry({"w": 2400, "h": 1300, "maximized": False}, (0, 0, 1366, 728), (16, 39), 1.0)
    assert (w, h) == (1350, 689) and x >= 0 and y >= 0
    # the same at 150 %: logical size fits 1920 × 1032 physical
    w, h, x, y, *_ = WG.initial_geometry({"w": 2400, "h": 1300}, (0, 0, 1920, 1032), (24, 58), 1.5)
    assert (w, h) == ((1920 - 24) // 1.5, int((1032 - 58) / 1.5))
    assert round(w * 1.5) + 24 <= 1920 and round(h * 1.5) + 58 <= 1032


def test_r92_minimum_and_small_screen():
    assert WG.initial_geometry({"w": 300, "h": 200}, AREA, (0, 0), 1.0)[:2] == (1024, 648)
    w, h, x, y, maxi, mw, mh = WG.initial_geometry(None, (0, 0, 1024, 600), (16, 39), 1.25)
    assert w <= (1024 - 16) / 1.25 and h <= (600 - 39) / 1.25 and (mw, mh) == (w, h)


@pytest.mark.parametrize("bad", [None, 5, "x", [], {"w": "1"}, {"w": 1200}, {"w": True, "h": 700},
                                 {"w": 50, "h": 700}, {"w": 1e9, "h": 700}])
def test_r92_damaged_value_gives_default(bad):
    assert WG.parse_saved(bad) is None
    assert WG.initial_geometry(bad, AREA, (0, 0), 1.0)[:2] == (1280, 768)


def test_r92_settings_key_valid_and_kept_on_reset(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import core.settings as CS
    importlib.reload(CS)
    m = CS.SettingsManager([])
    assert m.get("window") is None
    m.set("window", {"w": 1300, "h": 800, "maximized": True})
    m.reset_to_defaults()
    assert m.get("window") == {"w": 1300, "h": 800, "maximized": True}
    (tmp_path / "Signature Extractor" / "settings.json").write_text(json.dumps({"window": "big"}))
    assert CS.SettingsManager([]).get("window") is None


# ================================================================== remark 92: real window (X display)
def _make_app(tmp, window):
    if not os.environ.get("DISPLAY"):
        pytest.skip("no X display")
    os.environ["APPDATA"] = os.environ["USERPROFILE"] = str(tmp)
    os.environ["LANG"] = "ru_RU.UTF-8"
    d = tmp / "Signature Extractor"
    d.mkdir(exist_ok=True)
    data = {"theme": "light", "language": "ru"}
    if window is not None:
        data["window"] = window
    (d / "settings.json").write_text(json.dumps(data))
    import core.settings
    importlib.reload(core.settings)
    from ui import app as A
    a = A.App([])
    pump(a, 300)
    return a


def pump(a, ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        a.root.update()
        time.sleep(0.01)


def _saved(tmp):
    return json.loads((tmp / "Signature Extractor" / "settings.json").read_text(encoding="utf-8")).get("window")


@pytest.fixture
def env_restore():
    old = {k: os.environ.get(k) for k in ("APPDATA", "USERPROFILE", "LANG")}
    yield
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_ui_r92_size_restored_centred_and_saved_on_close(tmp_path, env_restore):
    a = _make_app(tmp_path, {"w": 1100, "h": 700, "maximized": False})
    try:
        r = a.root
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        assert (r.winfo_width(), r.winfo_height()) == (1100, 700)
        assert abs(r.winfo_x() - (sw - 1100) // 2) <= 2 and abs(r.winfo_y() - (sh - 700) // 2) <= 2
        assert not a.is_maximized()
        r.geometry("1200x720+3+4")                     # the user resizes and moves the window
        pump(a, 200)
    finally:
        a._on_close()
    assert _saved(tmp_path) == {"w": 1200, "h": 720, "maximized": False}       # no position saved
    b = _make_app(tmp_path, _saved(tmp_path))
    try:
        r = b.root
        assert (r.winfo_width(), r.winfo_height()) == (1200, 720)
        assert abs(r.winfo_x() - (r.winfo_screenwidth() - 1200) // 2) <= 2      # centred again, not +3+4
    finally:
        b.root.destroy()


def test_ui_r92_too_big_for_screen_is_fitted(tmp_path, env_restore):
    a = _make_app(tmp_path, {"w": 9000, "h": 6000, "maximized": False})
    try:
        r = a.root
        assert r.winfo_width() <= r.winfo_screenwidth() and r.winfo_height() <= r.winfo_screenheight()
        assert r.winfo_width() >= 1024 and r.winfo_x() >= 0 and r.winfo_y() >= 0
    finally:
        a.root.destroy()


def test_ui_r92_maximized_state_kept_with_normal_size(tmp_path, env_restore):
    a = _make_app(tmp_path, {"w": 1150, "h": 690, "maximized": False})
    try:
        a.set_maximized(True)
        pump(a, 200)
        assert a.is_maximized()
    finally:
        a._on_close()
    assert _saved(tmp_path) == {"w": 1150, "h": 690, "maximized": True}       # normal size, not the maximized one
    b = _make_app(tmp_path, _saved(tmp_path))
    try:
        assert b.is_maximized()
        b.set_maximized(False)
        pump(b, 200)
        assert not b.is_maximized()
    finally:
        b._on_close()
    assert _saved(tmp_path) == {"w": 1150, "h": 690, "maximized": False}


def test_ui_smoke_report(tmp_path, env_restore, monkeypatch):
    a = _make_app(tmp_path, None)
    rep = tmp_path / "smoke.json"
    monkeypatch.setenv("SE_SMOKE_REPORT", str(rep))
    from ui.smoke import maybe_schedule
    assert maybe_schedule(a, 10)
    end = time.time() + 15
    while not rep.exists() and time.time() < end:
        try:
            a.root.update()
        except Exception:
            break
        time.sleep(0.01)
    data = json.loads(rep.read_text(encoding="utf-8"))
    assert data["ok"] and data["version"] == "1.0.1" and data["heic"] == [64, 48] and data["frozen"] is False
    assert _saved(tmp_path) is None                    # the smoke run does not remember a window size
