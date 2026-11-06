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
    r = ctrl.timer_start("at", time="22:00", confirm=_answer("start_backdate", "earlier"))
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


def test_start_backdate_asks(env):
    ctrl, clock = env
    clock.now = datetime(2026, 9, 23, 22, 0)
    r = ctrl.timer_start("at", time="08:00")
    assert r["status"] == "needs_confirm" and not r["timer"]["running"]
    c = r["confirm"]
    assert c["kind"] == "start_backdate" and c["icon"] == "warning"
    assert c["default"] == "now" and c["cancel"] == "cancel"
    assert [o["label"] for o in c["options"]] == ["Start now (22:00)", "From today 08:00", "Cancel"]
    assert c["details"] == {"start_iso": "2026-09-23T08:00:00", "elapsed_minutes": 840}
    assert "14h 00m" in c["message"]


@pytest.mark.parametrize("choice, expected", [
    ("now", "2026-09-23T22:00:00"),
    ("earlier", "2026-09-23T08:00:00"),
])
def test_start_backdate_answers(env, choice, expected):
    ctrl, clock = env
    clock.now = datetime(2026, 9, 23, 22, 0)
    r = ctrl.timer_start("at", time="08:00", confirm=_answer("start_backdate", choice))
    assert r["status"] == "ok" and r["timer"]["start_iso"] == expected


def test_start_backdate_cancel(env):
    ctrl, clock = env
    clock.now = datetime(2026, 9, 23, 22, 0)
    r = ctrl.timer_start("at", time="08:00", confirm=_answer("start_backdate", "cancel"))
    assert r["status"] == "cancelled" and not r["timer"]["running"]
    assert not os.path.exists(tm._SESSION_FILE)


def test_start_backdate_not_under_six_hours(env):
    ctrl, clock = env
    clock.now = datetime(2026, 9, 23, 13, 59)
    r = ctrl.timer_start("at", time="08:00")
    assert r["status"] == "ok" and r["timer"]["start_iso"] == "2026-09-23T08:00:00"


def test_start_ahead_earlier_does_not_ask_backdate_too(env):
    ctrl, _ = env
    # 11:00 at 10:00 is yesterday 11:00, 23 h back, but start_ahead already asked
    r = ctrl.timer_start("at", time="11:00", confirm=_answer("start_ahead", "earlier"))
    assert r["status"] == "ok" and r["timer"]["start_iso"] == "2026-09-22T11:00:00"


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
    assert c["kind"] == "stop_shift" and c["token"] == f"{token}@{token[:11]}12:00:00"
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
    _started(ctrl, clock)
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


def test_stop_session_left_behind_does_not_block_start(env, monkeypatch):
    """session.json survives a saved STOP: no phantom 'unfinished shift'
    and the next START works first time."""
    ctrl, clock = env
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=8)
    with monkeypatch.context() as m:
        m.setattr(tm, "clear_saved_session", _fail)
        r = ctrl.timer_stop()
    assert r["status"] == "saved" and r["timer"]["recovery_pending"] is False
    assert os.path.exists(tm._SESSION_FILE)
    clock.now = T0 + timedelta(hours=9)
    r = ctrl.timer_start("now")
    assert r["status"] == "ok" and r["timer"]["running"]
    assert "saved_entry_id" not in tm.load_saved_session()
    assert len(storage.load_all_entries()) == 1


def test_stop_near_24h_by_the_clock_is_capped_not_zero(env):
    """09:00:30 → 09:00:10 the next day is 1439 elapsed minutes but would
    be saved as 09:00–09:00 (0 min): it counts as a full day."""
    ctrl, clock = env
    start = datetime(2026, 9, 23, 9, 0, 30)
    token = _started(ctrl, clock, start=start)
    clock.now = datetime(2026, 9, 24, 9, 0, 10)
    r = ctrl.timer_stop("button")
    assert r["confirm"]["kind"] == "over_24h"
    r = ctrl.timer_stop("button", _answer("over_24h", "save", token))
    assert r["entry"]["time_out"] == "17:00" and r["entry"]["minutes"] == 480


def test_stop_long_check_goes_by_the_clock(env):
    ctrl, clock = env
    _started(ctrl, clock, start=datetime(2026, 9, 23, 9, 0, 50))
    clock.now = datetime(2026, 9, 23, 23, 1, 10)      # 840 elapsed, 841 on the sheet
    assert ctrl.timer_stop("button")["confirm"]["kind"] == "long_shift"


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


# ── stop at / adjust the running shift ───────────────────────────────────────

def test_running_start_follows_the_timer(env):
    ctrl, clock = env
    assert ctrl.running_start() is None
    token = _started(ctrl, clock)
    assert ctrl.running_start() == T0
    ctrl.timer_discard(_answer("discard_shift", "discard", token))
    assert ctrl.running_start() is None


def test_stop_at_saves_the_given_end(env, tmp_timer):
    ctrl, clock = env
    _started(ctrl, clock, T0.replace(hour=9, second=40))
    clock.now = T0.replace(hour=17, minute=45)
    r = ctrl.timer_stop_at("17:00")
    assert r["status"] == "saved" and not r["timer"]["running"]
    assert (r["entry"]["time_in"], r["entry"]["time_out"]) == ("09:00", "17:00")
    assert r["entry"]["minutes"] == 480
    assert not os.path.exists(tm._SESSION_FILE)


def test_stop_at_refuses_bad_times(env, tmp_timer):
    ctrl, clock = env
    _started(ctrl, clock, T0.replace(hour=9))
    clock.now = T0.replace(hour=12)
    assert ctrl.timer_stop_at("nope")["field"] == "end"
    r = ctrl.timer_stop_at("09:00")
    assert r["status"] == "invalid" and "after the start (09:00)" in r["message"]
    r = ctrl.timer_stop_at("12:01")                       # still ahead
    assert r["status"] == "invalid" and "hasn't come yet" in r["message"]
    r = ctrl.timer_stop_at("08:00")                       # 23 h on: also ahead
    assert r["status"] == "invalid"
    assert ctrl.timer_state()["running"]
    assert ctrl.timer_stop_at("12:00")["status"] == "saved"


def test_stop_at_when_idle(env):
    ctrl, _ = env
    assert ctrl.timer_stop_at("17:00")["error"]["code"] == "not_running"


def test_stop_at_long_asks_first(env, tmp_timer):
    ctrl, clock = env
    token = _started(ctrl, clock, T0.replace(hour=6))
    clock.now = T0 + timedelta(hours=14)                  # Thu 00:00
    r = ctrl.timer_stop_at("22:00")
    assert r["confirm"]["kind"] == "long_entry" and r["confirm"]["token"] == token
    r = ctrl.timer_stop_at("22:00", _answer("long_entry", "cancel", token))
    assert r["status"] == "cancelled" and ctrl.timer_state()["running"]
    r = ctrl.timer_stop_at("22:00", _answer("long_entry", "save", "other"))
    assert r["error"]["code"] == "stale"
    r = ctrl.timer_stop_at("22:00", _answer("long_entry", "save", token))
    assert r["status"] == "saved" and r["entry"]["minutes"] == 16 * 60


