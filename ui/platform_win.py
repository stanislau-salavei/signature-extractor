"""Windows integration: per-monitor DPI v2, DWM caption colours, AppUserModelID, system theme.
Every call is a silent no-op on other systems / older Windows."""
from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)
IS_WIN = sys.platform.startswith("win")


def enable_per_monitor_dpi_v2() -> None:
    if not IS_WIN:
        return
    import ctypes
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4 (Windows 10 1703+)
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        log.warning("enable_per_monitor_dpi_v2: Exception caught", exc_info=True)   # remark 81
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        log.debug("DPI awareness not set", exc_info=True)


def set_app_user_model_id(app_id: str) -> None:
    if not IS_WIN:
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        log.debug("AppUserModelID not set", exc_info=True)


def _colorref(hex_color: str) -> int:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r | (g << 8) | (b << 16)


def set_caption_colors(root, bg: str, text: str, dark: bool) -> None:
    """Title bar in the interface background like Windows Terminal (DWM 35/36/20)."""
    if not IS_WIN:
        return
    try:
        import ctypes
        from ctypes import wintypes
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        dwm = ctypes.windll.dwmapi
        val = ctypes.c_int(1 if dark else 0)
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), 20, ctypes.byref(val), ctypes.sizeof(val))
        for attr, color in ((35, bg), (36, text)):
            c = wintypes.DWORD(_colorref(color))
            dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), attr, ctypes.byref(c), ctypes.sizeof(c))
    except Exception:
        log.debug("DWM caption colours not applied (Windows 10?)", exc_info=True)


def system_is_dark() -> bool:
    if IS_WIN:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        except Exception:
            log.debug("system_is_dark: Exception caught", exc_info=True)   # remark 81
            return False
    try:
        import darkdetect
        return bool(darkdetect.isDark())
    except Exception:
        log.debug("system_is_dark: Exception caught", exc_info=True)   # remark 81
        return False


# ------------------------------------------------------------------ stage 5: system info
# remark 88: no graphics card / DirectX 12 detection (it was only needed for AI)


def windows_version() -> str:
    """«Windows 11 23H2 (build 22631)»; outside Windows — platform.platform()."""
    import platform
    if not sys.platform.startswith("win"):
        return platform.platform()
    build, display = "", ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as k:
            def q(name):
                try:
                    return str(winreg.QueryValueEx(k, name)[0])
                except OSError:
                    log.debug("windows_version.q: OSError caught", exc_info=True)   # remark 81
                    return ""
            build = q("CurrentBuild") or q("CurrentBuildNumber")
            display = q("DisplayVersion") or q("ReleaseId")
    except Exception:
        log.debug("registry read failed", exc_info=True)
    try:
        name = "Windows 11" if build and int(build) >= 22000 else f"Windows {platform.release()}"
    except ValueError:
        log.debug("windows_version: ValueError caught", exc_info=True)   # remark 81
        name = f"Windows {platform.release()}"
    parts = [name] + ([display] if display else [])
    return " ".join(parts) + (f" (build {build})" if build else "")


def launch_installer(path) -> bool:
    """Start the downloaded installer detached from the app (flags of the installer — stage 6)."""
    import subprocess
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen([str(path)], close_fds=True,
                             creationflags=getattr(subprocess, "DETACHED_PROCESS", 0x8)
                             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200))
        else:
            subprocess.Popen([str(path)], close_fds=True, start_new_session=True)
        return True
    except Exception:
        log.exception("cannot start the installer %s", path)
        return False
