"""Settings → Round shift times: the rule (utils.round_shift), the setting in
data.json, and the timer saves that use it (STOP, F5, stop at, recovery)."""
import json
import os
from datetime import datetime, timedelta

import pytest

import storage
from timer import WorkTimer
from utils import round_shift
from webapp.controller import ShiftController

_CASES = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures",
                                     "rounding_cases.json"), encoding="utf-8"))["cases"]


@pytest.mark.parametrize("t_in,t_out,mode,step,expected", _CASES)
def test_round_shift_cases(t_in, t_out, mode, step, expected):
    assert round_shift(t_in, t_out, mode, step) == (tuple(expected) if expected else None)


def test_round_shift_never_exceeds_the_long_shift_limit():
    # rounding up a shift that didn't need the over-14 h confirm never makes it
    # one: 14 h is a whole number of every step
    from utils import entry_minutes, is_long_shift
    for step in (15, 30, 60):
        for mode in ("up", "nearest"):
            for minutes in range(1, 14 * 60 + 1):
                end = f"{(8 * 60 + minutes) // 60 % 24:02d}:{minutes % 60:02d}"
                out = round_shift("08:00", end, mode, step)
                if out:
                    assert not is_long_shift(entry_minutes(*out)), (step, mode, minutes)


@pytest.mark.parametrize("step", [True, 30.0, 60.0, "30"])
def test_round_shift_refuses_a_step_that_is_not_an_int(step):
    assert round_shift("09:07", "16:41", "up", step) is None


# ── the setting ──────────────────────────────────────────────────────────────

def test_rounding_off_by_default(tmp_storage):
    assert storage.get_rounding() == {"enabled": False, "mode": "nearest", "step": 30}


def test_rounding_saved_and_kept_as_a_top_level_key(tmp_storage):
    storage.save_settings({"rounding": {"enabled": True, "mode": "up", "step": 15}})
    assert storage.get_rounding() == {"enabled": True, "mode": "up", "step": 15}
    raw = json.load(open(storage.DATA_FILE, encoding="utf-8"))
    assert raw["rounding"] == {"enabled": True, "mode": "up", "step": 15}


@pytest.mark.parametrize("bad", [
    None, "up", [], {"enabled": True, "mode": "up"},
    {"enabled": "yes", "mode": "up", "step": 30},
    {"enabled": True, "mode": "sideways", "step": 30},
    {"enabled": True, "mode": "up", "step": 20},
    {"enabled": True, "mode": "up", "step": True},
    {"enabled": True, "mode": "up", "step": 30.5},
    {"enabled": True, "mode": "up", "step": 30.0},
    {"enabled": True, "mode": "up", "step": 60.0},
    {"enabled": True, "mode": "up", "step": 30, "extra": 1},
])
def test_rounding_save_is_strict(tmp_storage, bad):
    with pytest.raises(ValueError):
        storage.save_settings({"rounding": bad})
    assert storage.get_rounding()["enabled"] is False


@pytest.mark.parametrize("junk,expected", [
    ("on", {"enabled": False, "mode": "nearest", "step": 30}),
    ({"enabled": 1, "mode": "up", "step": 60}, {"enabled": False, "mode": "up", "step": 60}),
    ({"enabled": True, "mode": "UP", "step": "30"}, {"enabled": True, "mode": "nearest", "step": 30}),
    ({"enabled": True, "step": True}, {"enabled": True, "mode": "nearest", "step": 30}),
    ({"enabled": True, "mode": "up", "step": 60.0}, {"enabled": True, "mode": "up", "step": 30}),
])
def test_rounding_hand_edited_junk_reads_leniently(tmp_storage, junk, expected):
    raw = storage._load_raw()
    raw["rounding"] = junk
    storage._save_raw(raw)
    assert storage.get_rounding() == expected


# ── timer saves ──────────────────────────────────────────────────────────────

class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self):
        return self.now


T0 = datetime(2026, 9, 23, 9, 7, 25)


@pytest.fixture()
def env(tmp_storage, tmp_timer):
    clock = Clock(T0)
    return ShiftController(timer=WorkTimer(), clock=clock), clock


def _round(mode="nearest", step=30, enabled=True):
    storage.save_settings({"rounding": {"enabled": enabled, "mode": mode, "step": step}})


def _start(ctrl, clock, start=T0, job="Sales"):
    clock.now = start
    r = ctrl.timer_start("now", job_shift=job)
    assert r["status"] == "ok"
    return r["timer"]["start_iso"]


def _times(e):
    return e["time_in"], e["time_out"]


def test_stop_rounds_and_says_from_what(env):
    ctrl, clock = env
    _round("up", 30)
    _start(ctrl, clock)
    clock.now = T0.replace(hour=16, minute=41, second=50)
    r = ctrl.timer_stop("button")
    assert r["status"] == "saved"
    assert _times(r["entry"]) == ("09:00", "17:00") and r["entry"]["minutes"] == 480
    before = r["rounded"]["before"]
    assert _times(before) == ("09:07", "16:41")
    assert before["id"] == r["entry"]["id"] and before["date"] == "2026-09-23"
    assert before["job_shift"] == "Sales"
    [saved] = storage.load_all_entries()
    assert (saved.time_in, saved.time_out) == ("09:00", "17:00")