def test_stop_at_rescues_a_shift_over_24h(env, tmp_timer):
    ctrl, clock = env
    _started(ctrl, clock, T0.replace(hour=9))
    clock.now = T0 + timedelta(days=2)
    r = ctrl.timer_stop_at("17:30")
    assert r["status"] == "saved"
    assert (r["entry"]["date"], r["entry"]["time_out"]) == ("2026-09-23", "17:30")


def test_stop_at_save_failure_keeps_running(env, monkeypatch, tmp_timer):
    ctrl, clock = env
    _started(ctrl, clock, T0.replace(hour=9))
    clock.now = T0
    monkeypatch.setattr(storage, "save_entry", _fail)
    r = ctrl.timer_stop_at("09:45")
    assert r["error"]["code"] == "save_failed"
    assert ctrl.timer_state()["running"] and os.path.exists(tm._SESSION_FILE)


def test_adjust_moves_start_and_job(env, tmp_timer):
    ctrl, clock = env
    token = _started(ctrl, clock, T0)
    r = ctrl.timer_adjust(token, time="09:15", job_shift="  Support ")
    assert r["status"] == "ok"
    assert r["timer"]["start_iso"] == "2026-09-23T09:15:00" and r["timer"]["job_shift"] == "Support"
    saved = tm.load_saved_session()
    assert saved == {"job_shift": "Support", "start": "2026-09-23T09:15:00"}
    r = ctrl.timer_adjust(r["timer"]["start_iso"], job_shift="")
    assert r["timer"]["job_shift"] == "—" and r["timer"]["start_iso"] == "2026-09-23T09:15:00"


def test_adjust_refuses_ahead_and_stale(env, tmp_timer):
    ctrl, clock = env
    token = _started(ctrl, clock, T0)
    r = ctrl.timer_adjust(token, time="11:00")
    assert r["status"] == "invalid" and r["field"] == "time"
    assert ctrl.timer_adjust(token, time="xx")["field"] == "time"
    assert ctrl.timer_adjust("2026-09-23T08:00:00", time="09:00")["error"]["code"] == "stale"
    assert ctrl.timer_state()["start_iso"] == token


def test_adjust_far_back_asks_first(env, tmp_timer):
    ctrl, clock = env
    token = _started(ctrl, clock, T0)
    r = ctrl.timer_adjust(token, time="22:00")            # yesterday 22:00
    c = r["confirm"]
    assert c["kind"] == "start_backdate" and c["token"] == token
    assert [o["id"] for o in c["options"]] == ["earlier", "cancel"]
    r = ctrl.timer_adjust(token, "22:00", confirm=_answer("start_backdate", "cancel", token))
    assert r["status"] == "cancelled" and ctrl.timer_state()["start_iso"] == token
    r = ctrl.timer_adjust(token, "22:00", confirm=_answer("start_backdate", "earlier", token))
    assert r["timer"]["start_iso"] == "2026-09-22T22:00:00"


def test_adjust_later_start_needs_no_confirm(env, tmp_timer):
    ctrl, clock = env
    token = _started(ctrl, clock, T0 - timedelta(hours=8))   # 02:00
    clock.now = T0
    r = ctrl.timer_adjust(token, time="03:00")
    assert r["status"] == "ok" and r["timer"]["start_iso"] == "2026-09-23T03:00:00"


def test_adjust_write_failure_keeps_the_old_start(env, monkeypatch, tmp_timer):
    ctrl, clock = env
    token = _started(ctrl, clock, T0)
    monkeypatch.setattr(WorkTimer, "_save_session", _fail)
    r = ctrl.timer_adjust(token, time="09:00", job_shift="Other")
    assert r["error"]["code"] == "save_failed"
    assert r["timer"]["start_iso"] == token and r["timer"]["job_shift"] == "Sales"
    assert tm.load_saved_session()["start"] == token


def test_adjust_when_idle(env):
    ctrl, _ = env
    assert ctrl.timer_adjust("x", time="09:00")["error"]["code"] == "not_running"


def test_adjust_job_follows_the_start_rules(env, tmp_timer):
    # the job is checked as timer_start checks it: text only, no line
    # breaks (a newline splits shifts.txt), not over JOB_SHIFT_MAX
    ctrl, clock = env
    token = _started(ctrl, clock, T0)
    for bad in ("Night\nshift", "x" * (storage.JOB_SHIFT_MAX + 1), 5):
        r = ctrl.timer_adjust(token, job_shift=bad)
        assert r["status"] == "invalid" and r["field"] == "job_shift"
    assert ctrl.timer_state()["job_shift"] == "Sales"
    assert tm.load_saved_session()["job_shift"] == "Sales"
    r = ctrl.timer_adjust(token, job_shift="  Night   shift ")
    assert r["timer"]["job_shift"] == "Night shift"


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


def test_recovery_corrupt_file_set_aside(env, tmp_timer):
    ctrl, _ = env
    with open(tm._SESSION_FILE, "w") as f:
        f.write("{not json")
    assert ctrl.recovery() is None
    assert not os.path.exists(tm._SESSION_FILE)
    [kept] = list(tmp_timer.glob("session.bad-*.json"))
    assert kept.read_text() == "{not json"
    assert "session.json could not be read" in open(storage.ERROR_LOG, encoding="utf-8").read()


def test_recovery_skips_shift_already_saved(env, tmp_timer):
    """STOP saved the shift but session.json couldn't be removed: the next
    launch must not offer it again (that would save it twice)."""
    ctrl, _ = env
    start = T0 - timedelta(hours=3)
    _crash(start, job="Support")
    e = _add(date="2026-09-23", t_in="07:00", t_out="10:00", job="Support")
    tm.mark_session_saved(e.id)
    assert ctrl.recovery() is None
    assert not os.path.exists(tm._SESSION_FILE)


def test_recovery_offers_shift_matching_an_unrelated_entry(env):
    """An entry at the same date, minute and job (an earlier short shift,
    an import) is not proof this shift was saved: it is still offered."""
    ctrl, _ = env
    _crash(T0 - timedelta(hours=3), job="Support")
    _add(date="2026-09-23", t_in="07:00", t_out="07:10", job="Support")
    assert ctrl.recovery()["job_shift"] == "Support"


def test_recovery_offers_shift_when_marked_entry_missing(env):
    """Marked just before a save that then failed: still offered."""
    ctrl, _ = env
    _crash(T0 - timedelta(hours=3), job="Support")
    tm.mark_session_saved("never-saved")
    assert ctrl.recovery()["job_shift"] == "Support"


