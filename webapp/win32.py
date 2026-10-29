"""ctypes helpers for the pywebview shell: window placement, DWM title bar,
single-instance activation and the WebView2 runtime check. Every function
is a no-op (or returns None/False) when not on Windows or when a call fails."""

import ctypes
import sys
from ctypes import wintypes

IS_WINDOWS = sys.platform == "win32"

MUTEX_NAME = "Tyoaikaweleho_SingleInstance_Mutex"
ACTIVATE_EVENT_NAME = "Tyoaikaweleho_Activate_Event"
WEBVIEW2_CLIENT = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_DOWNLOAD_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"

DEFAULT_SIZE = (960, 760)
MIN_SIZE = (700, 560)

_ERROR_ALREADY_EXISTS = 183
_MONITOR_DEFAULTTONULL = 0
_MONITOR_DEFAULTTONEAREST = 2
_MONITOR_DEFAULTTOPRIMARY = 1
_SW_HIDE = 0
_SW_SHOWMINIMIZED = 2
_SW_SHOWMAXIMIZED = 3
_SW_RESTORE = 9
_WPF_RESTORETOMAXIMIZED = 0x2
_ASFW_ANY = -1
_SYNCHRONIZE = 0x00100000
_EVENT_MODIFY_STATE = 0x0002
_WAIT_OBJECT_0 = 0
_INFINITE = 0xFFFFFFFF

_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36

MB_OK = 0x0
MB_ICONERROR = 0x10
MB_ICONWARNING = 0x30
MB_ICONINFORMATION = 0x40
MB_YESNO = 0x4
IDYES = 6


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


class _WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [("length", wintypes.UINT),
                ("flags", wintypes.UINT),
                ("showCmd", wintypes.UINT),
                ("ptMinPosition", wintypes.POINT),
                ("ptMaxPosition", wintypes.POINT),
                ("rcNormalPosition", wintypes.RECT)]


_dlls: dict = {}


def _user32():
    dll = _dlls.get("user32")
    if dll is None:
        # private handle, so these argtypes don't leak into other ctypes users
        dll = ctypes.WinDLL("user32", use_last_error=True)
        dll.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        dll.MonitorFromPoint.restype = ctypes.c_void_p
        dll.MonitorFromRect.argtypes = [ctypes.POINTER(wintypes.RECT), wintypes.DWORD]
        dll.MonitorFromRect.restype = ctypes.c_void_p
        dll.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MONITORINFO)]
        dll.GetMonitorInfoW.restype = wintypes.BOOL
        dll.GetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(_WINDOWPLACEMENT)]
        dll.GetWindowPlacement.restype = wintypes.BOOL
        dll.SetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(_WINDOWPLACEMENT)]
        dll.SetWindowPlacement.restype = wintypes.BOOL
        dll.SetForegroundWindow.argtypes = [wintypes.HWND]
        dll.SetForegroundWindow.restype = wintypes.BOOL
        dll.GetForegroundWindow.argtypes = []
        dll.GetForegroundWindow.restype = wintypes.HWND
        dll.IsIconic.argtypes = [wintypes.HWND]
        dll.IsIconic.restype = wintypes.BOOL
        dll.IsZoomed.argtypes = [wintypes.HWND]
        dll.IsZoomed.restype = wintypes.BOOL
        dll.IsWindowVisible.argtypes = [wintypes.HWND]
        dll.IsWindowVisible.restype = wintypes.BOOL
        dll.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        dll.ShowWindow.restype = wintypes.BOOL
        dll.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
        dll.AllowSetForegroundWindow.restype = wintypes.BOOL
        dll.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                    wintypes.UINT]
        dll.MessageBoxW.restype = ctypes.c_int
        _dlls["user32"] = dll
    return dll


def _kernel32():
    dll = _dlls.get("kernel32")
    if dll is None:
        dll = ctypes.WinDLL("kernel32", use_last_error=True)
        dll.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        dll.CreateMutexW.restype = wintypes.HANDLE
        dll.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL,
                                     wintypes.LPCWSTR]
        dll.CreateEventW.restype = wintypes.HANDLE
        dll.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        dll.OpenEventW.restype = wintypes.HANDLE
        dll.SetEvent.argtypes = [wintypes.HANDLE]
        dll.SetEvent.restype = wintypes.BOOL
        dll.CloseHandle.argtypes = [wintypes.HANDLE]
        dll.CloseHandle.restype = wintypes.BOOL
        dll.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        dll.WaitForSingleObject.restype = wintypes.DWORD
        _dlls["kernel32"] = dll
    return dll


# ── message box ──────────────────────────────────────────────────