def test_keep_exact_is_a_revert(env):
    ctrl, clock = env
    _round("nearest", 60)
    _start(ctrl, clock)
    clock.now = T0.replace(hour=16, minute=41)
    r = ctrl.timer_stop("button")
    k = ctrl.revert_entry(r["rounded"]["before"], r["rounded"]["token"])
    assert k["status"] == "saved" and _times(k["entry"]) == ("09:07", "16:41")
    [saved] = storage.load_all_entries()
    assert (saved.time_in, saved.time_out) == ("09:07", "16:41")
    # once edited again, the token no longer matches
    again = ctrl.revert_entry(r["rounded"]["before"], r["rounded"]["token"])
    assert again["status"] == "error" and again["error"]["code"] == "stale"


def test_keep_exact_after_a_delete_does_not_bring_it_back(env):
    ctrl, clock = env
    _round()
    _start(ctrl, clock)
    clock.now = T0.replace(hour=16, minute=41)
    r = ctrl.timer_stop("button")
    ask = ctrl.delete_entry(r["entry"]["id"])
    gone = ctrl.delete_entry(r["entry"]["id"], [{"kind": "delete_entry", "choice": "delete",
                                                 "token": ask["confirm"]["token"]}])
    assert gone["status"] == "ok"
    k =ctrl.revert_entry(r["rounded"]["before"], r["rounded"]["token"])
    assert k["status"] == "error" and k["error"]["code"] == "not_found"
    assert storage.load_all_entries() == []


def test_stop_unrounded_while_off_or_already_round(env):
    ctrl, clock = env
    _round(enabled=False)
    _start(ctrl, clock)
    clock.now = T0.replace(hour=16, minute=41)
    r = ctrl.timer_stop("button")
    assert _times(r["entry"]) == ("09:07", "16:41") and "rounded" not in r

    _round()
    _start(ctrl, clock, T0.replace(hour=18, minute=0, second=0))
    clock.now = T0.replace(hour=19, minute=0, second=30)
    r = ctrl.timer_stop("button")
    assert _times(r["entry"]) == ("18:00", "19:00") and "rounded" not in r


def test_too_short_to_round_keeps_the_exact_times(env):
    ctrl, clock = env
    _round("down", 15)
    _start(ctrl, clock)
    clock.now = T0.replace(minute=17)
    r = ctrl.timer_stop("button")
    assert r["status"] == "saved" and _times(r["entry"]) == ("09:07", "09:17")
    assert "rounded" not in r


def test_f5_rounds_after_its_confirm(env):
    ctrl, clock = env
    _round("down", 60)
    token = _start(ctrl, clock)
    clock.now = T0.replace(hour=16, minute=41)
    ask = ctrl.timer_stop("shortcut")
    assert ask["status"] == "needs_confirm"
    r = ctrl.timer_stop("shortcut", [{"kind": "stop_shift", "choice": "stop",
                                      "token": ask["confirm"]["token"]}])
    assert token and r["status"] == "saved"
    assert _times(r["entry"]) == ("09:00", "16:00")


def test_stop_at_rounds_the_typed_end(env):
    ctrl, clock = env
    _round("nearest", 15)
    _start(ctrl, clock)
    clock.now = T0.replace(hour=17, minute=30)
    r = ctrl.timer_stop_at("16:41")
    assert _times(r["entry"]) == ("09:00", "16:30")
    assert _times(r["rounded"]["before"]) == ("09:07", "16:41")


def test_overnight_start_near_midnight_keeps_its_date(env):
    ctrl, clock = env
    _round("nearest", 15)
    start = datetime(2026, 9, 23, 23, 55, 10)
    _start(ctrl, clock, start)
    clock.now = start + timedelta(hours=8, minutes=10)
    r = ctrl.timer_stop("button")
    assert r["entry"]["date"] == "2026-09-23"
    assert _times(r["entry"]) == ("23:45", "08:00") and r["entry"]["overnight"]


def test_recovery_save_rounds(env):
    ctrl, clock = env
    _round("up", 30)
    WorkTimer().start("Support", start_time=datetime(2026, 9, 23, 7, 3))
    clock.now = datetime(2026, 9, 23, 12, 0)
    r = ctrl.recovery_resolve("save", end="11:50")
    assert r["status"] == "saved" and r["recovery"] is None
    assert _times(r["entry"]) == ("07:00", "12:00")
    assert _times(r["rounded"]["before"]) == ("07:03", "11:50")