def test_recovery_save_then_locked_session_not_offered_again(env, monkeypatch):
    ctrl, _ = env
    _crash(T0 - timedelta(hours=3), job="Support")
    with monkeypatch.context() as m:
        m.setattr(tm, "clear_saved_session", _fail)
        assert ctrl.recovery_resolve("save", "10:00")["status"] == "saved"
    assert os.path.exists(tm._SESSION_FILE)
    assert ctrl.recovery() is None
    assert len(storage.load_all_entries()) == 1


def test_stop_save_failure_keeps_shift_recoverable(env, monkeypatch):
    ctrl, clock = env
    _started(ctrl, clock, job="Sales")
    clock.now = T0 + timedelta(hours=2)
    with monkeypatch.context() as m:
        m.setattr(storage, "save_entry", _fail)
        assert ctrl.timer_stop("button")["error"]["code"] == "save_failed"
    assert "saved_entry_id" not in tm.load_saved_session()


def test_stop_then_locked_session_not_saved_twice(env, monkeypatch):
    ctrl, clock = env
    _started(ctrl, clock, job="Sales")
    clock.now = T0 + timedelta(hours=2)
    with monkeypatch.context() as m:
        m.setattr(tm, "clear_saved_session", _fail)
        assert ctrl.timer_stop("button")["status"] == "saved"
    assert os.path.exists(tm._SESSION_FILE)
    assert ctrl.recovery() is None
    assert len(storage.load_all_entries()) == 1


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


def test_recovery_save_zero_length_is_invalid(env, tmp_timer):
    ctrl, _ = env
    _crash(T0 - timedelta(hours=3))
    r = ctrl.recovery_resolve("save", end="07:00")
    assert r["status"] == "invalid" and r["field"] == "end"
    assert "after the start" in r["message"] and r["recovery"]
    assert storage.load_all_entries() == [] and os.path.exists(tm._SESSION_FILE)


def test_recovery_save_long_asks_first(env, tmp_timer):
    ctrl, _ = env
    _crash(T0 - timedelta(hours=3))
    token = ctrl.recovery()["start_iso"]
    r = ctrl.recovery_resolve("save", end="06:30")       # 23h 30m overnight
    c = r["confirm"]
    assert c["kind"] == "long_entry" and c["token"] == token
    assert c["details"]["elapsed_minutes"] == 1410 and c["details"]["overnight"]
    assert r["recovery"]["start_iso"] == token
    r = ctrl.recovery_resolve("save", "06:30", _answer("long_entry", "cancel", token))
    assert r["status"] == "cancelled" and r["recovery"]
    assert storage.load_all_entries() == []
    r = ctrl.recovery_resolve("save", "06:30", _answer("long_entry", "save", "other"))
    assert r["error"]["code"] == "stale"
    r = ctrl.recovery_resolve("save", "06:30", _answer("long_entry", "save", token))
    assert r["status"] == "saved" and r["entry"]["minutes"] == 1410


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


def test_save_entry_overlap_read_fails(env, monkeypatch):
    # the overlap check reads data.json before the write: a locked file
    # must still give the save_failed message, not an internal error
    ctrl, _ = env
    monkeypatch.setattr(storage, "load_all_entries", _fail)
    r = ctrl.save_entry({"date": "2026-09-23", "time_in": "09:00", "time_out": "17:00"})
    assert r["error"]["code"] == "save_failed" and "locked" in r["message"]


def test_save_entry_edit_read_fails(env, monkeypatch):
    # editing reads the stored entry first: a locked file is save_failed too
    ctrl, _ = env
    e = _add()
    monkeypatch.setattr(storage, "load_all_entries", _fail)
    r = ctrl.save_entry({"id": e.id, "date": "2026-09-23", "time_in": "09:00",
                         "time_out": "18:00"})
    assert r["error"]["code"] == "save_failed" and "locked" in r["message"]


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


def test_inline_edit_read_fails(env, monkeypatch):
    # both the lookup and the overlap check read data.json
    ctrl, _ = env
    e = _add()
    monkeypatch.setattr(storage, "load_all_entries", _fail)
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
                             "liquid_glass": False, "target_hours": 8.0, "pet": "off",
                             "pet_name": "", "pet_hint_seen": False, "pet_skin": "classic"}


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


def test_save_settings_sheet_names(env, tmp_path):
    ctrl, _ = env
    s = ctrl.get_settings()["settings"]
    assert s["employee_name"] == "" and s["manager_name"] == ""
    r = ctrl.save_settings(_settings_draft(employee_name=" Aino  Virtanen ", manager_name="Pekka"))
    assert r["settings"]["employee_name"] == "Aino Virtanen"
    assert r["settings"]["manager_name"] == "Pekka"
    # a draft without the names leaves them as they were
    r = ctrl.save_settings(_settings_draft())
    assert r["settings"]["employee_name"] == "Aino Virtanen"
    assert "control characters" in ctrl.save_settings(
        _settings_draft(employee_name="bell\x07"))["message"]
    assert "60 characters" in ctrl.save_settings(
        _settings_draft(employee_name="x" * 61))["message"]
    # the Full export prints them after EMPLOYEE: / MANAGER:
    from openpyxl import load_workbook
    out = tmp_path / "Full.xlsx"
    assert ctrl.export_month(2026, 5, str(out))["status"] == "saved"
    ws = load_workbook(str(out)).active
    assert ws["B3"].value == "Aino Virtanen" and ws["B5"].value == "Pekka"


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
    ({"employee_name": "x" * 61}, "employee_name"),
    ({"manager_name": "tab\tfeed"}, "manager_name"),
    ({"manager_name": None}, "manager_name"),
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


def test_save_ui_prefs_pet(env):
    ctrl, _ = env
    r = ctrl.save_ui_prefs({"pet": "wizard", "pet_name": "  Merlin   the  Grey "})
    assert r["status"] == "saved"
    assert r["settings"]["ui_prefs"]["pet"] == "wizard"
    assert r["settings"]["ui_prefs"]["pet_name"] == "Merlin the Grey"
    assert ctrl.save_ui_prefs({"pet_name": ""})["settings"]["ui_prefs"]["pet_name"] == ""
    for bad in ({"pet": "dragon"}, {"pet": None}, {"pet": True}):
        assert ctrl.save_ui_prefs(bad)["field"] == "ui_prefs"
    for bad in ("x" * 25, 3, None, "bell\x07", "evil‮gnp", "two lines"):
        r = ctrl.save_ui_prefs({"pet_name": bad})
        assert r["status"] == "invalid" and r["field"] == "pet_name"
    assert "control characters" in ctrl.save_ui_prefs({"pet_name": "bell\x07"})["message"]
    assert "24 characters" in ctrl.save_ui_prefs({"pet_name": "x" * 25})["message"]
    # emoji with joiners and ZWNJ names are fine
    for good in ("\U0001f9d9‍♂️", "\U0001f408‍⬛", "Mi‌na"):
        r = ctrl.save_ui_prefs({"pet_name": good})
        assert r["status"] == "saved" and r["settings"]["ui_prefs"]["pet_name"] == good
    assert ctrl.save_ui_prefs({"pet_name": "x" * 24})["status"] == "saved"
    assert storage.get_ui_prefs()["pet"] == "wizard"


