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
