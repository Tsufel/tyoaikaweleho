"""Contract tests for webapp.api.Api — the js_api object pywebview exposes.
Uses a fake window; no pywebview window is created and no real data is
touched (tmp_storage/tmp_timer)."""
import inspect
import json
import os
import re
from datetime import datetime

import pytest

import storage
from services import dlc
from timer import WorkTimer
from webapp import results as R
from webapp.api import Api
from webapp.controller import ShiftController
from webapp.events import CHANNEL, EventBus

TYPES_TS = os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "lib",
                        "api", "types.ts")


class FakeWindow:
    def __init__(self):
        self.dialogs: list = []
        self.dialog_calls: list = []
        self.scripts: list[str] = []

    def create_file_dialog(self, dialog_type, directory="", allow_multiple=False,
                           save_filename="", file_types=()):
        self.dialog_calls.append((dialog_type, directory, allow_multiple,
                                  save_filename, tuple(file_types)))
        return self.dialogs.pop(0) if self.dialogs else None

    def evaluate_js(self, script):
        self.scripts.append(script)


class FakeShell:
    def __init__(self, window):
        self.window = window
        self.calls: list = []

    def reveal(self):
        self.calls.append("reveal")

    def save_placement(self):
        self.calls.append("save_placement")

    def apply_theme(self, appearance, dark):
        self.calls.append(("theme", appearance, dark))

    def set_close_guard(self, enabled):
        self.calls.append(("guard", enabled))

    def quit(self):
        self.calls.append("quit")