def message_box(text: str, title: str = "Työaikaweleho", flags: int = MB_OK) -> int:
    if not IS_WINDOWS:
        print(f"{title}: {text}", file=sys.stderr)
        return 0
    try:
        return _user32().MessageBoxW(None, text, title, flags)
    except (AttributeError, OSError):
        return 0


# ── single instance ──────────────────────────────────────────────

def acquire_single_instance() -> tuple[bool, object]:
    """(acquired, handle). Keep the handle alive for the process lifetime."""
    if not IS_WINDOWS:
        return True, None
    k32 = _kernel32()
    handle = k32.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        return False, handle
    return True, handle


def create_activate_event():
    """Auto-reset event a second instance signals to bring this one forward."""
    if not IS_WINDOWS:
        return None
    try:
        return _kernel32().CreateEventW(None, False, False, ACTIVATE_EVENT_NAME) or None
    except (AttributeError, OSError):
        return None


def wait_activate(handle) -> bool:
    """Blocks until the activate event is signalled. False on failure."""
    if not handle:
        return False
    return _kernel32().WaitForSingleObject(handle, _INFINITE) == _WAIT_OBJECT_0


def focus_existing() -> bool:
    """Called by a second instance: lets the running one take the foreground
    and signals it. False if the running instance could not be reached."""
    if not IS_WINDOWS:
        return False
    try:
        _user32().AllowSetForegroundWindow(wintypes.DWORD(_ASFW_ANY & 0xFFFFFFFF))
        k32 = _kernel32()
        handle = k32.OpenEventW(_EVENT_MODIFY_STATE | _SYNCHRONIZE, False,
                                ACTIVATE_EVENT_NAME)
        if not handle:
            return False
        try:
            return bool(k32.SetEvent(handle))
        finally:
            k32.CloseHandle(handle)
    except (AttributeError, OSError):
        return False


# ── WebView2 ─────────────────────────────────────────────────────

