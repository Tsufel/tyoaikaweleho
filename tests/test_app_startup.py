"""webapp.app startup reads data.json before the window exists: an
unreadable file must not crash it (the UI reports the problem instead)."""
import pytest

import storage
import webapp.app as app


def _corrupt(*a, **k):
    raise storage.DataFileCorrupt("damaged")


def _locked(*a, **k):
    raise PermissionError(13, "locked")


@pytest.mark.parametrize("fail", [_corrupt, _locked])
def test_shell_opens_when_placement_unreadable(tmp_storage, monkeypatch, fail):
    monkeypatch.setattr(storage, "get_window_placement", fail)
    shell = app._Shell(controller=None, bus=None, smoke=False, dark=False)
    assert shell._placement is None
    assert "window placement unreadable" in (tmp_storage / "error.log").read_text(encoding="utf-8")


def test_shell_reads_placement(tmp_storage, monkeypatch):
    monkeypatch.setattr(storage, "get_window_placement", lambda: {"x": 1})
    assert app._Shell(controller=None, bus=None, smoke=False, dark=False)._placement == {"x": 1}


# ── window title ticker ──────────────────────────────────────────────────────

def test_title_for_shows_elapsed_while_running():
    from datetime import datetime
    now = datetime(2026, 9, 23, 10, 0, 0)
    assert app.title_for(None, now) == app.TITLE
    assert app.title_for(datetime(2026, 9, 23, 8, 55, 30), now) == f"1:04 · {app.TITLE}"
    assert app.title_for(datetime(2026, 9, 22, 9, 0, 0), now) == f"25:00 · {app.TITLE}"
    assert app.title_for(datetime(2026, 9, 23, 10, 5, 0), now) == f"0:00 · {app.TITLE}"


class _Ctrl:
    def __init__(self, start):
        self.start = start

    def running_start(self):
        return self.start


class _Win:
    def __init__(self):
        self.titles = []

    def set_title(self, t):
        self.titles.append(t)


def test_title_loop_sets_changes_only_and_stops(monkeypatch):
    from datetime import datetime
    now = datetime(2026, 9, 23, 10, 0, 0)
    ctrl = _Ctrl(datetime(2026, 9, 23, 9, 0, 0))
    shell = app._Shell(controller=ctrl, bus=None, smoke=True, dark=False)
    shell.window = _Win()
    ticks = iter([False, False, True])
    waits = []

    def wait(timeout):
        waits.append(timeout)
        if len(waits) == 2:
            ctrl.start = None  # shift stopped
        return next(ticks)

    monkeypatch.setattr(shell._title_stop, "wait", wait)
    shell.title_loop(clock=lambda: now)
    assert shell.window.titles == [f"1:00 · {app.TITLE}", app.TITLE]
    assert waits == [app.TITLE_TICK_S] * 3


def test_title_loop_logs_and_ends_on_failure(tmp_storage):
    class Broken:
        def running_start(self):
            raise RuntimeError("boom")

    shell = app._Shell(controller=Broken(), bus=None, smoke=True, dark=False)
    shell.window = _Win()
    shell.title_loop()
    assert "window title" in (tmp_storage / "error.log").read_text(encoding="utf-8")
