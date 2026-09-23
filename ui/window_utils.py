"""Window placement and modal-dialog plumbing shared by every dialog."""
import ctypes
import os
import re
import sys
import tkinter as tk
from ctypes import wintypes

from customtkinter import AppearanceModeTracker

from utils import get_app_dir

_MONITOR_DEFAULTTONULL = 0
_MONITOR_DEFAULTTONEAREST = 2

# CTkToplevel hides and re-shows itself 5 ms after creation (and again after
# resizable()), then hands focus back to whatever had it before — usually
# the main window. Take focus after that dance, twice in case it repeats.
_FOCUS_DELAYS_MS = (30, 150)
# CTkToplevel puts its own icon on at 200 ms
_ICON_DELAY_MS = 250
# A theme switch hides and re-shows every window; CTk's own re-show runs 5 ms
# after the switch
_RESHOW_DELAY_MS = 50


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


_user32 = None


def _get_user32():
    global _user32
    if _user32 is None:
        # private handle, so these argtypes don't leak into other ctypes users
        dll = ctypes.WinDLL("user32")
        dll.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        dll.MonitorFromPoint.restype = ctypes.c_void_p
        dll.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MONITORINFO)]
        dll.GetMonitorInfoW.restype = wintypes.BOOL
        _user32 = dll
    return _user32


def _monitor_work_area(x: int, y: int, flag: int) -> tuple[int, int, int, int] | None:
    """(left, top, right, bottom) of the work area (screen minus taskbar) of
    the monitor at (x, y). None if there's no monitor there (with
    _MONITOR_DEFAULTTONULL) or this isn't Windows."""
    if sys.platform != "win32":
        return None
    try:
        user32 = _get_user32()
        hmon = user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), flag)
        if not hmon:
            return None
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            return None
        r = info.rcWork
        return r.left, r.top, r.right, r.bottom
    except (AttributeError, OSError):
        return None


def work_area(win: tk.Misc, x: int, y: int) -> tuple[int, int, int, int]:
    """Work area of the monitor nearest (x, y); the whole primary screen if
    that can't be determined."""
    area = _monitor_work_area(x, y, _MONITOR_DEFAULTTONEAREST)
    if area is None:
        area = (0, 0, win.winfo_screenwidth(), win.winfo_screenheight())
    return area


