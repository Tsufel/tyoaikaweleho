"""Paths that only run in the wild: the startup update/DLC checks, a page that
stops answering evaluate_js, and a DLC install that cannot be written."""
import os
import threading
import time
from datetime import datetime

import pytest

import storage
import updater
from services import dlc
from timer import WorkTimer
from webapp.api import Api
from webapp.controller import ShiftController
from webapp.events import EventBus


class _Bus:
    def __init__(self):
        self.events: list = []

    def emit(self, name, payload=None):
        self.events.append((name, payload))


@pytest.fixture()
def api_bus(tmp_storage, tmp_timer, monkeypatch):
    ctrl = ShiftController(timer=WorkTimer(), clock=lambda: datetime(2026, 9, 23, 10, 0))
    bus = _Bus()
    api = Api(ctrl, bus, None, version="2.0.0", frozen=False, dev=True)
    return api, ctrl, bus


def _sync_checks(monkeypatch, app=None, dlc_version=None):
    """Run the background checks inline, answering as the given releases."""
    seen = {}

    def check_app(current, cb):
        seen["app"] = current
        if app:
            cb(*app)

    def check_dlc(current, cb):
        seen["dlc"] = current
        if dlc_version:
            cb(dlc_version)

    monkeypatch.setattr(updater, "check_for_update", check_app)
    monkeypatch.setattr(updater, "check_for_dlc_update", check_dlc)
    return seen


def _dlc_state(monkeypatch, state, version=None):
    st = {"state": state, "version": version, "error": None}
    monkeypatch.setattr(dlc, "load_status", lambda: dict(st))


# ── startup checks ───────────────────────────────────────────────

def test_update_found_at_startup_is_remembered_and_announced(api_bus, monkeypatch):
    api, ctrl, bus = api_bus
    _dlc_state(monkeypatch, "missing")
    seen = _sync_checks(monkeypatch, app=("2.1.0", "https://x/Setup.exe", "https://x/sha"))
    api._start_background_checks()
    assert seen == {"app": "2.0.0"}  # no DLC installed: no DLC check
    assert ctrl.pending_update == ("2.1.0", "https://x/Setup.exe", "https://x/sha")
    assert bus.events == [("update:available", {"version": "2.1.0", "current": "2.0.0"})]


def test_dlc_update_is_checked_only_when_the_dlc_loads(api_bus, monkeypatch):
    api, ctrl, bus = api_bus
    for state in ("missing", "incompatible"):
        _dlc_state(monkeypatch, state, "1.0.0")
        seen = _sync_checks(monkeypatch, dlc_version="1.1.0")
        api._start_background_checks()
        assert "dlc" not in seen and bus.events == []


def test_dlc_update_found_emits_update_then_status(api_bus, monkeypatch):
    api, ctrl, bus = api_bus
    _dlc_state(monkeypatch, "ok", "1.0.0")
    seen = _sync_checks(monkeypatch, dlc_version="1.1.0")
    api._start_background_checks()
    assert seen["dlc"] == "1.0.0"
    assert ctrl.dlc_update_version == "1.1.0"
    names = [n for n, _ in bus.events]
    assert names == ["dlc:update", "dlc:status"]
    assert bus.events[0][1] == {"version": "1.1.0"}
    assert bus.events[1][1]["update_version"] == "1.1.0"


def test_dlc_without_version_is_checked_as_0_0_0(api_bus, monkeypatch):
    api, _, _ = api_bus
    _dlc_state(monkeypatch, "ok", None)
    seen = _sync_checks(monkeypatch)
    api._start_background_checks()
    assert seen["dlc"] == "0.0.0"


def test_broken_dlc_status_does_not_stop_startup(api_bus, monkeypatch):
    api, _, bus = api_bus

    def boom():
        raise RuntimeError("bad dlc")

    monkeypatch.setattr(dlc, "load_status", boom)
    seen = _sync_checks(monkeypatch, app=("2.1.0", "u", None))
    api._start_background_checks()
    assert "dlc" not in seen
    assert [n for n, _ in bus.events] == ["update:available"]


def test_dlc_status_failure_after_update_is_logged(api_bus, monkeypatch):
    api, ctrl, bus = api_bus
    _dlc_state(monkeypatch, "ok", "1.0.0")
    _sync_checks(monkeypatch, dlc_version="1.1.0")

    def boom():
        raise RuntimeError("status exploded")

    monkeypatch.setattr(ctrl, "dlc_status", boom)
    api._start_background_checks()
    assert [n for n, _ in bus.events] == ["dlc:update"]
    with open(storage.ERROR_LOG, encoding="utf-8") as f:
        assert "[api] dlc status" in f.read()


# ── event pump ───────────────────────────────────────────────────

def _wait(cond, timeout=3.0):
    deadline = time.monotonic() + timeout
    while not cond() and time.monotonic() < deadline:
        time.sleep(0.01)
    return cond()


def test_a_failed_delivery_is_logged_and_the_next_event_still_goes(tmp_storage):
    class Flaky:
        def __init__(self):
            self.scripts: list[str] = []
            self.calls = 0

        def evaluate_js(self, script):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("renderer gone")
            self.scripts.append(script)

    window = Flaky()
    bus = EventBus(window)
    bus.set_ready()
    bus.start()
    try:
        bus.emit("first")
        bus.emit("second")
        assert _wait(lambda: window.scripts)
    finally:
        bus.close()
    assert '"second"' in window.scripts[0]
    with open(storage.ERROR_LOG, encoding="utf-8") as f:
        assert "[events] could not deliver first" in f.read()


def test_stalled_while_evaluate_js_blocks(tmp_storage):
    entered, release = threading.Event(), threading.Event()

    class Hung:
        def evaluate_js(self, script):
            entered.set()
            release.wait(5)

    bus = EventBus(Hung())
    assert bus.stalled(0) is False  # nothing in flight
    bus.set_ready()
    bus.start()
    try:
        bus.emit("x")
        assert entered.wait(3)
        time.sleep(0.03)
        assert bus.stalled(0.01) is True
        assert bus.stalled(60) is False
    finally:
        release.set()
    assert _wait(lambda: not bus.stalled(0))
    bus.close()


# ── DLC install ──────────────────────────────────────────────────

def test_dlc_install_that_cannot_be_moved_into_place_leaves_no_temp_file(
        monkeypatch, tmp_path):
    dest = tmp_path / "image_ocr.py"
    dest.write_bytes(b"# previous dlc\n")
    monkeypatch.setattr(dlc, "_check_repo_configured", lambda: "Tsufel/tyoaikaweleho")
    monkeypatch.setattr(dlc, "_fetch", lambda url, repo: b"# new dlc\n")
    monkeypatch.setattr(dlc, "fetch_expected_hash", lambda repo: None)
    monkeypatch.setattr(dlc, "dlc_path", lambda: str(dest))

    def locked(src, dst):
        raise PermissionError(13, "file in use", dst)

    monkeypatch.setattr(os, "replace", locked)
    with pytest.raises(dlc.DlcError, match="Could not write DLC file"):
        dlc.install()
    assert os.listdir(tmp_path) == ["image_ocr.py"]
    assert dest.read_bytes() == b"# previous dlc\n"
