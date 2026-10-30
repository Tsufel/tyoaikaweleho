"""Tests for webapp.controller — the v1.3 UI rules behind the v2 JS API."""
import json
import os
from datetime import datetime, timedelta

import pytest

import storage
import timer as tm
from services import dlc
from timer import WorkTimer
from webapp.controller import ShiftController


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self):
        return self.now


T0 = datetime(2026, 9, 23, 10, 0, 0)


@pytest.fixture()
def env(tmp_storage, tmp_timer):
    clock = Clock(T0)
    return ShiftController(timer=WorkTimer(), clock=clock), clock


def _answer(kind, choice, token=None):
    a = {"kind": kind, "choice": choice}
    if token is not None:
        a["token"] = token
    return [a]


def _started(ctrl, clock, start=T0, job="Sales"):
    clock.now = start
    r = ctrl.timer_start("now", job_shift=job)
    assert r["status"] == "ok" and r["timer"]["running"]
    return r["timer"]["start_iso"]


def _fail(*a, **k):
    raise OSError("locked")


def _add(date="2026-09-23", t_in="09:00", t_out="17:00", job="Sales", id_=None):
    e = storage.WorkEntry(id=id_ or storage.new_entry_id(), date=date, job_shift=job,
                          time_in=t_in, time_out=t_out)
    storage.save_entry(e)
    return e


# ── start ────────────────────────────────────────────────────────────────────

def test_start_now(env, tmp_timer):
    ctrl, clock = env
    clock.now = T0.replace(microsecond=123456)
    r = ctrl.timer_start("now", job_shift="  Support ")
    assert r["ok"] and r["timer"]["start_iso"] == "2026-09-23T10:00:00"
    assert r["timer"]["job_shift"] == "Support"
    assert r["timer"]["start_epoch_ms"] == int(T0.timestamp() * 1000)
    assert os.path.exists(tm._SESSION_FILE)


def test_start_uses_default_job_shift(env):
    ctrl, _ = env
    storage.set_default_job_shift("Warehouse")
    assert ctrl.timer_start("now")["timer"]["job_shift"] == "Warehouse"


def test_start_blank_job_shift_becomes_dash(env, monkeypatch):
    ctrl, _ = env
    monkeypatch.setattr(storage, "get_default_job_shift", lambda: "  ")
    assert ctrl.timer_start("now")["timer"]["job_shift"] == "—"


def test_start_when_running(env):
    ctrl, clock = env
    _started(ctrl, clock)
    r = ctrl.timer_start("now")
    assert r["status"] == "error" and r["error"]["code"] == "already_running"


def test_start_blocked_by_pending_recovery(env):
    ctrl, clock = env
    WorkTimer().start("Sales", start_time=T0 - timedelta(hours=2))
    r = ctrl.timer_start("now")
    assert r["error"]["code"] == "recovery_pending"
    assert r["timer"]["recovery_pending"] is True


def test_start_at_invalid_time(env):
    ctrl, _ = env
    r = ctrl.timer_start("at", time="25:99")
    assert r["status"] == "invalid" and r["field"] == "time"
    assert not r["timer"]["running"]


def test_start_unknown_mode(env):
    ctrl, _ = env
    assert ctrl.timer_start("later")["status"] == "invalid"


def test_start_at_earlier_today(env):
    ctrl, _ = env
    r = ctrl.timer_start("at", time="9")
    assert r["timer"]["start_iso"] == "2026-09-23T09:00:00"


def test_start_at_far_ahead_means_yesterday(env):
    ctrl, _ = env
    r = ctrl.timer_start("at", time="22:00")
    assert r["timer"]["start_iso"] == "2026-09-22T22:00:00"


def test_start_ahead_asks(env):
    ctrl, _ = env
    r = ctrl.timer_start("at", time="11:00")
    assert r["status"] == "needs_confirm"
    c = r["confirm"]
    assert c["kind"] == "start_ahead" and c["title"] == "Start time hasn't come yet"
    assert [o["id"] for o in c["options"]] == ["now", "earlier", "cancel"]
    assert c["options"][0]["label"] == "Start now (10:00)"
    assert c["options"][1]["label"] == "From yesterday 11:00"
    assert not r["timer"]["running"]


@pytest.mark.parametrize("choice, expected", [
    ("now", "2026-09-23T10:00:00"),
    ("earlier", "2026-09-22T11:00:00"),
])
def test_start_ahead_answers(env, choice, expected):
    ctrl, _ = env
    r = ctrl.timer_start("at", time="11:00", confirm=_answer("start_ahead", choice))
    assert r["timer"]["start_iso"] == expected


def test_start_ahead_cancel(env):
    ctrl, _ = env
    r = ctrl.timer_start("at", time="11:00", confirm=_answer("start_ahead", "cancel"))
    assert r["status"] == "cancelled" and not r["timer"]["running"]


def test_start_session_write_fails(env, monkeypatch):
    ctrl, _ = env
    monkeypatch.setattr(WorkTimer, "_save_session", _fail)
    r = ctrl.timer_start("now")
    assert r["error"]["code"] == "save_failed" and "locked" in r["message"]
    assert not r["timer"]["running"]


# ── stop ─────────────────────────────────────────────────────────────────────

def test_stop_not_running(env):
    ctrl, _ = env
    r = ctrl.timer_stop()
    assert r["status"] == "ok" and not r["timer"]["running"]