def clamp_to_workarea(win: tk.Misc, x: int, y: int, w: int, h: int) -> tuple[int, int]:
    """Move a w×h window at (x, y) the least distance needed to be fully
    inside its monitor's work area."""
    left, top, right, bottom = work_area(win, x + w // 2, y + h // 2)
    x = max(left, min(x, right - w))
    y = max(top, min(y, bottom - h))
    return x, y


_GEOMETRY = re.compile(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)")


def parse_geometry(geom: str) -> tuple[int, int, int, int] | None:
    """'860x700+100+50' → (860, 700, 100, 50). None for anything else."""
    m = _GEOMETRY.fullmatch(geom)
    return tuple(int(g) for g in m.groups()) if m else None


def geometry_on_screen(win: tk.Misc, geom: str) -> bool:
    """True if a window at *geom* would have its title bar on a monitor that
    is connected now — a saved position from a since-unplugged screen isn't."""
    parsed = parse_geometry(geom)
    if parsed is None:
        return False
    w, h, x, y = parsed
    if w < 100 or h < 100:
        return False
    px, py = x + w // 2, y + 10          # top-centre, i.e. the title bar
    area = _monitor_work_area(px, py, _MONITOR_DEFAULTTONULL)
    if area is None and sys.platform == "win32":
        return False
    if area is None:
        area = (0, 0, win.winfo_screenwidth(), win.winfo_screenheight())
    left, top, right, bottom = area
    return left <= px < right and top <= py < bottom


def fit_geometry(win: tk.Misc, w: int, h: int, x: int | None = None,
                 y: int | None = None) -> str:
    """Tk geometry for a w×h window shrunk to fit its monitor's work area;
    centred on the primary work area when x/y are not given."""
    if x is None or y is None:
        left, top, right, bottom = work_area(win, 0, 0)
    else:
        left, top, right, bottom = work_area(win, x + w // 2, y + 10)
    w = min(w, right - left - 40)
    h = min(h, bottom - top - 40)
    if x is None or y is None:
        x = left + (right - left - w) // 2
        y = top + (bottom - top - h) // 2
    x = max(left, min(x, right - w))
    y = max(top, min(y, bottom - h))
    return f"{w}x{h}+{x}+{y}"


def app_icon_path() -> str | None:
    path = os.path.join(get_app_dir(), "icon.ico")
    return path if os.path.exists(path) else None


def _set_app_icon(win: tk.Wm):
    path = app_icon_path()
    if path is None:
        return
    try:
        win.iconbitmap(path)
    except tk.TclError:
        pass


def _requested_size(win: tk.Toplevel) -> tuple[int, int]:
    """Size the window will have once mapped: the explicit geometry() size if
    one was set, else what its contents ask for."""
    win.update_idletasks()
    parsed = re.match(r"(\d+)x(\d+)", win.wm_geometry())
    w, h = (int(parsed.group(1)), int(parsed.group(2))) if parsed else (0, 0)
    # an unset CTkToplevel reports its 200×200 placeholder
    if getattr(win, "_current_width", None) == 200 and getattr(win, "_current_height", None) == 200:
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    return max(w, win.winfo_reqwidth()), max(h, win.winfo_reqheight())


def center_on(win: tk.Toplevel, parent: tk.Misc):
    """Centre *win* over *parent* (or the screen if parent isn't shown),
    kept inside the monitor's work area."""
    w, h = _requested_size(win)
    top = parent.winfo_toplevel()
    if top.winfo_viewable():
        cx = top.winfo_rootx() + top.winfo_width() // 2
        cy = top.winfo_rooty() + top.winfo_height() // 2
    else:
        left, t, right, bottom = work_area(win, 0, 0)
        cx, cy = (left + right) // 2, (t + bottom) // 2
    x, y = clamp_to_workarea(win, cx - w // 2, cy - h // 2, w, h)
    # position only — raw Tk, so CTk doesn't rescale or override the size
    win.wm_geometry(f"+{x}+{y}")


def prepare_dialog(win: tk.Toplevel, parent: tk.Misc, focus: tk.Misc | None = None,
                   modal: bool = True, center: bool = True):
    """Turn a freshly built Toplevel into a proper dialog of *parent*: kept in
    front of it, centred on it, with the app icon, keyboard focus on *focus*
    (default: the dialog) and, if *modal*, the input grab.

    Tk grabs don't stack, so a dialog opened from another dialog takes the
    grab away from it; the previous holder gets it back when *win* closes.
    Call this last in the dialog's __init__, after its widgets are built.
    """
    top = parent.winfo_toplevel()
    # a transient of a hidden window (the app behind its splash) stays hidden
    if top.winfo_viewable():
        win.transient(top)
    if center:
        center_on(win, parent)
    win.after(_ICON_DELAY_MS, lambda: win.winfo_exists() and _set_app_icon(win))

    prev_grab = win.grab_current()
    target = focus or win

    def take_focus():
        if not win.winfo_exists():
            return
        try:
            # CTk's hide/show can drop the grab; don't take one a child
            # dialog of ours already holds
            if modal and win.grab_current() is None:
                win.grab_set()
            current = win.focus_get()
            if current is None or current.winfo_toplevel() is not win:
                win.lift()
                win.focus_force()
                target.focus_set()
        except tk.TclError:
            pass

    if modal:
        try:
            win.grab_set()
        except tk.TclError:
            pass  # not mappable yet; take_focus retries
    for delay in _FOCUS_DELAYS_MS:
        win.after(delay, take_focus)

    def reshow():
        try:
            if (win.winfo_exists() and win.state() == "withdrawn"
                    and top.state() in ("normal", "zoomed")):
                win.deiconify()
                take_focus()
        except tk.TclError:
            pass

    def on_theme_change(_mode):
        # Hiding the main window for its title-bar recolour takes its
        # transient dialogs along, and CTk then restores them as "withdrawn",
        # leaving an invisible dialog that still holds the grab
        try:
            win.after(_RESHOW_DELAY_MS, reshow)
        except tk.TclError:
            pass

    AppearanceModeTracker.add(on_theme_change)

    def restore_grab(event):
        if event.widget is not win:
            return
        AppearanceModeTracker.remove(on_theme_change)
        if prev_grab is None or prev_grab is win:
            return
        try:
            if prev_grab.winfo_exists():
                prev_grab.grab_set()
        except tk.TclError:
            pass

    win.bind("<Destroy>", restore_grab, add="+")