def test_save_ui_prefs_pet_skin(env):
    ctrl, _ = env
    r = ctrl.save_ui_prefs({"pet_skin": "neon"})
    assert r["status"] == "saved" and r["settings"]["ui_prefs"]["pet_skin"] == "neon"
    r = ctrl.save_ui_prefs({"pet_skin": "plaid"})
    assert r["status"] == "invalid" and r["field"] == "ui_prefs" and "pet_skin" in r["message"]
    assert storage.get_ui_prefs()["pet_skin"] == "neon"


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


@pytest.mark.parametrize("name", ["A\nB", "A\rB", "Tab\there", "Sales \ud83d",
                                  "evil‮RTL", "x" * 101, 5])
def test_add_job_shift_rejects_bad_names(env, tmp_storage, name):
    ctrl, _ = env
    before = storage.get_job_shift_list()
    r = ctrl.add_job_shift(name)
    assert r["status"] == "invalid" and r["field"] == "name"
    assert storage.get_job_shift_list() == before


def test_add_job_shift_collapses_spaces(env):
    ctrl, _ = env
    r = ctrl.add_job_shift("  Night   shift ")
    assert r["added"] is True and "Night shift" in r["shifts"]


def test_save_entry_rejects_a_bad_job_shift(env, tmp_storage):
    ctrl, _ = env
    draft = {"date": "2026-09-01", "time_in": "08:00", "time_out": "16:00"}
    for bad in ("Sales\nNight", "Sales \ud83d", "y" * 101):
        r = ctrl.save_entry({**draft, "job_shift": bad})
        assert r["status"] == "invalid" and r["field"] == "job_shift"
    assert storage.load_all_entries() == []
    assert not (tmp_storage / "data.json.tmp").exists()
    r = ctrl.save_entry({**draft, "job_shift": " Sales  Night "})
    assert r["status"] == "saved" and r["entry"]["job_shift"] == "Sales Night"


def test_timer_start_rejects_a_bad_job_shift(env):
    ctrl, _ = env
    for bad in (5, "A\nB", "z" * 101):
        r = ctrl.timer_start("now", job_shift=bad)
        assert r["status"] == "invalid" and r["field"] == "job_shift"
        assert r["timer"]["running"] is False
    assert ctrl.timer_start("now", job_shift=None)["timer"]["running"] is True


def test_restore_rejects_an_unreadable_date(env):
    ctrl, _ = env
    for date_ in ("", "not a date", "2026-13-40"):
        r = ctrl.restore_entry({"id": "x", "date": date_, "time_in": "09:00"})
        assert r["status"] == "invalid" and r["field"] == "entry"
    assert storage.load_all_entries() == []
    r = ctrl.restore_entry({"id": "x", "date": "20260901", "time_in": "09:00",
                            "time_out": "17:00", "job_shift": "Sales"})
    assert r["status"] == "saved" and storage.load_all_entries()[0].date == "2026-09-01"


def test_export_month_rejects_a_bad_month(env, tmp_path):
    ctrl, _ = env
    for month in (13, 0, "x", None):
        r = ctrl.export_month(2026, month, str(tmp_path / "x.xlsx"))
        assert r["status"] == "invalid" and r["field"] == "month"


# ── stats / export / import ──────────────────────────────────────────────────

def test_get_stats(env):
    ctrl, _ = env
    _add("2026-09-23", "09:00", "17:00")
    r = ctrl.get_stats("2026-09-21", "2026-09-27", "day")
    assert r["data"]["totals"]["minutes"] == 480 and len(r["data"]["buckets"]) == 7


def test_stats_span_reaches_every_manual_entry(env):
    """Shifts added by hand are often back-filled into earlier periods, which
    no fixed Stats period (week/month/3 months/year) shows. The span covers
    them all, so the All time range counts every saved shift."""
    ctrl, _ = env  # today is 2026-09-23
    assert ctrl.get_stats_span() == {**ctrl.get_stats_span(), "ok": True,
                                     "first": None, "last": None}
    drafts = [
        {"date": "3.2.2025", "time_in": "9", "time_out": "1730", "job_shift": "Sales"},
        {"date": "2025-08-14", "time_in": "22:00", "time_out": "06:00", "job_shift": ""},
        {"date": "23.9.", "time_in": "08:00", "time_out": "16:00", "job_shift": "Mine"},
        {"date": "2026-10-05", "time_in": "09:00", "time_out": "12:00", "job_shift": "Sales"},
    ]
    for d in drafts:
        assert ctrl.save_entry(d)["status"] == "saved"
    r = ctrl.get_stats_span()
    assert r["ok"] and (r["first"], r["last"]) == ("2025-02-03", "2026-10-05")
    data = ctrl.get_stats(r["first"], r["last"], "month")["data"]
    assert data["totals"]["shifts"] == 4
    assert data["totals"]["minutes"] == 510 + 480 + 480 + 180


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

    def fake(path, report=None):
        if path.endswith("bad.xlsx"):
            raise ValueError("not a timesheet")
        return 3, 1
    monkeypatch.setattr(import_excel, "import_from_file", fake)
    assert ctrl.import_excel([])["status"] == "cancelled"
    r = ctrl.import_excel(["a.xlsx", r"C:\some\dir\bad.xlsx"])
    assert (r["imported"], r["skipped"], r["files"]) == (3, 1, 2)
    assert r["message"].startswith("Imported 3 entries from 2 files.\n1 duplicate skipped.")
    # the base name, not the whole path
    assert r["errors"] == ["bad.xlsx: not a timesheet"]
    assert r["notes"] == []


def test_import_excel_says_why_nothing_was_found(env, tmp_path):
    from datetime import datetime
    from openpyxl import Workbook
    ctrl, _ = env
    empty = tmp_path / "Notes.xlsx"
    wb = Workbook()
    wb.active.append(["Just some notes", 1, 2])
    wb.save(empty)
    odd = tmp_path / "Odd.xlsx"
    wb = Workbook()
    wb.active.append([datetime(2026, 5, 10), "Sales", "half past", "17:00"])
    wb.save(odd)
    old = tmp_path / "Old.xls"
    old.write_bytes(b"\xd0\xcf\x11\xe0")
    r = ctrl.import_excel([str(empty), str(odd), str(old)])
    assert r["imported"] == 0
    assert r["notes"] == [
        "No timesheet rows found in Notes.xlsx: dates go in column A, "
        "times in B/C (or C/D with a shift in B).",
        "Odd.xlsx: found dates, but the start times weren't readable times "
        "(e.g. 9:30 or 9.30).",
    ]
    assert len(r["errors"]) == 1 and r["errors"][0].startswith("Old.xls: this isn't an .xlsx")
    assert "No timesheet rows found in Notes.xlsx" in r["message"]


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