def test_stop_under_a_minute_discards(env, tmp_timer):
    ctrl, clock = env
    _started(ctrl, clock)
    clock.now = T0 + timedelta(seconds=59)
    r = ctrl.timer_stop()
    assert r["status"] == "discarded" and r["message"] == "Shift under a minute — not saved"
    assert storage.load_all_entries() == []
    assert not os.path.exists(tm._SESSION_FILE)


def test_stop_saves(env, tmp_timer):
    ctrl, clock = env
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=8, minutes=5)
    r = ctrl.timer_stop()
    assert r["status"] == "saved" and not r["timer"]["running"]
    assert r["entry"]["time_in"] == "10:00" and r["entry"]["time_out"] == "18:05"
    assert r["entry"]["minutes"] == 485
    [e] = storage.load_all_entries()
    assert (e.date, e.job_shift, e.time_out) == ("2026-09-23", "Sales", "18:05")
    assert not os.path.exists(tm._SESSION_FILE)


def test_stop_overnight(env):
    ctrl, clock = env
    _started(ctrl, clock, start=datetime(2026, 9, 23, 22, 0))
    clock.now = datetime(2026, 9, 24, 6, 0)
    r = ctrl.timer_stop()
    assert r["entry"]["date"] == "2026-09-23" and r["entry"]["overnight"]
    assert r["entry"]["time_out_display"] == "06:00 +1"


def test_stop_shortcut_asks(env):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=2)
    r = ctrl.timer_stop("shortcut")
    c = r["confirm"]
    assert c["kind"] == "stop_shift" and c["token"] == token
    assert c["title"] == "Stop shift?" and c["icon"] == "question"
    r = ctrl.timer_stop("shortcut", _answer("stop_shift", "keep", token))
    assert r["status"] == "cancelled" and r["timer"]["running"]
    r = ctrl.timer_stop("shortcut", _answer("stop_shift", "stop", token))
    assert r["status"] == "saved"


def test_stop_shortcut_long_skips_long_confirm(env):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=15)
    r = ctrl.timer_stop("shortcut")
    assert r["confirm"]["icon"] == "warning"
    r = ctrl.timer_stop("shortcut", _answer("stop_shift", "stop", token))
    assert r["status"] == "saved"


def test_stop_shortcut_under_minute_still_asks_first(env):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(seconds=30)
    assert ctrl.timer_stop("shortcut")["status"] == "needs_confirm"
    r = ctrl.timer_stop("shortcut", _answer("stop_shift", "stop", token))
    assert r["status"] == "discarded"


def test_stop_button_long_shift(env):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=14, minutes=1)
    r = ctrl.timer_stop("button")
    assert r["confirm"]["kind"] == "long_shift" and r["confirm"]["title"] == "Long shift"
    r = ctrl.timer_stop("button", _answer("long_shift", "keep", token))
    assert r["status"] == "cancelled" and r["timer"]["running"]
    r = ctrl.timer_stop("button", _answer("long_shift", "stop", token))
    assert r["status"] == "saved"


def test_stop_button_exactly_14h_no_confirm(env):
    ctrl, clock = env
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=14)
    assert ctrl.timer_stop("button")["status"] == "saved"


def test_stop_close_source_long_does_not_ask(env):
    ctrl, clock = env
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=15)
    assert ctrl.timer_stop("close")["status"] == "saved"


def test_stop_over_24h_asks(env):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=26)
    r = ctrl.timer_stop("close")
    c = r["confirm"]
    assert c["kind"] == "over_24h" and c["title"] == "Shift over 24 hours"
    assert [o["id"] for o in c["options"]] == ["save", "discard", "keep"]
    assert c["details"]["capped_end"] == "18:00"


def test_stop_over_24h_save_caps(env):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=26)
    r = ctrl.timer_stop("button", _answer("over_24h", "save", token))
    assert r["status"] == "saved" and r["entry"]["time_out"] == "18:00"


def test_stop_over_24h_keep(env):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=26)
    r = ctrl.timer_stop("button", _answer("over_24h", "keep", token))
    assert r["status"] == "cancelled" and r["timer"]["running"]


def test_stop_over_24h_discard_chain(env, tmp_timer):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=26)
    first = _answer("over_24h", "discard", token)
    r = ctrl.timer_stop("button", first)
    assert r["confirm"]["kind"] == "discard_shift"
    r = ctrl.timer_stop("button", first + _answer("discard_shift", "cancel", token))
    assert r["status"] == "cancelled" and r["timer"]["running"]
    r = ctrl.timer_stop("button", first + _answer("discard_shift", "discard", token))
    assert r["status"] == "discarded" and storage.load_all_entries() == []
    assert not os.path.exists(tm._SESSION_FILE)


def test_stop_stale_token(env):
    ctrl, clock = env
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=2)
    r = ctrl.timer_stop("shortcut", _answer("stop_shift", "stop", "2020-01-01T00:00:00"))
    assert r["error"]["code"] == "stale" and r["timer"]["running"]


def test_stop_save_fails_keeps_running(env, monkeypatch, tmp_timer):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=8)
    # a nested context: monkeypatch.undo() would also undo the tmp_* redirects
    with monkeypatch.context() as m:
        m.setattr(storage, "save_entry", _fail)
        r = ctrl.timer_stop()
    assert r["error"]["code"] == "save_failed"
    assert "still running" in r["message"] and "locked" in r["message"]
    assert r["timer"]["running"] and r["timer"]["start_iso"] == token
    assert r["timer"]["job_shift"] == "Sales"
    assert json.load(open(tm._SESSION_FILE))["start"].startswith("2026-09-23T10:00")
    assert ctrl.timer_stop()["status"] == "saved"
    assert storage.DATA_FILE.startswith(str(tmp_timer))