class RecordingBus:
    def __init__(self):
        self.events: list = []

    def emit(self, name, payload=None):
        json.dumps(payload, allow_nan=False)
        self.events.append((name, payload))


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture()
def offline(monkeypatch):
    """No network, no DLC file changes, no shell launches."""
    import updater
    monkeypatch.setattr(updater, "fetch_latest_release", lambda *a, **k: None)
    monkeypatch.setattr(updater, "fetch_latest_dlc_version", lambda *a, **k: "0.0.0")
    monkeypatch.setattr(updater, "apply_update",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(dlc, "install", lambda *a, **k: True)
    monkeypatch.setattr(dlc, "remove", lambda *a, **k: None)
    monkeypatch.setattr(dlc, "reload", lambda *a, **k: {})
    monkeypatch.setattr(os, "startfile", lambda *a, **k: None, raising=False)


@pytest.fixture()
def rig(tmp_storage, tmp_timer, offline):
    window = FakeWindow()
    shell = FakeShell(window)
    bus = RecordingBus()
    clock = Clock(datetime(2026, 9, 23, 10, 0, 0))
    ctrl = ShiftController(timer=WorkTimer(), clock=clock)
    api = Api(ctrl, bus, shell, version="2.0.0", frozen=False, dev=True)
    return api, window, shell, bus, tmp_storage


def _public(api):
    return {n: getattr(api, n) for n in dir(api) if not n.startswith("_")}


def _contract_methods() -> set[str]:
    with open(TYPES_TS, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"export interface Api \{(.*?)\n\}", src, re.S)
    assert m, "Api interface not found in types.ts"
    return set(re.findall(r"^\s+(\w+)\(", m.group(1), re.M))


def _check(result):
    assert isinstance(result, dict), result
    json.dumps(result, allow_nan=False)
    assert isinstance(result.get("ok"), bool)
    assert isinstance(result.get("status"), str)
    return result


def test_public_attributes_are_all_callable(rig):
    api = rig[0]
    public = _public(api)
    assert public
    for name, attr in public.items():
        assert callable(attr), f"public non-callable attribute: {name}"
        assert inspect.ismethod(attr), f"{name} is not a bound method"


@pytest.mark.skipif(not os.path.isfile(TYPES_TS), reason="frontend not present")
def test_public_methods_match_types_ts(rig):
    assert set(_public(rig[0])) == _contract_methods()


def test_main_args():
    import main
    assert main._parse_args(["--dev"]).dev == main.DEV_URL
    assert main._parse_args(["--dev", "http://localhost:5174/"]).dev == "http://localhost:5174/"
    a = main._parse_args(["--smoke-test"])
    assert a.smoke_test and a.dev is None
    assert not hasattr(a, "legacy")
    assert main.DATA_DIR_ENV == storage.DATA_DIR_ENV


def test_every_method_returns_json(rig):
    api, window, shell, bus, tmp = rig
    calls = [
        ("bootstrap", ()), ("frontend_ready", ()), ("set_close_guard", (True,)),
        ("set_theme", ("Dark", True)), ("set_theme", ("Nope", True)),
        ("log_client_error", ("boom", "at x")), ("open_shifts_file", ()),
        ("get_timer", ()), ("timer_start", ("now", None, None, None)),
        ("timer_stop", ("button", None)), ("timer_discard", (None,)),
        ("recovery_resolve", ("discard", None, None)),
        ("list_month", (2026, 9)), ("get_entry", ("missing",)),
        ("save_entry", ({"date": "2026-09-01", "time_in": "08:00", "time_out": "16:00",
                         "job_shift": "Sales"}, None)),
        ("update_entry_field", ("missing", "time_in", "09:00", None)),
        ("delete_entry", ("missing", None)), ("restore_entry", ({"bad": 1},)),
        ("get_settings", ()), ("save_settings", ({},)), ("save_ui_prefs", ({"lulz": True},)),
        ("add_job_shift", ("Night",)),
        ("get_stats", ("2026-09-01", "2026-09-30", "day")),
        ("export_month", (2026, 9)), ("import_excel", ()), ("ocr_pick_and_extract", ()),
        ("ocr_save", ([],)), ("check_updates", ()), ("install_update", ()),
        ("get_dlc_status", ()), ("dlc_install", ()), ("dlc_remove", (None,)),
        ("close_app", (None,)),
    ]
    called = set()
    for name, args in calls:
        _check(getattr(api, name)(*args))
        called.add(name)
    assert called == set(_public(api))
    for name, payload in bus.events:
        json.dumps(payload, allow_nan=False)


def test_js_undefined_args_arrive_as_none(rig):
    api = rig[0]
    _check(api.timer_stop(None, None))
    _check(api.get_stats("2026-09-01", "2026-09-30", None))


def test_guarded_logs_and_returns_internal_error(rig, monkeypatch):
    api, *_rest, tmp = rig
    monkeypatch.setattr(api._c, "list_month", lambda *a: 1 / 0)
    res = _check(api.list_month(2026, 9))
    assert res["ok"] is False and res["status"] == "error"
    assert res["error"]["code"] == "internal"
    assert res["message"]
    with open(storage.ERROR_LOG, encoding="utf-8") as f:
        assert "ZeroDivisionError" in f.read()


def test_wrong_arity_is_guarded(rig):
    res = _check(rig[0].list_month(2026))
    assert res["error"]["code"] == "internal"


def test_frontend_ready_reveals(rig):
    api, _w, shell, *_ = rig
    _check(api.frontend_ready())
    assert shell.calls == ["reveal"]


def test_close_app_idle_quits_after_saving_placement(rig):
    api, _w, shell, *_ = rig
    res = _check(api.close_app())
    assert res["quit"] is True
    assert shell.calls == ["save_placement", "quit"]


def test_close_app_running_needs_confirm_and_does_not_quit(rig):
    api, _w, shell, *_ = rig
    _check(api.timer_start("now"))
    res = _check(api.close_app())
    assert res["status"] == "needs_confirm"
    assert "quit" not in shell.calls


def test_export_appends_xlsx_and_saves(rig):
    api, window, _s, _b, tmp = rig
    target = tmp / "out"
    window.dialogs.append((str(target),))
    res = _check(api.export_month(2026, 9))
    assert res["status"] == "saved"
    assert res["path"].endswith("out.xlsx")
    assert os.path.isfile(res["path"])
    kind, _dir, multiple, name, types = window.dialog_calls[0]
    assert kind == 30 and not multiple
    assert name == "Hours September 2026.xlsx"


def test_dialog_cancel_is_cancelled(rig):
    api, window, *_ = rig
    assert _check(api.export_month(2026, 9))["status"] == "cancelled"
    assert _check(api.import_excel())["status"] == "cancelled"
    assert window.dialog_calls[1][2] is True      # import allows multiple


def test_file_types_are_valid_for_pywebview(rig):
    util = pytest.importorskip("webview.util")
    from webapp import api as api_mod
    for ft in api_mod._EXCEL_TYPES + api_mod._EXPORT_TYPES + api_mod._IMAGE_TYPES:
        util.parse_file_type(ft)


def test_ocr_without_dlc_skips_dialog(rig, monkeypatch):
    api, window, *_ = rig
    monkeypatch.setattr(dlc, "load_status",
                        lambda: {"state": "missing", "version": None, "error": None})
    res = _check(api.ocr_pick_and_extract())
    assert res["error"]["code"] == "dlc_unavailable"
    assert window.dialog_calls == []


def test_install_update_from_source_is_not_frozen(rig):
    api, _w, shell, bus, _t = rig
    res = _check(api.install_update())
    assert res["error"]["code"] == "not_frozen"
    assert "save_placement" not in shell.calls
    assert not any(n.startswith("update:") for n, _ in bus.events)


def test_install_update_frozen_saves_placement_and_reports(rig):
    api, _w, shell, bus, _t = rig
    api._frozen = True
    api._c.remember_update("9.9.9", "https://example.invalid/x.exe", None)
    res = _check(api.install_update())
    assert res["error"]["code"] == "update_failed"
    assert shell.calls[0] == "save_placement"
    names = [n for n, _ in bus.events]
    assert names == ["update:installing", "update:failed"]
    assert bus.events[0][1] == {"version": "9.9.9"}


def test_dlc_install_emits_status(rig):
    api, _w, _s, bus, _t = rig
    _check(api.dlc_install())
    assert [n for n, _ in bus.events] == ["dlc:status"]


def test_dlc_remove_needs_confirm_without_event(rig):
    api, _w, _s, bus, _t = rig
    res = _check(api.dlc_remove())
    assert res["status"] == "needs_confirm"
    assert bus.events == []


def test_set_theme_and_close_guard_reach_shell(rig):
    api, _w, shell, *_ = rig
    _check(api.set_theme("Light", False))
    _check(api.set_close_guard(1))
    assert shell.calls == [("theme", "Light", False), ("guard", True)]


def test_log_client_error_is_truncated_and_tagged(rig):
    api = rig[0]
    _check(api.log_client_error("x" * 50000))
    with open(storage.ERROR_LOG, encoding="utf-8") as f:
        text = f.read()
    assert "[frontend]" in text and len(text) < 20000


# ── EventBus ─────────────────────────────────────────────────────

def test_event_script_shape():
    script = EventBus.script("timer:changed", {"label": "Työ €"})
    assert f'new CustomEvent("{CHANNEL}"' in script
    assert '"name": "timer:changed"' in script and '"payload"' in script
    assert script.isascii()
    detail = json.loads(script[script.index("detail: ") + 8:script.rindex("}));")])
    assert detail == {"name": "timer:changed", "payload": {"label": "Työ €"}}


def test_event_bus_waits_for_ready_and_keeps_order(tmp_storage):
    window = FakeWindow()
    bus = EventBus(window)
    bus.start()
    bus.emit("a", {"n": 1})
    bus.emit("b")
    import time
    time.sleep(0.05)
    assert window.scripts == []
    bus.set_ready()
    deadline = time.time() + 2
    while len(window.scripts) < 2 and time.time() < deadline:
        time.sleep(0.01)
    bus.close()
    assert ['"name": "a"' in window.scripts[0], '"name": "b"' in window.scripts[1]] == [True, True]


def test_event_bus_drops_unserialisable_payload(tmp_storage):
    window = FakeWindow()
    bus = EventBus(window)
    bus.set_ready()
    bus.start()
    bus.emit("bad", {"x": object()})
    bus.emit("good")
    import time
    deadline = time.time() + 2
    while not window.scripts and time.time() < deadline:
        time.sleep(0.01)
    bus.close()
    assert len(window.scripts) == 1 and '"good"' in window.scripts[0]