def _pre_update_dirs():
    folder = os.path.join(os.path.dirname(storage.DATA_FILE), "backups")
    return sorted(f for f in os.listdir(folder) if f.startswith("pre-update-"))


def test_install_update_copies_user_files_first(env, monkeypatch):
    import updater
    ctrl, _ = env
    storage.set_default_job_shift("Support")
    storage.add_job_shift("Night")
    order = []
    monkeypatch.setattr(storage, "pre_update_copy",
                        lambda c, n, real=storage.pre_update_copy: (order.append("copy"),
                                                                    real(c, n))[1])
    monkeypatch.setattr(updater, "apply_update", lambda u, s: order.append("apply"))
    ctrl.remember_update("2.1.0", "https://x/setup.exe", None)
    assert ctrl.install_update(frozen=True, current="2.0.0")["ok"]
    assert order == ["copy", "apply"]
    assert _pre_update_dirs() == ["pre-update-v2.0.0-to-v2.1.0"]
    target = os.path.join(os.path.dirname(storage.DATA_FILE), "backups", _pre_update_dirs()[0])
    for name in ("data.json", "shifts.txt"):
        with open(os.path.join(target, name), "rb") as a, \
                open(os.path.join(os.path.dirname(storage.DATA_FILE), name), "rb") as b:
            assert a.read() == b.read()


def test_install_update_aborts_when_the_copy_fails(env, monkeypatch):
    import updater
    ctrl, _ = env
    storage.set_default_job_shift("Support")
    calls = []
    monkeypatch.setattr(updater, "apply_update", lambda u, s: calls.append(u))

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(storage.shutil, "copy2", boom)
    ctrl.remember_update("2.1.0", "https://x/setup.exe", None)
    r = ctrl.install_update(frozen=True, current="2.0.0")
    assert r["error"]["code"] == "update_failed" and "backed up" in r["message"]
    assert calls == []


def test_pre_update_copies_keep_the_newest_three(tmp_storage):
    storage.set_default_job_shift("Support")
    for i in range(5):
        storage.pre_update_copy("2.0.0", f"2.0.{i + 1}")
        folder = os.path.join(os.path.dirname(storage.DATA_FILE), "backups",
                              f"pre-update-v2.0.0-to-v2.0.{i + 1}")
        os.utime(folder, (1_000_000 + i, 1_000_000 + i))
    storage.pre_update_copy("2.0.0", "2.0.6")
    assert _pre_update_dirs() == ["pre-update-v2.0.0-to-v2.0.4", "pre-update-v2.0.0-to-v2.0.5",
                                  "pre-update-v2.0.0-to-v2.0.6"]
    assert storage.get_default_job_shift() == "Support"


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


def test_bootstrap_reports_restored_data_once(env, tmp_storage, monkeypatch):
    ctrl, _ = env
    _dlc_state(monkeypatch, "missing", None)
    _add(date="2026-09-20")
    _add(date="2026-09-21")
    (tmp_storage / "data.json").write_text("{ broken", encoding="utf-8")
    d = ctrl.bootstrap("2.0.0")["data"]
    assert d["data_recovery"]["source"].endswith("data.json.bak")
    assert "data.damaged-" in d["data_recovery"]["damaged_copy"]
    assert ctrl.bootstrap("2.0.0")["data"]["data_recovery"] is None


def test_bootstrap_without_damage_has_no_data_recovery(env, monkeypatch):
    ctrl, _ = env
    _dlc_state(monkeypatch, "missing", None)
    assert ctrl.bootstrap("2.0.0")["data"]["data_recovery"] is None


def test_relaunch_with_same_version_does_not_rewrite_data(env, tmp_storage, monkeypatch):
    ctrl, _ = env
    _dlc_state(monkeypatch, "missing", None)
    _add(date="2026-09-20")
    _add(date="2026-09-21")
    ctrl.bootstrap("2.0.0")   # records the version: a real change
    bak = (tmp_storage / "data.json.bak").read_bytes()
    data = (tmp_storage / "data.json").read_bytes()
    saves = []
    real = storage._save_raw
    monkeypatch.setattr(storage, "_save_raw", lambda d: (saves.append(1), real(d)))
    ctrl.bootstrap("2.0.0")
    assert saves == []
    assert (tmp_storage / "data.json.bak").read_bytes() == bak
    assert (tmp_storage / "data.json").read_bytes() == data


def test_get_recovery_reads_without_writing(env, tmp_storage, monkeypatch):
    ctrl, _ = env
    _add(date="2026-09-20")
    _crash(T0 - timedelta(hours=1))
    monkeypatch.setattr(storage, "_save_raw", _fail)
    r = ctrl.get_recovery()
    assert r["ok"] and r["recovery"]["job_shift"] == "Support"
    assert r["timer"]["recovery_pending"] is True
    assert r["data_recovery"] is None


def test_get_recovery_without_session(env):
    ctrl, _ = env
    r = ctrl.get_recovery()
    assert r["ok"] and r["recovery"] is None and r["timer"]["running"] is False


def test_get_recovery_hands_over_a_repair_once(env, tmp_storage):
    ctrl, _ = env
    _add(date="2026-09-20")
    _add(date="2026-09-21")
    (tmp_storage / "data.json").write_text("{ broken", encoding="utf-8")
    storage.load_all_entries()   # a mid-session read repairs data.json
    assert ctrl.get_recovery()["data_recovery"]["source"].endswith("data.json.bak")
    assert ctrl.get_recovery()["data_recovery"] is None


def test_ensure_shifts_file(env, tmp_storage):
    ctrl, _ = env
    path = ctrl.ensure_shifts_file()
    assert path == str(tmp_storage / "shifts.txt") and os.path.exists(path)


# ── achievements ─────────────────────────────────────────────────────────────

def _ach(ctrl):
    r = ctrl.get_achievements()
    assert r["ok"] and r["status"] == "ok"
    json.dumps(r, allow_nan=False)
    return r, {i["id"]: i for i in r["items"]}


def test_achievements_first_run_then_ack_all(env):
    ctrl, _clock = env
    _add("2026-09-21")
    r, items = _ach(ctrl)
    assert r["first_run"] is True
    assert r["newly"] == ["first_shift"]
    assert items["first_shift"]["met_on"] == "2026-09-21"
    assert set(items) == {a["id"] for a in __import__("achievements").CATALOGUE}
    assert ctrl.ack_achievements(r["newly"])["ok"]
    r, _ = _ach(ctrl)
    assert r["first_run"] is False and r["newly"] == []
    assert storage.get_achievements_seen() == {"first_shift": "2026-09-21"}