def test_stop_session_clear_failure_is_logged(env, monkeypatch):
    ctrl, clock = env
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=8)
    monkeypatch.setattr(tm, "clear_saved_session", _fail)
    assert ctrl.timer_stop()["status"] == "saved"
    assert "session.json" in open(storage.ERROR_LOG, encoding="utf-8").read()


# ── discard ──────────────────────────────────────────────────────────────────

def test_discard_not_running(env):
    ctrl, _ = env
    assert ctrl.timer_discard()["error"]["code"] == "not_running"


def test_discard_flow(env, tmp_timer):
    ctrl, clock = env
    token = _started(ctrl, clock)
    r = ctrl.timer_discard()
    assert r["confirm"]["kind"] == "discard_shift" and r["confirm"]["default"] == "cancel"
    assert ctrl.timer_discard(_answer("discard_shift", "cancel", token))["status"] == "cancelled"
    r = ctrl.timer_discard(_answer("discard_shift", "discard", token))
    assert r["status"] == "discarded" and r["message"] == "Shift discarded"
    assert not os.path.exists(tm._SESSION_FILE)


def test_discard_stale(env):
    ctrl, clock = env
    _started(ctrl, clock)
    r = ctrl.timer_discard(_answer("discard_shift", "discard", "nope"))
    assert r["error"]["code"] == "stale" and r["timer"]["running"]


# ── recovery ─────────────────────────────────────────────────────────────────

def _crash(start, job="Support"):
    WorkTimer().start(job, start_time=start)


def test_recovery_none(env):
    ctrl, _ = env
    assert ctrl.recovery() is None


def test_recovery_recent(env):
    ctrl, _ = env
    _crash(T0 - timedelta(hours=3))
    rec = ctrl.recovery()
    assert rec["start_iso"] == "2026-09-23T07:00:00" and rec["job_shift"] == "Support"
    assert rec["elapsed_minutes"] == 180 and rec["over_limit"] is False
    assert rec["suggested_end"] == "10:00"


def test_recovery_over_limit(env):
    ctrl, _ = env
    _crash(T0 - timedelta(hours=30))
    rec = ctrl.recovery()
    assert rec["over_limit"] is True and rec["suggested_end"] == "12:00"


def test_recovery_corrupt_file_removed(env, tmp_timer):
    ctrl, _ = env
    with open(tm._SESSION_FILE, "w") as f:
        f.write("{not json")
    assert ctrl.recovery() is None
    assert not os.path.exists(tm._SESSION_FILE)


def test_recovery_unreadable_file_kept(env, monkeypatch):
    import webapp.controller as wc
    ctrl, _ = env
    _crash(T0 - timedelta(hours=2))

    def locked(*a, **k):
        raise PermissionError("locked")
    with monkeypatch.context() as m:
        m.setattr(wc, "open", locked, raising=False)
        assert ctrl.recovery() is None
    assert os.path.exists(tm._SESSION_FILE)
    assert ctrl.recovery()["job_shift"] == "Support"


def test_recovery_aware_start_accepted(env):
    ctrl, _ = env
    start = (T0 - timedelta(hours=2)).astimezone()
    with open(tm._SESSION_FILE, "w") as f:
        json.dump({"job_shift": "Sales", "start": start.isoformat()}, f)
    rec = ctrl.recovery()
    assert rec is not None and rec["start_iso"].startswith("2026-09-23T08:00")


def test_close_anyway_with_unreadable_data(env, monkeypatch):
    ctrl, clock = env
    _started(ctrl, clock)
    token = ctrl.timer_state()["start_iso"]

    def locked():
        raise PermissionError("data.json locked")
    for name in ("get_default_job_shift", "get_default_start_time", "get_pay_rate"):
        monkeypatch.setattr(storage, name, locked)
    assert ctrl.timer_state()["running"] is True
    r = ctrl.close_app(_answer("close_running", "close", token))
    assert r["quit"] is True


def test_recovery_while_running_is_none(env):
    ctrl, clock = env
    _started(ctrl, clock)
    assert ctrl.recovery() is None


def test_recovery_resume(env):
    ctrl, _ = env
    _crash(T0 - timedelta(hours=3))
    r = ctrl.recovery_resolve("resume")
    assert r["recovery"] is None and r["timer"]["running"]
    assert r["timer"]["start_iso"] == "2026-09-23T07:00:00"
    assert r["timer"]["job_shift"] == "Support"


def test_recovery_save(env, tmp_timer):
    ctrl, _ = env
    _crash(T0 - timedelta(hours=3))
    r = ctrl.recovery_resolve("save", end="9.45")
    assert r["status"] == "saved" and r["entry"]["time_out"] == "09:45"
    assert r["recovery"] is None
    assert not os.path.exists(tm._SESSION_FILE)
    assert len(storage.load_all_entries()) == 1


def test_recovery_save_invalid_end(env):
    ctrl, _ = env
    _crash(T0 - timedelta(hours=3))
    r = ctrl.recovery_resolve("save", end="xx")
    assert r["status"] == "invalid" and r["field"] == "end"
    assert r["recovery"]["start_iso"] == "2026-09-23T07:00:00"


