"""webapp.win32 window placement maths against a mocked user32 and a fake
monitor layout. No real Win32 calls are made, so this covers the coordinate
logic only: real mixed-DPI hardware is not exercised here.

Layout (screen coordinates, as a system-DPI-aware process sees them -- the
app calls SetProcessDPIAware via pywebview, so a monitor at another scale is
reported in virtualised coordinates; all APIs agree on that space):
  LEFT    -2400,-300 .. 0,1050    taskbar on its left   (work starts x=-2340)
  PRIMARY     0,0   .. 1920,1080  taskbar at the bottom (work ends y=1040)
  RIGHT    1920,0   .. 3200,720   taskbar at the top    (work starts y=40)
"""
import ctypes
from ctypes import wintypes

import pytest

from webapp import win32

LEFT, PRIMARY, RIGHT = 11, 22, 33
LAYOUT = {
    LEFT: ((-2400, -300, 0, 1050), (-2340, -300, 0, 1050)),
    PRIMARY: ((0, 0, 1920, 1080), (0, 0, 1920, 1040)),
    RIGHT: ((1920, 0, 3200, 720), (1920, 40, 3200, 720)),
}


def _contains(r, x, y):
    return r[0] <= x < r[2] and r[1] <= y < r[3]


def _dist(r, x, y):
    dx = max(r[0] - x, 0, x - (r[2] - 1))
    dy = max(r[1] - y, 0, y - (r[3] - 1))
    return dx * dx + dy * dy