def webview2_version() -> str | None:
    """Installed Evergreen WebView2 Runtime version (machine or per-user)."""
    if not IS_WINDOWS:
        return None
    import winreg
    keys = [(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\" + WEBVIEW2_CLIENT),
            (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\" + WEBVIEW2_CLIENT),
            (winreg.HKEY_CURRENT_USER, "SOFTWARE\\" + WEBVIEW2_CLIENT)]
    for root, path in keys:
        try:
            with winreg.OpenKey(root, path) as key:
                version, _ = winreg.QueryValueEx(key, "pv")
        except OSError:
            continue
        if version and str(version) != "0.0.0.0":
            return str(version)
    return None


# ── monitors / placement ─────────────────────────────────────────

def _monitor_info(hmon) -> _MONITORINFO | None:
    if not hmon:
        return None
    info = _MONITORINFO()
    info.cbSize = ctypes.sizeof(_MONITORINFO)
    if not _user32().GetMonitorInfoW(hmon, ctypes.byref(info)):
        return None
    return info


def _monitor_at(x: int, y: int, flag: int) -> _MONITORINFO | None:
    try:
        return _monitor_info(_user32().MonitorFromPoint(wintypes.POINT(int(x), int(y)), flag))
    except (AttributeError, OSError):
        return None


def _rect(r) -> tuple[int, int, int, int]:
    return r.left, r.top, r.right, r.bottom


def system_scale() -> float:
    if not IS_WINDOWS:
        return 1.0
    try:
        dpi = _user32().GetDpiForSystem()
    except (AttributeError, OSError):
        return 1.0
    return dpi / 96.0 if dpi else 1.0


def _fit(w: int, h: int, x: int | None, y: int | None) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of a w×h window shrunk to its monitor's work
    area; centred on the primary work area when x/y are not given."""
    if x is None or y is None:
        info = _monitor_at(0, 0, _MONITOR_DEFAULTTOPRIMARY)
    else:
        info = _monitor_at(x + w // 2, y + 10, _MONITOR_DEFAULTTONEAREST)
    left, top, right, bottom = _rect(info.rcWork) if info else (0, 0, w + 40, h + 40)
    w = max(1, min(w, right - left - 40))
    h = max(1, min(h, bottom - top - 40))
    if x is None or y is None:
        x = left + (right - left - w) // 2
        y = top + (bottom - top - h) // 2
    x = max(left, min(x, right - w))
    y = max(top, min(y, bottom - h))
    return x, y, x + w, y + h


def default_rect() -> tuple[int, int, int, int]:
    s = system_scale()
    return _fit(round(DEFAULT_SIZE[0] * s), round(DEFAULT_SIZE[1] * s), None, None)


def restore_rect(placement: dict | None) -> tuple[tuple[int, int, int, int], bool]:
    """Screen rect + maximised flag to open with: the saved placement when its
    title bar is on a monitor connected now, else the centred default."""
    if placement:
        try:
            left, top = int(placement["left"]), int(placement["top"])
            w = int(placement["right"]) - left
            h = int(placement["bottom"]) - top
        except (KeyError, TypeError, ValueError):
            w = h = 0
        if w >= 100 and h >= 100 and _monitor_at(left + w // 2, top + 10,
                                                 _MONITOR_DEFAULTTONULL):
            return _fit(w, h, left, top), bool(placement.get("maximized"))
    return default_rect(), bool(placement and placement.get("maximized"))


def _work_offset(rect) -> tuple[int, int]:
    """Work area minus monitor origin: rcNormalPosition is in workspace
    coordinates, which differ from screen ones when the taskbar is top/left."""
    try:
        hmon = _user32().MonitorFromRect(ctypes.byref(rect), _MONITOR_DEFAULTTONEAREST)
    except (AttributeError, OSError):
        return 0, 0
    info = _monitor_info(hmon)
    if info is None:
        return 0, 0
    return (info.rcWork.left - info.rcMonitor.left, info.rcWork.top - info.rcMonitor.top)


def get_placement(hwnd) -> dict | None:
    """{left, top, right, bottom, maximized} in screen coordinates."""
    if not (IS_WINDOWS and hwnd):
        return None
    try:
        wp = _WINDOWPLACEMENT()
        wp.length = ctypes.sizeof(_WINDOWPLACEMENT)
        if not _user32().GetWindowPlacement(hwnd, ctypes.byref(wp)):
            return None
    except (AttributeError, OSError):
        return None
    r = wp.rcNormalPosition
    dx, dy = _work_offset(r)
    maximized = (wp.showCmd == _SW_SHOWMAXIMIZED
                 or (wp.showCmd == _SW_SHOWMINIMIZED
                     and bool(wp.flags & _WPF_RESTORETOMAXIMIZED)))
    return {"left": r.left + dx, "top": r.top + dy, "right": r.right + dx,
            "bottom": r.bottom + dy, "maximized": maximized}


def set_normal_rect(hwnd, rect: tuple[int, int, int, int]) -> bool:
    """Move the (still hidden) window's restored rect to *rect* (screen
    coords) without showing it."""
    if not (IS_WINDOWS and hwnd):
        return False
    try:
        r = wintypes.RECT(*rect)
        dx, dy = _work_offset(r)
        wp = _WINDOWPLACEMENT()
        wp.length = ctypes.sizeof(_WINDOWPLACEMENT)
        wp.flags = 0
        wp.showCmd = _SW_HIDE
        wp.ptMinPosition = wintypes.POINT(-1, -1)
        wp.ptMaxPosition = wintypes.POINT(-1, -1)
        wp.rcNormalPosition = wintypes.RECT(rect[0] - dx, rect[1] - dy,
                                            rect[2] - dx, rect[3] - dy)
        return bool(_user32().SetWindowPlacement(hwnd, ctypes.byref(wp)))
    except (AttributeError, OSError):
        return False


def bring_to_front(hwnd):
    if not (IS_WINDOWS and hwnd):
        return
    try:
        u = _user32()
        if u.IsIconic(hwnd):
            u.ShowWindow(hwnd, _SW_RESTORE)
        u.SetForegroundWindow(hwnd)
    except (AttributeError, OSError):
        pass


def window_state(hwnd) -> dict:
    """{visible, focused, maximized} for window:visibility."""
    if not (IS_WINDOWS and hwnd):
        return {"visible": True, "focused": True, "maximized": False}
    try:
        u = _user32()
        iconic = bool(u.IsIconic(hwnd))
        return {"visible": bool(u.IsWindowVisible(hwnd)) and not iconic,
                "focused": u.GetForegroundWindow() == hwnd,
                "maximized": bool(u.IsZoomed(hwnd))}
    except (AttributeError, OSError):
        return {"visible": True, "focused": True, "maximized": False}


# ── title bar ────────────────────────────────────────────────────

def _colorref(hex_color: str) -> int | None:
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return None
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return None
    return r | (g << 8) | (b << 16)


def set_title_bar(hwnd, dark: bool, caption: str | None = None, text: str | None = None):
    """Immersive dark mode plus caption/text colour (the colours need
    Windows 11; older builds ignore them)."""
    if not (IS_WINDOWS and hwnd):
        return
    try:
        dwm = ctypes.WinDLL("dwmapi")
    except OSError:
        return
    hwnd = wintypes.HWND(hwnd)

    def _set(attr: int, value: int):
        v = ctypes.c_int(value)
        try:
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
        except OSError:
            pass

    _set(_DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0)
    for attr, color in ((_DWMWA_CAPTION_COLOR, caption), (_DWMWA_TEXT_COLOR, text)):
        ref = _colorref(color) if color else None
        if ref is not None:
            _set(attr, ref)