def test_recovery_save_fails(env, monkeypatch, tmp_timer):
    ctrl, _ = env
    _crash(T0 - timedelta(hours=3))
    monkeypatch.setattr(storage, "save_entry", _fail)
    r = ctrl.recovery_resolve("save", end="09:30")
    assert r["error"]["code"] == "save_failed"
    assert r["recovery"]["suggested_end"] == "09:30"
    assert os.path.exists(tm._SESSION_FILE)


def test_recovery_discard(env, tmp_timer):
    ctrl, _ = env
    _crash(T0 - timedelta(hours=3))
    token = ctrl.recovery()["start_iso"]
    r = ctrl.recovery_resolve("discard")
    assert r["confirm"]["kind"] == "discard_shift" and r["confirm"]["token"] == token
    r = ctrl.recovery_resolve("discard", confirm=_answer("discard_shift", "cancel", token))
    assert r["status"] == "cancelled" and r["recovery"]
    r = ctrl.recovery_resolve("discard", confirm=_answer("discard_shift", "discard", token))
    assert r["status"] == "discarded" and r["recovery"] is None
    assert not os.path.exists(tm._SESSION_FILE)


def test_recovery_resolve_nothing_pending(env):
    ctrl, _ = env
    r = ctrl.recovery_resolve("save", end="10:00")
    assert r["status"] == "ok" and r["recovery"] is None


def test_recovery_unknown_action(env):
    ctrl, _ = env
    _crash(T0 - timedelta(hours=1))
    assert ctrl.recovery_resolve("explode")["status"] == "invalid"


# ── close ────────────────────────────────────────────────────────────────────

def test_close_idle(env):
    ctrl, _ = env
    assert ctrl.close_app() == {"ok": True, "status": "ok", "quit": True}


def test_close_running_flow(env, tmp_timer):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=1, minutes=5)
    r = ctrl.close_app()
    c = r["confirm"]
    assert c["kind"] == "close_running" and "1h 05m ago" in c["message"]
    assert [o["id"] for o in c["options"]] == ["stop_close", "close", "cancel"]
    r = ctrl.close_app(_answer("close_running", "cancel", token))
    assert r["status"] == "cancelled" and "quit" not in r
    r = ctrl.close_app(_answer("close_running", "close", token))
    assert r["quit"] is True and os.path.exists(tm._SESSION_FILE)


def test_close_stop_and_close(env):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=8)
    r = ctrl.close_app(_answer("close_running", "stop_close", token))
    assert r["status"] == "saved" and r["quit"] is True


def test_close_stop_over_24h_chains(env):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=25)
    first = _answer("close_running", "stop_close", token)
    r = ctrl.close_app(first)
    assert r["confirm"]["kind"] == "over_24h" and "quit" not in r
    r = ctrl.close_app(first + _answer("over_24h", "save", token))
    assert r["status"] == "saved" and r["quit"] is True


def test_close_stop_save_fails_does_not_quit(env, monkeypatch):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=8)
    monkeypatch.setattr(storage, "save_entry", _fail)
    r = ctrl.close_app(_answer("close_running", "stop_close", token))
    assert r["error"]["code"] == "save_failed" and "quit" not in r


# ── entries ──────────────────────────────────────────────────────────────────

def test_list_month(env):
    ctrl, _ = env
    storage.set_pay_rate(20.0)
    _add("2026-09-21", "09:00", "17:00")          # Mon W39
    _add("2026-09-28", "22:00", "06:00")          # Mon W40, overnight
    _add("2026-09-29", "09:00", "")               # open
    _add("2026-10-01", "09:00", "10:00")          # other month
    r = ctrl.list_month(2026, 9)
    d = r["data"]
    assert d["label"] == "September 2026" and len(d["entries"]) == 3
    assert [w["key"] for w in d["weeks"]] == ["2026-W39", "2026-W40"]
    assert d["weeks"][1]["minutes"] == 480 and len(d["weeks"][1]["entry_ids"]) == 2
    assert d["total_minutes"] == 960 and d["earnings"] == 320.0
    assert d["entries"][2]["minutes"] is None


def test_list_month_invalid(env):
    ctrl, _ = env
    assert ctrl.list_month(2026, 13)["status"] == "invalid"


def test_get_entry(env):
    ctrl, _ = env
    e = _add()
    assert ctrl.get_entry(e.id)["entry"]["id"] == e.id
    assert ctrl.get_entry("missing")["error"]["code"] == "not_found"


def test_save_entry_new(env):
    ctrl, _ = env
    r = ctrl.save_entry({"date": "23.9.2026", "job_shift": " Sales ",
                         "time_in": "9", "time_out": "17.30"})
    assert r["status"] == "saved"
    assert (r["entry"]["date"], r["entry"]["time_in"], r["entry"]["time_out"]) == \
           ("2026-09-23", "09:00", "17:30")
    assert r["entry"]["job_shift"] == "Sales"


def test_save_entry_open_ended(env):
    ctrl, _ = env
    r = ctrl.save_entry({"date": "2026-09-23", "time_in": "09:00", "time_out": ""})
    assert r["status"] == "saved" and r["entry"]["minutes"] is None


def test_save_entry_updates_existing(env):
    ctrl, _ = env
    e = _add()
    ctrl.save_entry({"id": e.id, "date": e.date, "time_in": "08:00", "time_out": "16:00"})
    [only] = storage.load_all_entries()
    assert only.id == e.id and only.time_in == "08:00"