def test_achievements_empty_ack_ends_first_run(env):
    ctrl, _clock = env
    assert _ach(ctrl)[0]["first_run"] is True
    assert ctrl.ack_achievements([])["ok"]
    r, _ = _ach(ctrl)
    assert r["first_run"] is False and r["newly"] == []
    assert storage.get_achievements_seen() == {}


def test_achievements_newly_after_first_run(env):
    ctrl, _clock = env
    ctrl.ack_achievements([])
    _add("2026-09-22", "09:00", "17:00")
    r, _ = _ach(ctrl)
    assert r["first_run"] is False and r["newly"] == ["first_shift"]


def test_achievements_seen_are_permanent(env):
    ctrl, _clock = env
    e = _add("2026-09-21")
    ctrl.ack_achievements(["first_shift"])
    storage.delete_entry(e.id)
    r, items = _ach(ctrl)
    assert items["first_shift"]["met_on"] == "2026-09-21"
    assert items["first_shift"]["progress"]["cur"] == 1
    assert r["newly"] == []


def test_achievements_ack_skips_unmet_and_rejects_unknown(env):
    ctrl, _clock = env
    _add("2026-09-21")
    assert ctrl.ack_achievements(["hours_1000", "first_shift"])["ok"]
    assert storage.get_achievements_seen() == {"first_shift": "2026-09-21"}
    for bad in (["nope"], "first_shift", [1], None, {"first_shift": 1}):
        r = ctrl.ack_achievements(bad)
        assert r["status"] == "invalid" and r["field"] == "ids"
    assert storage.get_achievements_seen() == {"first_shift": "2026-09-21"}


def test_pet_stats(env):
    ctrl, clock = env  # today is 2026-09-23
    r = ctrl.get_pet_stats()
    assert r["ok"] and r == {**r, "lifetime_minutes": 0, "days": {}}
    _add("2026-07-01", "08:00", "16:00")  # outside the 8-week window, still lifetime
    _add("2026-07-30", "09:00", "10:00")  # first day of the 8-week window
    _add("2026-09-22", "22:00", "02:00")  # overnight: counts on its start date
    _add("2026-09-22", "08:00", "09:30")
    _add("2026-09-24", "08:00", "16:00")  # future
    r = ctrl.get_pet_stats()
    json.dumps(r, allow_nan=False)
    assert r["lifetime_minutes"] == 480 + 60 + 240 + 90
    assert r["days"] == {"2026-07-30": 60, "2026-09-22": 330}


def test_records(env):
    ctrl, clock = env  # today is Wed 2026-09-23
    r = ctrl.get_records()
    assert r["ok"] and r["total_shifts"] == 0 and r["longest_shift"] is None
    assert r["streak"] == {"current": 0, "best": 0}
    _add("2026-09-21", "07:30", "16:00")
    _add("2026-09-22", "09:00", "18:30")
    _add("2026-09-24", "05:00", "23:00")  # future: not a record yet
    r = ctrl.get_records()
    json.dumps(r, allow_nan=False)
    assert r["total_shifts"] == 2
    assert r["longest_shift"]["minutes"] == 570
    assert r["longest_shift"]["entry"]["date"] == "2026-09-22"
    assert r["earliest_start"]["time"] == "07:30"
    assert r["latest_finish"] == {**r["latest_finish"], "time": "18:30", "next_day": False}
    assert r["best_week"] == {"key": "2026-W39", "start": "2026-09-21", "minutes": 1080}
    assert r["streak"] == {"current": 2, "best": 2}
    storage.set_ui_prefs({"target_hours": 9})  # Monday's 8.5 h no longer counts
    assert ctrl.get_records()["streak"] == {"current": 1, "best": 1}


def test_achievements_ignore_future_entries(env):
    ctrl, clock = env  # today is 2026-09-23
    _add("2026-09-24")
    r, items = _ach(ctrl)
    assert r["newly"] == [] and items["first_shift"]["met_on"] is None
    clock.now = T0 + timedelta(days=1)
    assert _ach(ctrl)[0]["newly"] == ["first_shift"]


def test_achievements_use_target_and_pay_rate(env):
    ctrl, _clock = env
    storage.set_ui_prefs({"target_hours": 4})
    _add("2026-09-21", "09:00", "14:00")  # 5 h: past a 4 h target
    _, items = _ach(ctrl)
    assert items["lulz_blue_overtime"]["met_on"] == "2026-09-21"
    assert items["lulz_blue_overtime"]["progress"]["goal"] == 4
    storage.set_pay_rate(250.0)
    _, items = _ach(ctrl)
    assert items["earned_1k"]["met_on"] == "2026-09-21"


def test_achievements_ack_save_failure(env, monkeypatch):
    ctrl, _clock = env
    _add("2026-09-21")
    monkeypatch.setattr(storage, "add_achievements_seen", _fail)
    r = ctrl.ack_achievements(["first_shift"])
    assert r["status"] == "error" and r["error"]["code"] == "save_failed"
    assert storage.get_achievements_seen() is None


# ── entries written by a newer version (2.1.4 tolerant reader) ───────────────

_FUTURE = {"break_minutes": 30, "note": "covered", "updated_at": "2026-09-23T17:00:00Z"}


def _add_future(date="2026-09-23", t_in="09:00", t_out="17:00", id_="fut1"):
    data = storage._load_raw()
    data["entries"].append({"id": id_, "date": date, "job_shift": "Sales",
                            "time_in": t_in, "time_out": t_out, **_FUTURE})
    storage._save_raw(data)
    return id_


def _row(id_):
    return next(r for r in storage._load_raw()["entries"] if r.get("id") == id_)


def test_future_entry_in_month_stats_and_export(env, monkeypatch):
    import excel_export
    ctrl, _ = env
    storage.set_pay_rate(20.0)
    _add_future()
    d = ctrl.list_month(2026, 9)["data"]
    assert [e["id"] for e in d["entries"]] == ["fut1"]
    assert d["total_minutes"] == 480 and d["earnings"] == 160.0
    assert "note" not in d["entries"][0]          # rows stay the 2.1 shape
    r = ctrl.get_stats("2026-09-21", "2026-09-27", "day")
    assert r["data"]["totals"]["minutes"] == 480
    calls = []
    monkeypatch.setattr(excel_export, "export_month", lambda **k: calls.append(k))
    assert ctrl.export_month(2026, 9, "C:/x/out.xlsx")["status"] == "saved"
    assert [e.id for e in calls[0]["entries"]] == ["fut1"]


def test_edit_keeps_future_keys(env):
    ctrl, _ = env
    _add_future()
    r = ctrl.save_entry({"id": "fut1", "date": "2026-09-23", "job_shift": "Support",
                         "time_in": "08:00", "time_out": "16:00"})
    assert r["status"] == "saved"
    assert _row("fut1") == {"id": "fut1", "date": "2026-09-23", "job_shift": "Support",
                            "time_in": "08:00", "time_out": "16:00", **_FUTURE}


