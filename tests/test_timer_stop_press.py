"""Stop time = when STOP was pressed; DST-safe elapsed time (fall-back night)."""
import json
from datetime import datetime, timedelta

import pytest

import timer as tm
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


def _started(ctrl, clock, start=T0, job="Sales"):
    clock.now = start
    r = ctrl.timer_start("now", job_shift=job)
    assert r["status"] == "ok" and r["timer"]["running"]
    return r["timer"]["start_iso"]


def _reply(r, choice):
    """Answer a confirm the way the frontend does (echoing its token)."""
    c = r["confirm"]
    return [{"kind": c["kind"], "choice": choice, "token": c["token"]}]


# ── stop time = when STOP was pressed ────────────────────────────────────────

def test_stop_saves_press_minute_not_answer_minute(env):
    ctrl, clock = env
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=14, minutes=30)          # STOP pressed 00:30
    r = ctrl.timer_stop("button")
    assert r["confirm"]["kind"] == "long_shift"
    assert r["confirm"]["details"]["start_iso"] == "2026-09-23T10:00:00"
    assert r["confirm"]["token"] == "2026-09-23T10:00:00@2026-09-24T00:30:00"
    clock.now = T0 + timedelta(hours=15, minutes=12)          # answered 01:12
    r = ctrl.timer_stop("button", _reply(r, "stop"))
    assert r["status"] == "saved" and r["entry"]["time_out"] == "00:30"


def test_shortcut_stop_saves_press_minute(env):
    ctrl, clock = env
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=7, minutes=59)
    r = ctrl.timer_stop("shortcut")
    clock.now = T0 + timedelta(hours=8, minutes=20)
    r = ctrl.timer_stop("shortcut", _reply(r, "stop"))
    assert r["entry"]["time_out"] == "17:59"


def test_over_24h_discard_chain_keeps_press_token(env):
    ctrl, clock = env
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=25)
    r = ctrl.timer_stop("button")
    first = _reply(r, "discard")
    clock.now = T0 + timedelta(hours=25, minutes=5)
    r = ctrl.timer_stop("button", first)
    assert r["confirm"]["kind"] == "discard_shift"
    r = ctrl.timer_stop("button", first + _reply(r, "discard"))
    assert r["status"] == "discarded"


def test_close_stop_saves_press_minute(env):
    ctrl, clock = env
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=8)
    r = ctrl.close_app()
    clock.now = T0 + timedelta(hours=9)
    r = ctrl.close_app(_reply(r, "stop_close"))
    assert r["status"] == "saved" and r["quit"] is True
    assert r["entry"]["time_out"] == "18:00"


def test_plain_start_token_still_accepted(env):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=15)
    r = ctrl.timer_stop("button", [{"kind": "long_shift", "choice": "stop", "token": token}])
    assert r["status"] == "saved" and r["entry"]["time_out"] == "01:00"


def test_press_token_for_another_start_is_stale(env):
    ctrl, clock = env
    _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=15)
    r = ctrl.timer_stop("button", [{"kind": "long_shift", "choice": "stop",
                                    "token": "2026-09-22T10:00:00@2026-09-23T01:00:00"}])
    assert r["error"]["code"] == "stale" and r["timer"]["running"]


def test_press_time_after_now_is_stale(env):
    ctrl, clock = env
    token = _started(ctrl, clock)
    clock.now = T0 + timedelta(hours=15)
    r = ctrl.timer_stop("button", [{"kind": "long_shift", "choice": "stop",
                                    "token": f"{token}@2026-09-30T00:00:00"}])
    assert r["error"]["code"] == "stale" and r["timer"]["running"]


# ── DST: the night the clocks go back ────────────────────────────────────────

@pytest.fixture()
def helsinki(monkeypatch):
    """Local time = Europe/Helsinki; on 2026-10-25 04:00 the clocks go back
    to 03:00, so 03:00–04:00 happens twice."""
    from zoneinfo import ZoneInfo
    zone = ZoneInfo("Europe/Helsinki")
    monkeypatch.setattr(tm, "_epoch", lambda dt: dt.replace(tzinfo=zone).timestamp())


def test_elapsed_between_counts_the_repeated_hour(helsinki):
    assert tm.elapsed_between(datetime(2026, 10, 25, 0, 0),
                              datetime(2026, 10, 25, 6, 0)) == 7 * 3600
    # spring forward loses one
    assert tm.elapsed_between(datetime(2026, 3, 29, 0, 0),
                              datetime(2026, 3, 29, 6, 0)) == 5 * 3600


def test_stop_across_fall_back_shows_real_elapsed(env, helsinki):
    ctrl, clock = env
    _started(ctrl, clock, start=datetime(2026, 10, 24, 22, 0))
    clock.now = datetime(2026, 10, 25, 6, 0)
    r = ctrl.timer_stop("shortcut")
    assert r["confirm"]["details"]["elapsed_minutes"] == 9 * 60
    assert "9h 00m ago" in r["confirm"]["message"]
    r = ctrl.timer_stop("shortcut", _reply(r, "stop"))
    assert r["entry"]["time_in"] == "22:00" and r["entry"]["time_out"] == "06:00"


def test_epoch_ms_counts_from_the_right_pass(env, helsinki):
    ctrl, clock = env
    first = datetime(2026, 10, 25, 3, 30)
    _started(ctrl, clock, start=datetime(2026, 10, 25, 3, 30, fold=1))
    ms = ctrl.timer_state()["start_epoch_ms"]
    assert ms == int(tm._epoch(first) * 1000) + 3600 * 1000


def test_start_in_repeated_hour_keeps_its_fold(env, helsinki, tmp_timer):
    ctrl, clock = env
    _started(ctrl, clock, start=datetime(2026, 10, 25, 3, 30, fold=1))
    assert json.load(open(tm._SESSION_FILE))["start_fold"] == 1
    # the app closes; the next launch recovers the shift from session.json
    clock.now = datetime(2026, 10, 25, 5, 0)
    ctrl2 = ShiftController(timer=WorkTimer(), clock=clock)
    rec = ctrl2.recovery()
    assert rec["elapsed_minutes"] == 90
    r = ctrl2.recovery_resolve("resume")
    assert r["timer"]["running"] and ctrl2.running_start().fold == 1


def test_old_session_without_fold_still_loads(env, tmp_timer):
    ctrl, clock = env
    with open(tm._SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"job_shift": "Sales", "start": "2026-09-23T08:00:00"}, f)
    rec = ctrl.recovery()
    assert rec["start_iso"] == "2026-09-23T08:00:00" and rec["elapsed_minutes"] == 120


def test_normal_start_writes_no_fold_key(env, tmp_timer):
    ctrl, clock = env
    _started(ctrl, clock)
    assert "start_fold" not in json.load(open(tm._SESSION_FILE))