@pytest.mark.parametrize("draft, field", [
    ({"date": "nope", "time_in": "09:00"}, "date"),
    ({"date": "2026-09-23", "time_in": ""}, "time_in"),
    ({"date": "2026-09-23", "time_in": "09:00", "time_out": "99"}, "time_out"),
])
def test_save_entry_invalid(env, draft, field):
    ctrl, _ = env
    r = ctrl.save_entry(draft)
    assert r["status"] == "invalid" and r["field"] == field
    assert storage.load_all_entries() == []


def test_save_entry_long_confirm(env):
    ctrl, _ = env
    draft = {"date": "2026-09-23", "time_in": "06:00", "time_out": "21:00"}
    r = ctrl.save_entry(draft)
    assert r["confirm"]["kind"] == "long_entry" and r["confirm"]["icon"] == "warning"
    assert ctrl.save_entry(draft, _answer("long_entry", "cancel"))["status"] == "cancelled"
    assert storage.load_all_entries() == []
    assert ctrl.save_entry(draft, _answer("long_entry", "save"))["status"] == "saved"


def test_save_entry_fails(env, monkeypatch):
    ctrl, _ = env
    monkeypatch.setattr(storage, "save_entry", _fail)
    r = ctrl.save_entry({"date": "2026-09-23", "time_in": "09:00", "time_out": "17:00"})
    assert r["error"]["code"] == "save_failed" and "locked" in r["message"]


def test_inline_edit_time_out(env):
    ctrl, _ = env
    e = _add()
    r = ctrl.update_entry_field(e.id, "time_out", "18")
    assert r["status"] == "saved" and r["entry"]["time_out"] == "18:00"
    assert storage.load_all_entries()[0].time_out == "18:00"


def test_inline_edit_strips_plus_one(env):
    ctrl, _ = env
    e = _add(t_in="22:00", t_out="06:00")
    assert ctrl.update_entry_field(e.id, "time_out", "06:00 +1") == \
        {"ok": True, "status": "ok", "unchanged": True}
    r = ctrl.update_entry_field(e.id, "time_out", "07:00 +1")
    assert r["entry"]["time_out"] == "07:00"


def test_inline_edit_invalid(env):
    ctrl, _ = env
    e = _add()
    r = ctrl.update_entry_field(e.id, "time_in", "abc")
    assert r["status"] == "invalid" and r["message"] == "Invalid time, not saved"
    assert storage.load_all_entries()[0].time_in == "09:00"


def test_inline_edit_open_entry_blank_unchanged(env):
    ctrl, _ = env
    e = _add(t_out="")
    assert ctrl.update_entry_field(e.id, "time_out", "")["unchanged"] is True


def test_inline_edit_long_confirm(env):
    ctrl, _ = env
    e = _add()
    r = ctrl.update_entry_field(e.id, "time_in", "02:00")
    assert r["confirm"]["kind"] == "long_entry"
    assert ctrl.update_entry_field(e.id, "time_in", "02:00",
                                   _answer("long_entry", "cancel"))["status"] == "cancelled"
    assert storage.load_all_entries()[0].time_in == "09:00"
    r = ctrl.update_entry_field(e.id, "time_in", "02:00", _answer("long_entry", "save"))
    assert r["status"] == "saved"


def test_inline_edit_bad_field_and_missing(env):
    ctrl, _ = env
    e = _add()
    assert ctrl.update_entry_field(e.id, "date", "2026-01-01")["status"] == "invalid"
    assert ctrl.update_entry_field("x", "time_in", "09:00")["error"]["code"] == "not_found"


def test_inline_edit_fails(env, monkeypatch):
    ctrl, _ = env
    e = _add()
    monkeypatch.setattr(storage, "update_entry", _fail)
    r = ctrl.update_entry_field(e.id, "time_out", "18:00")
    assert r["error"]["code"] == "save_failed" and "change could not be saved" in r["message"]


def test_delete_flow(env):
    ctrl, _ = env
    e = _add()
    r = ctrl.delete_entry(e.id)
    c = r["confirm"]
    assert c["kind"] == "delete_entry" and c["default"] == "cancel"
    assert c["message"] == "Delete the shift on Wed 23 Sep, 09:00–17:00?"
    token = c["token"]
    assert ctrl.delete_entry(e.id, _answer("delete_entry", "cancel", token))["status"] == "cancelled"
    r = ctrl.delete_entry(e.id, _answer("delete_entry", "delete", token))
    assert r["status"] == "ok" and r["deleted"]["id"] == e.id
    assert r["message"] == "Deleted on Wed 23 Sep, 09:00–17:00."
    assert storage.load_all_entries() == []
    r = ctrl.restore_entry(r["deleted"])
    assert r["status"] == "saved" and r["message"].startswith("Restored on Wed 23 Sep")
    assert storage.load_all_entries()[0].id == e.id


def test_delete_stale_after_edit(env):
    ctrl, _ = env
    e = _add()
    token = ctrl.delete_entry(e.id)["confirm"]["token"]
    ctrl.update_entry_field(e.id, "time_out", "18:00")
    r = ctrl.delete_entry(e.id, _answer("delete_entry", "delete", token))
    assert r["error"]["code"] == "stale"
    assert len(storage.load_all_entries()) == 1