def test_new_entry_with_unknown_id_has_no_extras(env):
    ctrl, _ = env
    _add_future()
    r = ctrl.save_entry({"id": "other", "date": "2026-09-24",
                         "time_in": "08:00", "time_out": "16:00"})
    assert r["status"] == "saved" and set(_row("other")) == set(storage.ENTRY_FIELDS)


def test_inline_edit_keeps_future_keys(env):
    ctrl, _ = env
    _add_future()
    assert ctrl.update_entry_field("fut1", "time_out", "18:00")["status"] == "saved"
    assert _row("fut1")["time_out"] == "18:00"
    assert {k: _row("fut1")[k] for k in _FUTURE} == _FUTURE


def test_delete_and_undo_keep_future_keys(env):
    ctrl, _ = env
    _add_future()
    before = _row("fut1")
    token = ctrl.delete_entry("fut1")["confirm"]["token"]
    r = ctrl.delete_entry("fut1", _answer("delete_entry", "delete", token))
    assert r["status"] == "ok" and r["deleted"] == before
    assert storage.load_all_entries() == []
    r = ctrl.restore_entry(r["deleted"])
    assert r["status"] == "saved" and _row("fut1") == before


def test_restore_drops_deleted_flag(env):
    ctrl, _ = env
    r = ctrl.restore_entry({"id": "a", "date": "2026-09-23", "job_shift": "Sales",
                            "time_in": "09:00", "time_out": "17:00",
                            "deleted": True, "note": "x"})
    assert r["status"] == "saved"
    assert _row("a") == {"id": "a", "date": "2026-09-23", "job_shift": "Sales",
                         "time_in": "09:00", "time_out": "17:00", "note": "x"}
    assert [e.id for e in storage.load_all_entries()] == ["a"]


def test_restore_rejects_unstorable_extras(env):
    ctrl, _ = env
    base = {"id": "a", "date": "2026-09-23", "time_in": "09:00", "time_out": "17:00"}
    assert ctrl.restore_entry({**base, "note": object()})["status"] == "invalid"
    assert ctrl.restore_entry({**base, "note": {1, 2}})["status"] == "invalid"
    assert storage._load_raw()["entries"] == []


# ── overlapping shifts ───────────────────────────────────────────────────────

def test_save_entry_overlap_asks(env):
    ctrl, _ = env
    _add(t_in="09:00", t_out="17:00", job="Support")
    draft = {"date": "2026-09-23", "job_shift": "Sales", "time_in": "16:00", "time_out": "20:00"}
    r = ctrl.save_entry(draft)
    c = r["confirm"]
    assert c["kind"] == "overlap" and c["icon"] == "warning"
    assert c["default"] == "cancel" and c["cancel"] == "cancel"
    assert [o["id"] for o in c["options"]] == ["save", "cancel"]
    assert c["details"] == {"overlaps": 1}
    assert c["message"].startswith("This shift overlaps another entry:")
    assert "• Support on Wed 23 Sep, 09:00–17:00" in c["message"]
    assert len(storage.load_all_entries()) == 1
    assert ctrl.save_entry(draft, _answer("overlap", "cancel"))["status"] == "cancelled"
    assert len(storage.load_all_entries()) == 1
    assert ctrl.save_entry(draft, _answer("overlap", "save"))["status"] == "saved"
    assert len(storage.load_all_entries()) == 2


def test_save_entry_overlap_lists_at_most_three(env):
    ctrl, _ = env
    for h in (8, 10, 12, 14, 16):
        _add(t_in=f"{h:02d}:00", t_out=f"{h + 1:02d}:00")
    r = ctrl.save_entry({"date": "2026-09-23", "time_in": "07:00", "time_out": "18:00"})
    c = r["confirm"]
    assert c["details"] == {"overlaps": 5}
    assert c["message"].startswith("This shift overlaps 5 other entries:")
    assert c["message"].count("\n• ") == 4 and "• and 2 more" in c["message"]


def test_save_entry_touching_and_own_copy_do_not_ask(env):
    ctrl, _ = env
    e = _add()
    _add(t_in="17:00", t_out="20:00")
    r = ctrl.save_entry({"id": e.id, "date": e.date, "time_in": "08:00", "time_out": "17:00"})
    assert r["status"] == "saved"


def test_save_entry_known_overlap_not_asked_again(env):
    ctrl, _ = env
    _add(t_in="09:00", t_out="17:00")
    e = _add(t_in="16:00", t_out="20:00")
    # already overlapping: changing its job or end doesn't ask again
    r = ctrl.save_entry({"id": e.id, "date": e.date, "job_shift": "Training",
                         "time_in": "16:00", "time_out": "21:00"})
    assert r["status"] == "saved"


def test_save_entry_new_overlap_on_edit_asks(env):
    ctrl, _ = env
    _add(t_in="09:00", t_out="12:00")
    e = _add(t_in="13:00", t_out="17:00")
    r = ctrl.save_entry({"id": e.id, "date": e.date, "time_in": "11:00", "time_out": "17:00"})
    assert r["confirm"]["kind"] == "overlap"


def test_inline_edit_overlap(env):
    ctrl, _ = env
    _add(t_in="09:00", t_out="12:00")
    e = _add(t_in="13:00", t_out="17:00")
    r = ctrl.update_entry_field(e.id, "time_in", "11:00")
    assert r["confirm"]["kind"] == "overlap"
    assert ctrl.update_entry_field(e.id, "time_in", "11:00",
                                   _answer("overlap", "cancel"))["status"] == "cancelled"
    assert ctrl.get_entry(e.id)["entry"]["time_in"] == "13:00"
    r = ctrl.update_entry_field(e.id, "time_in", "11:00", _answer("overlap", "save"))
    assert r["status"] == "saved"
    # now a known overlap: a further edit that keeps it doesn't ask
    assert ctrl.update_entry_field(e.id, "time_out", "18:00")["status"] == "saved"


def test_stop_overlap_warning(env):
    ctrl, clock = env
    _add(t_in="11:00", t_out="12:00", job="Training")
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=4)
    r = ctrl.timer_stop()
    assert r["status"] == "saved"
    assert r["overlap_warning"] == ("This shift overlaps another entry:\n"
                                    "• Training on Wed 23 Sep, 11:00–12:00")
    assert len(storage.load_all_entries()) == 2
    json.dumps(r, allow_nan=False)


def test_stop_without_overlap_has_no_warning(env):
    ctrl, clock = env
    _add(t_in="06:00", t_out="10:00")
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=1)
    assert "overlap_warning" not in ctrl.timer_stop()