def test_manual_entries_are_never_rounded(env):
    ctrl, _ = env
    _round("up", 60)
    r = ctrl.save_entry({"date": "2026-09-23", "job_shift": "Sales",
                         "time_in": "09:07", "time_out": "16:41"})
    assert _times(r["entry"]) == ("09:07", "16:41") and "rounded" not in r


def test_an_unreadable_setting_saves_the_shift_exact(env, monkeypatch):
    ctrl, clock = env
    _round()
    _start(ctrl, clock)
    clock.now = T0.replace(hour=16, minute=41)

    def locked():
        raise OSError("locked")
    monkeypatch.setattr(storage, "get_rounding", locked)
    r = ctrl.timer_stop("button")
    assert r["status"] == "saved" and _times(r["entry"]) == ("09:07", "16:41")


def test_a_float_step_in_data_json_still_saves_the_shift(env):
    # a hand-edited 30.0 reads as the default 30, and the save goes on
    ctrl, clock = env
    raw = storage._load_raw()
    raw["rounding"] = {"enabled": True, "mode": "down", "step": 60.0}
    storage._save_raw(raw)
    _start(ctrl, clock)
    clock.now = T0.replace(hour=16, minute=41)
    r = ctrl.timer_stop("button")
    assert r["status"] == "saved" and _times(r["entry"]) == ("09:00", "16:30")


def test_a_rounding_crash_saves_the_shift_exact(env, monkeypatch):
    ctrl, clock = env
    _round()
    _start(ctrl, clock)
    clock.now = T0.replace(hour=16, minute=41)

    def broken(*_a):
        raise ValueError("boom")
    import webapp.controller as controller
    monkeypatch.setattr(controller, "round_shift", broken)
    r = ctrl.timer_stop("button")
    assert r["status"] == "saved" and _times(r["entry"]) == ("09:07", "16:41")
    assert "rounded" not in r
    assert "rounding failed" in open(storage.ERROR_LOG, encoding="utf-8").read()


def test_overlap_warning_uses_the_rounded_times(env):
    ctrl, clock = env
    storage.save_entry(storage.WorkEntry(id=storage.new_entry_id(), date="2026-09-23",
                                         job_shift="Sales", time_in="17:00", time_out="18:00"))
    _round("up", 60)
    _start(ctrl, clock)
    clock.now = T0.replace(hour=16, minute=41)
    r = ctrl.timer_stop("button")
    # 09:07–16:41 alone doesn't touch 17:00; rounded to 09:00–17:00 it only meets it
    assert _times(r["entry"]) == ("09:00", "17:00") and "overlap_warning" not in r


def test_overlap_check_sees_the_rounded_times_not_the_exact_ones(env):
    ctrl, clock = env
    storage.save_entry(storage.WorkEntry(id=storage.new_entry_id(), date="2026-09-23",
                                         job_shift="Sales", time_in="16:45", time_out="17:30"))
    storage.save_entry(storage.WorkEntry(id=storage.new_entry_id(), date="2026-09-24",
                                         job_shift="Sales", time_in="16:00", time_out="17:00"))
    # exact 09:07-16:41 is clear of 16:45; rounded up to 09:00-17:00 it overlaps
    _round("up", 60)
    _start(ctrl, clock)
    clock.now = T0.replace(hour=16, minute=41)
    r = ctrl.timer_stop("button")
    assert _times(r["entry"]) == ("09:00", "17:00") and "overlap_warning" in r
    # exact 09:07-16:10 overlaps 16:00; rounded down to 09:00-16:00 it only meets it
    _round("down", 60)
    day2 = T0 + timedelta(days=1)
    _start(ctrl, clock, day2)
    clock.now = day2.replace(hour=16, minute=10)
    r = ctrl.timer_stop("button")
    assert _times(r["entry"]) == ("09:00", "16:00") and "overlap_warning" not in r


# ── settings API ─────────────────────────────────────────────────────────────

def _draft(**over):
    d = {"default_start_time": "09:30", "pay_rate": "20", "default_job_shift": "",
         "export_format": "Simple", "export_include_pay": False, "appearance": "System",
         "ui_prefs": {}}
    d.update(over)
    return d


def test_settings_carry_rounding(env):
    ctrl, _ = env
    assert ctrl.get_settings()["settings"]["rounding"] == storage.ROUNDING_DEFAULT
    on = {"enabled": True, "mode": "down", "step": 60}
    r = ctrl.save_settings(_draft(rounding=on))
    assert r["status"] == "saved" and r["settings"]["rounding"] == on
    # left out = unchanged
    assert ctrl.save_settings(_draft())["settings"]["rounding"] == on


def test_settings_refuse_bad_rounding_and_write_nothing(env):
    ctrl, _ = env
    r = ctrl.save_settings(_draft(pay_rate="35", rounding={"enabled": True, "mode": "up", "step": 45}))
    assert r["status"] == "invalid" and r["field"] == "rounding"
    s = ctrl.get_settings()["settings"]
    assert s["pay_rate"] == 20.0 and s["rounding"]["enabled"] is False