def test_delete_fails(env, monkeypatch):
    ctrl, _ = env
    e = _add()
    token = ctrl.delete_entry(e.id)["confirm"]["token"]
    monkeypatch.setattr(storage, "delete_entry", _fail)
    r = ctrl.delete_entry(e.id, _answer("delete_entry", "delete", token))
    assert r["error"]["code"] == "save_failed"


def test_restore_invalid_and_fails(env, monkeypatch):
    ctrl, _ = env
    assert ctrl.restore_entry({"id": 1})["status"] == "invalid"
    monkeypatch.setattr(storage, "save_entry", _fail)
    r = ctrl.restore_entry({"id": "a", "date": "2026-09-23", "time_in": "09:00",
                            "time_out": "17:00", "job_shift": "Sales"})
    assert r["error"]["code"] == "save_failed" and "restored" in r["message"]


# ── settings ─────────────────────────────────────────────────────────────────

def _settings_draft(**over):
    d = {"default_start_time": "8", "pay_rate": "20,50", "default_job_shift": " Support ",
         "export_format": "Full", "export_include_pay": True, "appearance": "Dark",
         "ui_prefs": {"target_hours": 7.5}}
    d.update(over)
    return d


def test_get_settings_defaults(env):
    ctrl, _ = env
    s = ctrl.get_settings()["settings"]
    assert s["pay_rate"] == 20.0 and s["pay_rate_text"] == "20"
    assert s["export_format"] in ("Simple", "Full")
    assert s["ui_prefs"] == {"lulz": False, "reduce_effects": False, "lulz_sound": False,
                             "liquid_glass": False, "target_hours": 8.0}


def test_save_settings(env):
    ctrl, _ = env
    r = ctrl.save_settings(_settings_draft())
    s = r["settings"]
    assert r["status"] == "saved"
    assert s["default_start_time"] == "08:00" and s["pay_rate"] == 20.5
    assert s["pay_rate_text"] == "20.5" and s["default_job_shift"] == "Support"
    assert s["export_format"] == "Full" and s["export_include_pay"] is True
    assert s["appearance"] == "Dark" and s["ui_prefs"]["target_hours"] == 7.5
    assert "shifts" in r


def test_save_settings_lulz_sound(env):
    ctrl, _ = env
    r = ctrl.save_settings(_settings_draft(ui_prefs={"lulz": True, "lulz_sound": True}))
    assert r["status"] == "saved"
    assert r["settings"]["ui_prefs"]["lulz_sound"] is True
    assert storage.get_ui_prefs()["lulz_sound"] is True


def test_save_settings_liquid_glass(env):
    ctrl, _ = env
    r = ctrl.save_settings(_settings_draft(ui_prefs={"liquid_glass": True}))
    assert r["status"] == "saved"
    assert r["settings"]["ui_prefs"]["liquid_glass"] is True
    assert storage.get_ui_prefs()["liquid_glass"] is True


def test_save_settings_ignores_bad_appearance(env):
    ctrl, _ = env
    r = ctrl.save_settings(_settings_draft(appearance="Purple"))
    assert r["status"] == "saved" and r["settings"]["appearance"] == "System"


@pytest.mark.parametrize("over, field", [
    ({"default_start_time": "xx"}, "default_start_time"),
    ({"pay_rate": "-3"}, "pay_rate"),
    ({"pay_rate": "abc"}, "pay_rate"),
    ({"export_format": "Fancy"}, "export_format"),
    ({"ui_prefs": {"target_hours": 30}}, "target_hours"),
    ({"ui_prefs": {"bogus": 1}}, "ui_prefs"),
])
def test_save_settings_invalid_writes_nothing(env, over, field):
    ctrl, _ = env
    r = ctrl.save_settings(_settings_draft(**over))
    assert r["status"] == "invalid" and r["field"] == field
    assert storage.get_default_job_shift() != "Support"
    assert storage.get_pay_rate() == 20.0


def test_save_settings_fails(env, monkeypatch):
    ctrl, _ = env
    monkeypatch.setattr(storage, "_save_raw", _fail)
    r = ctrl.save_settings(_settings_draft())
    assert r["error"]["code"] == "save_failed"
    assert r["message"].startswith("Settings could not be written")


def test_save_ui_prefs(env, monkeypatch):
    ctrl, _ = env
    r = ctrl.save_ui_prefs({"lulz": True})
    assert r["status"] == "saved" and r["settings"]["ui_prefs"]["lulz"] is True
    assert ctrl.save_ui_prefs({"target_hours": 0})["field"] == "target_hours"
    assert ctrl.save_ui_prefs({"lulz": "yes"})["status"] == "invalid"
    r = ctrl.save_ui_prefs({"lulz_sound": True})
    assert r["status"] == "saved" and r["settings"]["ui_prefs"]["lulz_sound"] is True
    assert ctrl.save_ui_prefs({"lulz_sound": 1})["status"] == "invalid"
    r = ctrl.save_ui_prefs({"liquid_glass": True})
    assert r["status"] == "saved" and r["settings"]["ui_prefs"]["liquid_glass"] is True
    assert ctrl.save_ui_prefs({"liquid_glass": 1})["status"] == "invalid"
    monkeypatch.setattr(storage, "_save_raw", _fail)
    assert ctrl.save_ui_prefs({"lulz": False})["error"]["code"] == "save_failed"