def test_recovery_save_overlap_warning(env, tmp_timer):
    ctrl, _ = env
    _add(t_in="08:00", t_out="09:00")
    _crash(T0 - timedelta(hours=3))
    r = ctrl.recovery_resolve("save", end="9.45")
    assert r["status"] == "saved" and "overlaps another entry" in r["overlap_warning"]


def test_overlap_warning_swallows_read_errors(env, monkeypatch):
    ctrl, clock = env
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=1)
    monkeypatch.setattr(ctrl, "_overlaps", _fail)
    r = ctrl.timer_stop()
    assert r["status"] == "saved" and "overlap_warning" not in r
    assert len(storage.load_all_entries()) == 1


def test_list_month_overlap_flag(env):
    ctrl, _ = env
    _add("2026-08-31", "22:00", "06:00")          # previous month, overnight
    _add("2026-09-01", "05:00", "09:00")          # overlaps it on the 1st
    _add("2026-09-10", "09:00", "17:00")
    _add("2026-09-10", "17:00", "19:00")          # touching only
    _add("2026-09-12", "09:00", "")               # open
    rows = ctrl.list_month(2026, 9)["data"]["entries"]
    assert [(r["date"], r["overlap"]) for r in rows] == [
        ("2026-09-01", True), ("2026-09-10", False), ("2026-09-10", False),
        ("2026-09-12", False)]
    prev = [e for e in storage.load_all_entries() if e.date == "2026-08-31"][0]
    assert rows[0]["overlap_with"] == [{"id": prev.id, "date": "2026-08-31",
                                        "job_shift": prev.job_shift,
                                        "time_in": "22:00", "time_out": "06:00"}]
    assert all(r["overlap_with"] == [] for r in rows[1:])


def test_export_remembers_last_path(env, monkeypatch):
    import excel_export
    ctrl, _ = env
    monkeypatch.setattr(excel_export, "export_month", lambda **k: None)
    assert ctrl.last_export() is None
    ctrl.export_month(2026, 9, "")
    assert ctrl.last_export() is None
    ctrl.export_month(2026, 9, "C:/x/out.xlsx")
    assert ctrl.last_export() == "C:/x/out.xlsx"


# ── your data: backups & restore ─────────────────────────────────────────────

def test_backup_now_and_list(env):
    ctrl, _ = env
    r = ctrl.backup_now()
    assert r["status"] == "ok" and r["backup"] is None   # nothing saved yet
    _add()
    r = ctrl.backup_now()
    assert r["status"] == "saved" and r["backup"].startswith("manual-")
    listed = ctrl.list_backups()
    assert listed["ok"] and listed["data_dir"] == storage.DATA_DIR
    assert r["backup"] in [b["name"] for b in listed["backups"]]


def test_backup_now_write_failure(env, monkeypatch):
    ctrl, _ = env
    _add()
    monkeypatch.setattr(storage, "_stamped_copy", _fail)
    r = ctrl.backup_now()
    assert r["error"]["code"] == "save_failed"


def test_restore_backup_flow(env, tmp_storage):
    ctrl, _ = env
    keep = _add(date="2026-09-01")
    name = ctrl.backup_now()["backup"]
    _add(date="2026-09-02")
    _add(date="2026-09-03")
    r = ctrl.restore_backup(name)
    assert r["status"] == "needs_confirm"
    c = r["confirm"]
    assert c["kind"] == "restore_backup" and c["default"] == "cancel"
    assert c["details"]["name"] == name
    assert c["details"]["entries"] == 1 and c["details"]["current_entries"] == 3
    assert "(1 shift)" in c["message"] and "3 shifts now" in c["message"]
    # cancel changes nothing
    r = ctrl.restore_backup(name, _answer("restore_backup", "cancel", c["token"]))
    assert r["status"] == "cancelled"
    assert len(storage.load_all_entries()) == 3
    r = ctrl.restore_backup(name, _answer("restore_backup", "restore", c["token"]))
    assert r["status"] == "saved", r
    assert [e.id for e in storage.load_all_entries()] == [keep.id]
    assert r["restored"] == name and r["safety_copy"].startswith("pre-restore-")
    safety = os.path.join(storage.backups_dir(), r["safety_copy"])
    with open(safety, encoding="utf-8") as f:
        assert len(json.load(f)["entries"]) == 3
    assert "settings" in r and "timer" in r and "shifts" in r


def test_restore_backup_rejects_names_outside_the_list(env):
    ctrl, _ = env
    _add()
    os.makedirs(storage.backups_dir(), exist_ok=True)
    with open(os.path.join(storage.backups_dir(), "mine.json"), "w", encoding="utf-8") as f:
        f.write('{"entries": []}')
    for bad in ("mine.json", "../data.json", storage.DATA_FILE, None, 3):
        r = ctrl.restore_backup(bad, _answer("restore_backup", "restore"))
        assert r["status"] == "invalid" and r["field"] == "name"
    assert len(storage.load_all_entries()) == 1


def test_restore_backup_refuses_a_damaged_copy(env):
    ctrl, _ = env
    _add()
    os.makedirs(storage.backups_dir(), exist_ok=True)
    with open(os.path.join(storage.backups_dir(), "data-2020-01-01.json"), "w",
              encoding="utf-8") as f:
        f.write("{oops")
    r = ctrl.restore_backup("data-2020-01-01.json", _answer("restore_backup", "restore"))
    assert r["status"] == "invalid"
    assert len(storage.load_all_entries()) == 1


def test_restore_backup_stale_token(env):
    ctrl, _ = env
    _add()
    name = ctrl.backup_now()["backup"]
    token = ctrl.restore_backup(name)["confirm"]["token"]
    with open(os.path.join(storage.backups_dir(), name), "w", encoding="utf-8") as f:
        f.write('{"entries": [], "pay_rate": 5, "padding": "changed"}')
    r = ctrl.restore_backup(name, _answer("restore_backup", "restore", token))
    assert r["error"]["code"] == "stale"
    assert len(storage.load_all_entries()) == 1


def test_restore_backup_write_failure_changes_nothing(env, monkeypatch):
    ctrl, _ = env
    _add()
    name = ctrl.backup_now()["backup"]
    _add(date="2026-09-02")
    token = ctrl.restore_backup(name)["confirm"]["token"]
    monkeypatch.setattr(storage, "_stamped_copy", _fail)
    r = ctrl.restore_backup(name, _answer("restore_backup", "restore", token))
    assert r["error"]["code"] == "save_failed"
    assert len(storage.load_all_entries()) == 2


def test_restore_backup_keeps_a_running_shift(env):
    ctrl, clock = env
    _add(date="2026-09-01")
    name = ctrl.backup_now()["backup"]
    _started(ctrl, clock)
    token = ctrl.restore_backup(name)["confirm"]["token"]
    r = ctrl.restore_backup(name, _answer("restore_backup", "restore", token))
    assert r["status"] == "saved" and r["timer"]["running"]
