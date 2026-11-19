"""Windows integration: per-monitor DPI v2, DWM caption colours, AppUserModelID, system theme.
Every call is a silent no-op on other systems / older Windows."""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional

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
        pass
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
            return False
    try:
        import darkdetect
        return bool(darkdetect.isDark())
    except Exception:
        return False


# ------------------------------------------------------------------ stage 5: DirectX 12, system info
_DX12: Optional[bool] = None


def dx12_supported() -> bool:
    """True when a DirectX 12 device can be created (feature level 11_0) — the GPU toggle in Settings.

    ``D3D12CreateDevice(NULL, D3D_FEATURE_LEVEL_11_0, IID_ID3D12Device, NULL)`` only tests support and
    returns S_FALSE (or S_OK) when it is there.  No d3d12.dll / any error → False.  Cached.
    ``SE_FORCE_DX12=0/1`` overrides it (tests, screenshots on Linux)."""
    global _DX12
    force = os.environ.get("SE_FORCE_DX12")
    if force in ("0", "1"):
        return force == "1"
    if _DX12 is not None:
        return _DX12
    ok = False
    if sys.platform.startswith("win"):
        try:
            import ctypes
            import uuid

            d3d12 = ctypes.WinDLL("d3d12.dll")
            iid = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID("189819f1-1db6-4b57-be54-1821339b85f7").bytes_le)
            fn = d3d12.D3D12CreateDevice
            fn.restype = ctypes.c_long
            hr = fn(None, 0xB000, ctypes.byref(iid), None)    # D3D_FEATURE_LEVEL_11_0
            ok = hr in (0, 1)                                  # S_OK / S_FALSE
        except Exception:
            log.info("DirectX 12 not available", exc_info=True)
            ok = False
    _DX12 = ok
    return ok


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
                    return ""
            build = q("CurrentBuild") or q("CurrentBuildNumber")
            display = q("DisplayVersion") or q("ReleaseId")
    except Exception:
        log.debug("registry read failed", exc_info=True)
    try:
        name = "Windows 11" if build and int(build) >= 22000 else f"Windows {platform.release()}"
    except ValueError:
        name = f"Windows {platform.release()}"
    parts = [name] + ([display] if display else [])
    return " ".join(parts) + (f" (build {build})" if build else "")


def gpu_names() -> str:
    """Graphics adapter names via DXGI (IDXGIFactory1::EnumAdapters1), else wmic; «unknown» when nothing."""
    if not sys.platform.startswith("win"):
        return os.environ.get("SE_FAKE_GPU", "unknown")
    names = _dxgi_adapters()
    if not names:
        try:
            import subprocess
            out = subprocess.run(["wmic", "path", "Win32_VideoController", "get", "Name"], capture_output=True,
                                 text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            names = [ln.strip() for ln in out.stdout.splitlines()[1:] if ln.strip()]
        except Exception:
            log.debug("wmic failed", exc_info=True)
    return "; ".join(dict.fromkeys(names)) or "unknown"


def _dxgi_adapters() -> list:
    try:
        import ctypes
        import uuid
        from ctypes import wintypes

        class DESC1(ctypes.Structure):
            _fields_ = [("Description", wintypes.WCHAR * 128), ("VendorId", wintypes.UINT),
                        ("DeviceId", wintypes.UINT), ("SubSysId", wintypes.UINT), ("Revision", wintypes.UINT),
                        ("DedicatedVideoMemory", ctypes.c_size_t), ("DedicatedSystemMemory", ctypes.c_size_t),
                        ("SharedSystemMemory", ctypes.c_size_t), ("AdapterLuid", ctypes.c_int64),
                        ("Flags", wintypes.UINT)]

        dxgi = ctypes.WinDLL("dxgi.dll")
        iid = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID("770aae78-f26f-4dba-a829-253c83d1b387").bytes_le)
        factory = ctypes.c_void_p()
        if dxgi.CreateDXGIFactory1(ctypes.byref(iid), ctypes.byref(factory)) != 0:
            return []
        vt = ctypes.cast(factory, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        enum1 = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p))(vt[12])
        release = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(vt[2])
        names, i = [], 0
        while True:
            ad = ctypes.c_void_p()
            if enum1(factory, i, ctypes.byref(ad)) != 0:
                break
            avt = ctypes.cast(ad, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            desc1 = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(DESC1))(avt[10])
            d = DESC1()
            if desc1(ad, ctypes.byref(d)) == 0 and not (d.Flags & 2):     # skip DXGI_ADAPTER_FLAG_SOFTWARE
                names.append(d.Description)
            ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(avt[2])(ad)
            i += 1
        release(factory)
        return names
    except Exception:
        log.debug("DXGI enumeration failed", exc_info=True)
        return []


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