def test_add_job_shift(env):
    ctrl, _ = env
    assert ctrl.add_job_shift("  ")["field"] == "name"
    r = ctrl.add_job_shift(" Night ")
    assert r["added"] is True and "Night" in r["shifts"]
    r = ctrl.add_job_shift("night")
    assert r["added"] is False and r["message"] == "'night' is already in the shift list."


def test_add_job_shift_fails(env, monkeypatch):
    ctrl, _ = env
    monkeypatch.setattr(storage, "add_job_shift", _fail)
    assert ctrl.add_job_shift("X")["error"]["code"] == "save_failed"


# ── stats / export / import ──────────────────────────────────────────────────

def test_get_stats(env):
    ctrl, _ = env
    _add("2026-09-23", "09:00", "17:00")
    r = ctrl.get_stats("2026-09-21", "2026-09-27", "day")
    assert r["data"]["totals"]["minutes"] == 480 and len(r["data"]["buckets"]) == 7


@pytest.mark.parametrize("args, field", [
    (("2026-09-27", "2026-09-21", "day"), "range"),
    (("bad", "2026-09-21", "day"), "range"),
    (("2000-01-01", "2026-09-21", "day"), "range"),
    (("2026-09-21", "2026-09-27", "year"), "granularity"),
])
def test_get_stats_invalid(env, args, field):
    ctrl, _ = env
    r = ctrl.get_stats(*args)
    assert r["status"] == "invalid" and r["field"] == field


def test_export_filename():
    assert ShiftController.export_filename(2026, 9) == "Hours September 2026.xlsx"


def test_export_month(env, monkeypatch):
    import excel_export
    ctrl, _ = env
    _add()
    calls = []
    monkeypatch.setattr(excel_export, "export_month", lambda **k: calls.append(k))
    assert ctrl.export_month(2026, 9, "")["status"] == "cancelled"
    r = ctrl.export_month(2026, 9, "C:/x/out.xlsx")
    assert r["status"] == "saved" and r["path"] == "C:/x/out.xlsx"
    assert len(calls[0]["entries"]) == 1 and calls[0]["save_path"] == "C:/x/out.xlsx"


@pytest.mark.parametrize("exc, code", [(PermissionError("busy"), "file_locked"),
                                       (RuntimeError("boom"), "internal")])
def test_export_month_errors(env, monkeypatch, exc, code):
    import excel_export
    ctrl, _ = env

    def raise_(**k):
        raise exc
    monkeypatch.setattr(excel_export, "export_month", raise_)
    assert ctrl.export_month(2026, 9, "out.xlsx")["error"]["code"] == code


def test_import_excel(env, monkeypatch):
    import import_excel
    ctrl, _ = env

    def fake(path):
        if path == "bad.xlsx":
            raise ValueError("not a timesheet")
        return 3, 1
    monkeypatch.setattr(import_excel, "import_from_file", fake)
    assert ctrl.import_excel([])["status"] == "cancelled"
    r = ctrl.import_excel(["a.xlsx", "bad.xlsx"])
    assert (r["imported"], r["skipped"], r["files"]) == (3, 1, 2)
    assert r["message"].startswith("Imported 3 entries from 2 files.\n1 duplicate skipped.")
    assert "bad.xlsx: not a timesheet" in r["errors"][0]


# ── OCR / DLC / updates ──────────────────────────────────────────────────────

class FakeOcr:
    def __init__(self, found=None, fail=None):
        self.found, self.fail, self.saved = found or [], fail, None

    def extract_entries_from_image(self, path):
        if self.fail:
            raise self.fail
        return self.found

    def save_confirmed_entries(self, rows):
        self.saved = rows
        return len(rows), 0


def test_ocr_extract_maps_candidates(env):
    ctrl, _ = env
    mod = FakeOcr([{"date": "2026-09-23", "job_shift": "", "time_in": "09:00",
                    "time_out": "17:00", "_raw_line": "23.9 9-17", "_confidence": "ok"},
                   {"date": "", "time_in": "", "_confidence": "weird"}])
    r = ctrl.ocr_extract(["a.png"], module=mod)
    c = r["candidates"]
    assert c[0]["raw_line"] == "23.9 9-17" and c[0]["confidence"] == "ok"
    assert c[1]["confidence"] == "uncertain" and "_raw_line" not in c[0]


def test_ocr_extract_errors(env, monkeypatch):
    ctrl, _ = env
    assert ctrl.ocr_extract([], module=FakeOcr())["status"] == "cancelled"
    r = ctrl.ocr_extract(["a.png"], module=FakeOcr(fail=RuntimeError("no engine")))
    assert r["error"]["code"] == "ocr_failed" and "no engine" in r["message"]
    r = ctrl.ocr_extract(["a.png"], module=FakeOcr())
    assert r["ok"] and r["candidates"] == [] and "No timesheet entries" in r["message"]
    monkeypatch.setattr(dlc, "module", lambda: None)
    assert ctrl.ocr_extract(["a.png"])["error"]["code"] == "dlc_unavailable"


def test_ocr_save(env):
    ctrl, _ = env
    mod = FakeOcr()
    r = ctrl.ocr_save([{"date": "2026-09-23", "time_in": "09:00", "time_out": "17:00"},
                       {"date": "", "time_in": "09:00"}], module=mod)
    assert r["status"] == "saved" and r["imported"] == 1 and r["invalid_skipped"] == 1
    assert "1 row(s) had no date or start time" in r["message"]
    assert mod.saved[0]["job_shift"] == ""