class FakeUser32:
    def __init__(self, monitors=None, placement=None, dpi=96):
        self.monitors = dict(LAYOUT if monitors is None else monitors)
        self.placement = placement      # (flags, showCmd, (l, t, r, b)) in workspace coords
        self.set_calls = []
        self.dpi = dpi

    def _pick(self, hits, flag, x, y):
        if hits:
            return hits[0]
        if flag == win32._MONITOR_DEFAULTTONULL or not self.monitors:
            return None
        if flag == win32._MONITOR_DEFAULTTOPRIMARY:
            return PRIMARY if PRIMARY in self.monitors else None
        return min(self.monitors, key=lambda m: _dist(self.monitors[m][0], x, y))

    def MonitorFromPoint(self, pt, flag):
        hits = [m for m, (mon, _) in self.monitors.items() if _contains(mon, pt.x, pt.y)]
        return self._pick(hits, flag, pt.x, pt.y)

    def MonitorFromRect(self, pref, flag):
        r = pref._obj

        def area(mon):
            w = min(r.right, mon[2]) - max(r.left, mon[0])
            h = min(r.bottom, mon[3]) - max(r.top, mon[1])
            return w * h if w > 0 and h > 0 else 0
        best = sorted(((area(mon), m) for m, (mon, _) in self.monitors.items()), reverse=True)
        hits = [m for a, m in best if a > 0]
        return self._pick(hits, flag, (r.left + r.right) // 2, (r.top + r.bottom) // 2)

    def GetMonitorInfoW(self, hmon, pref):
        if hmon not in self.monitors:
            return 0
        mon, work = self.monitors[hmon]
        info = pref._obj
        info.rcMonitor = wintypes.RECT(*mon)
        info.rcWork = wintypes.RECT(*work)
        return 1

    def GetWindowPlacement(self, hwnd, pref):
        if self.placement is None:
            return 0
        flags, show, rect = self.placement
        wp = pref._obj
        wp.flags, wp.showCmd = flags, show
        wp.rcNormalPosition = wintypes.RECT(*rect)
        return 1

    def SetWindowPlacement(self, hwnd, pref):
        wp = pref._obj
        r = wp.rcNormalPosition
        self.set_calls.append((wp.showCmd, (r.left, r.top, r.right, r.bottom)))
        # what Windows would report back afterwards
        self.placement = (0, 1, (r.left, r.top, r.right, r.bottom))
        return 1

    def GetDpiForSystem(self):
        return self.dpi


@pytest.fixture()
def user32(monkeypatch):
    fake = FakeUser32()
    monkeypatch.setattr(win32, "IS_WINDOWS", True)
    monkeypatch.setitem(win32._dlls, "user32", fake)
    return fake


def _place(left, top, w=800, h=600, maximized=False):
    return {"left": left, "top": top, "right": left + w, "bottom": top + h,
            "maximized": maximized}


# ── get_placement: workspace -> screen ─────────────────────────────────────

def test_get_placement_primary_bottom_taskbar_is_identity(user32):
    user32.placement = (0, 1, (100, 100, 900, 700))
    assert win32.get_placement(1) == _place(100, 100)


def test_get_placement_top_taskbar_adds_offset(user32):
    # window at screen y=140 on RIGHT is workspace y=100 (taskbar is 40 tall)
    user32.placement = (0, 1, (2000, 100, 2800, 600))
    assert win32.get_placement(1) == _place(2000, 140, 800, 500)


def test_get_placement_negative_monitor_left_taskbar(user32):
    # LEFT's work area starts 60 px right of the monitor edge
    user32.placement = (0, 1, (-2060, -100, -1260, 500))
    assert win32.get_placement(1) == _place(-2000, -100)


@pytest.mark.parametrize("flags, show, maximized", [
    (0, win32._SW_SHOWMAXIMIZED, True),
    (win32._WPF_RESTORETOMAXIMIZED, win32._SW_SHOWMINIMIZED, True),
    (0, win32._SW_SHOWMINIMIZED, False),
    (0, 1, False),
])
def test_get_placement_maximized_flag(user32, flags, show, maximized):
    user32.placement = (flags, show, (100, 100, 900, 700))
    assert win32.get_placement(1)["maximized"] is maximized


def test_get_placement_failure_returns_none(user32):
    user32.placement = None
    assert win32.get_placement(1) is None
    assert win32.get_placement(0) is None


def test_get_placement_not_windows(monkeypatch):
    monkeypatch.setattr(win32, "IS_WINDOWS", False)
    assert win32.get_placement(1) is None
    assert win32.set_normal_rect(1, (0, 0, 10, 10)) is False


# ── set_normal_rect: screen -> workspace, and round trip ───────────────────

@pytest.mark.parametrize("rect, workspace", [
    ((100, 100, 900, 700), (100, 100, 900, 700)),          # PRIMARY
    ((2000, 140, 2800, 640), (2000, 100, 2800, 600)),      # RIGHT, top taskbar
    ((-2000, -100, -1200, 500), (-2060, -100, -1260, 500)),  # LEFT, left taskbar
])
def test_set_normal_rect_writes_workspace_coords_hidden(user32, rect, workspace):
    assert win32.set_normal_rect(1, rect) is True
    assert user32.set_calls == [(win32._SW_HIDE, workspace)]
    # and reading it back gives the same screen rect
    got = win32.get_placement(1)
    assert (got["left"], got["top"], got["right"], got["bottom"]) == rect


# ── restore_rect ─────────────────────────────────────────────────────────────

def test_restore_keeps_position_on_each_monitor(user32):
    for p in (_place(100, 100), _place(2000, 100, 800, 500), _place(-2000, -200)):
        rect, maxed = win32.restore_rect(p)
        assert rect == (p["left"], p["top"], p["right"], p["bottom"]) and not maxed


def test_restore_monitor_removed_falls_back_to_centred_default(user32):
    saved = _place(-2000, -200, maximized=True)
    del user32.monitors[LEFT]
    rect, maxed = win32.restore_rect(saved)
    assert maxed is True                      # still opens maximised, on primary
    w, h = win32.DEFAULT_SIZE
    assert rect == ((1920 - w) // 2, (1040 - h) // 2, (1920 - w) // 2 + w, (1040 - h) // 2 + h)


def test_restore_title_bar_off_every_monitor_falls_back(user32):
    # below PRIMARY's bottom edge: the title bar point is on no monitor
    rect, _ = win32.restore_rect(_place(300, 1200))
    assert rect == win32.default_rect()


def test_restore_title_bar_above_top_falls_back(user32):
    rect, _ = win32.restore_rect(_place(300, -50))
    assert rect == win32.default_rect()


def test_restore_partly_off_right_edge_is_clamped_into_work_area(user32):
    # title bar centre is on RIGHT, but the window runs past its right edge
    rect, _ = win32.restore_rect(_place(2700, 100, 800, 500))
    assert rect == (3200 - 800, 100, 3200, 600)


def test_restore_under_top_taskbar_is_pushed_down(user32):
    rect, _ = win32.restore_rect(_place(2000, 5, 800, 500))
    assert rect[1] == 40 and rect[3] == 540


def test_restore_under_left_taskbar_negative_coords(user32):
    rect, _ = win32.restore_rect(_place(-2390, 0))
    assert rect == (-2340, 0, -2340 + 800, 600)


def test_restore_oversized_window_shrinks_to_its_monitor(user32):
    # a big window saved on the large LEFT monitor, now restored on the small RIGHT one
    rect, _ = win32.restore_rect(_place(1950, 50, 2000, 1300))
    l, t, r, b = rect
    assert (r - l, b - t) == (1280 - 40, 680 - 40)
    assert 1920 <= l and r <= 3200 and 40 <= t and b <= 720


def test_restore_window_straddling_monitors_uses_title_bar_monitor(user32):
    # title bar centre at x=-100 is on LEFT even though the window spans into PRIMARY
    rect, _ = win32.restore_rect(_place(-500, 100, 800, 600))
    assert rect == (-800, 100, 0, 700)


@pytest.mark.parametrize("bad", [
    None, {}, {"left": "x"}, _place(0, 0, 50, 50),
    {"left": 0, "top": 0, "right": None, "bottom": 10},
])
def test_restore_garbage_placement_uses_default(user32, bad):
    rect, maxed = win32.restore_rect(bad)
    assert rect == win32.default_rect() and maxed is False


def test_default_rect_scales_with_system_dpi_and_fits(user32):
    user32.dpi = 144                           # 150 %
    l, t, r, b = win32.default_rect()
    assert r - l == round(win32.DEFAULT_SIZE[0] * 1.5)
    assert b - t == 1040 - 40                  # 1140 tall doesn't fit, shrunk
    assert t == 20 and l == (1920 - (r - l)) // 2


def test_default_rect_without_any_monitor_info(user32):
    user32.monitors.clear()
    l, t, r, b = win32.default_rect()
    assert (r - l, b - t) == win32.DEFAULT_SIZE and (l, t) == (20, 20)


def test_work_offset_when_monitor_lookup_fails(user32):
    user32.monitors.clear()
    assert win32._work_offset(wintypes.RECT(0, 0, 10, 10)) == (0, 0)
    user32.placement = (0, 1, (10, 20, 900, 700))
    assert win32.get_placement(1)["left"] == 10


def test_saved_placement_round_trips_through_restore(user32):
    """save on RIGHT (top taskbar) -> restore -> SetWindowPlacement -> save again."""
    user32.placement = (0, 1, (2100, 60, 2900, 560))
    first = win32.get_placement(1)
    rect, _ = win32.restore_rect(first)
    win32.set_normal_rect(1, rect)
    assert win32.get_placement(1) == first