def _dlc_state(monkeypatch, state="ok", version="2.0.0", error=None):
    monkeypatch.setattr(dlc, "load_status",
                        lambda: {"state": state, "version": version, "error": error})


def test_dlc_status(env, monkeypatch):
    ctrl, _ = env
    _dlc_state(monkeypatch, "incompatible", None, "boom")
    s = ctrl.dlc_status()
    assert s["state"] == "incompatible" and "(boom)" in s["message"]
    assert s["ocr_available"] is False
    _dlc_state(monkeypatch)
    ctrl.dlc_update_version = "2.1.0"
    assert ctrl.dlc_status()["update_version"] == "2.1.0"
    ctrl.dlc_update_version = "1.0.0"
    assert ctrl.dlc_status()["update_version"] is None


def test_dlc_remove_flow(env, monkeypatch):
    ctrl, _ = env
    _dlc_state(monkeypatch)
    removed = []
    monkeypatch.setattr(dlc, "remove", lambda: removed.append(1))
    monkeypatch.setattr(dlc, "reload", lambda: None)
    r = ctrl.dlc_remove()
    assert r["confirm"]["kind"] == "remove_dlc" and r["confirm"]["title"] == "Remove Image OCR"
    assert ctrl.dlc_remove(_answer("remove_dlc", "cancel"))["status"] == "cancelled"
    assert ctrl.dlc_remove(_answer("remove_dlc", "remove"))["ok"] and removed


def test_dlc_install_failure(env, monkeypatch):
    ctrl, _ = env
    _dlc_state(monkeypatch, "missing", None)

    def boom():
        raise dlc.DlcError("hash mismatch")
    monkeypatch.setattr(dlc, "install", boom)
    r = ctrl.dlc_install()
    assert r["error"]["code"] == "dlc_failed" and r["message"] == "hash mismatch"


def test_check_updates(env, monkeypatch):
    import updater
    ctrl, _ = env
    _dlc_state(monkeypatch, "missing", None)
    monkeypatch.setattr(updater, "fetch_latest_release",
                        lambda: ("2.1.0", "https://x/setup.exe", None))
    r = ctrl.check_updates("2.0.0")
    assert r["app"]["available"] is True and ctrl.pending_update[0] == "2.1.0"
    r = ctrl.check_updates("2.1.0")
    assert r["message"] == "You're up to date (v2.1.0)."


def test_check_updates_with_dlc_note(env, monkeypatch):
    import updater
    ctrl, _ = env
    _dlc_state(monkeypatch, "ok", "2.0.0")
    monkeypatch.setattr(updater, "fetch_latest_release", lambda: None)
    monkeypatch.setattr(updater, "fetch_latest_dlc_version", lambda: "2.0.1")
    r = ctrl.check_updates("2.0.0")
    assert r["dlc"]["available"] and "DLC (v2.0.1)" in r["message"]
    assert ctrl.dlc_update_version == "2.0.1"


def test_check_updates_network_error(env, monkeypatch):
    import updater
    ctrl, _ = env

    def offline():
        raise OSError("offline")
    monkeypatch.setattr(updater, "fetch_latest_release", offline)
    r = ctrl.check_updates("2.0.0")
    assert r["error"]["code"] == "network" and "offline" in r["message"]


def test_install_update(env, monkeypatch):
    import updater
    ctrl, _ = env
    assert ctrl.install_update(frozen=False)["error"]["code"] == "not_frozen"
    assert ctrl.install_update(frozen=True)["error"]["code"] == "update_failed"
    calls = []
    monkeypatch.setattr(updater, "apply_update", lambda u, s: calls.append((u, s)))
    ctrl.remember_update("2.1.0", "https://x/setup.exe", "https://x/sha")
    assert ctrl.install_update(frozen=True) == {"ok": True, "status": "ok", "version": "2.1.0"}
    assert calls == [("https://x/setup.exe", "https://x/sha")]


# ── app ──────────────────────────────────────────────────────────────────────

def test_changelog(env, monkeypatch):
    import changelog as cl
    ctrl, _ = env
    monkeypatch.setattr(cl, "CHANGELOG", {"1.2.0": ["a"], "1.3.0": ["b"], "2.0.0": ["c"]})
    assert ctrl.changelog("2.0.0") is None          # first run
    assert ctrl.changelog("2.0.0") is None          # same version
    storage.set_last_seen_version("1.2.0")
    assert ctrl.changelog("2.0.0") == [{"version": "2.0.0", "items": ["c"]},
                                       {"version": "1.3.0", "items": ["b"]}]
    assert storage.get_last_seen_version() == "2.0.0"


def test_bootstrap(env, monkeypatch):
    ctrl, _ = env
    _dlc_state(monkeypatch, "missing", None)
    _crash(T0 - timedelta(hours=1))
    d = ctrl.bootstrap("2.0.0", frozen=False, dev=True)["data"]
    assert d["version"] == "2.0.0" and d["dev"] is True and d["today"] == "2026-09-23"
    assert d["recovery"]["job_shift"] == "Support"
    assert d["timer"]["recovery_pending"] is True
    assert d["month"] == {"year": 2026, "month": 9}
    assert d["shifts"] and d["settings"]["pay_rate"] == 20.0


def test_ensure_shifts_file(env, tmp_storage):
    ctrl, _ = env
    path = ctrl.ensure_shifts_file()
    assert path == str(tmp_storage / "shifts.txt") and os.path.exists(path)
