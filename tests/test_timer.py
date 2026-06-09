"""Tests for timer — WorkTimer state machine, session persistence, _is_newer."""
import json
import pytest
from datetime import datetime, timedelta

import timer as tm
from timer import WorkTimer, load_saved_session, clear_saved_session


# ── version comparison ────────────────────────────────────────────────────────

from updater import _is_newer

@pytest.mark.parametrize("latest, current, expected", [
    ("1.1.0", "1.0.0", True),
    ("2.0.0", "1.9.9", True),
    ("1.0.1", "1.0.0", True),
    ("1.0.0", "1.0.0", False),   # same version
    ("1.0.0", "1.1.0", False),   # older than current
    ("0.9.9", "1.0.0", False),
])
def test_is_newer(latest, current, expected):
    assert _is_newer(latest, current) is expected


# ── WorkTimer state ───────────────────────────────────────────────────────────

def test_idle_by_default():
    t = WorkTimer()
    assert t.is_running is False


def test_start_sets_running(tmp_timer):
    t = WorkTimer()
    t.start("Sales")
    assert t.is_running is True


def test_start_idempotent(tmp_timer):
    """Starting an already-running timer has no effect."""
    t = WorkTimer()
    t.start("Sales")
    first_start = t._start_dt
    t.start("Support")          # second call ignored
    assert t._start_dt == first_start
    assert t._job_shift == "Sales"


def test_stop_returns_dict(tmp_timer):
    t = WorkTimer()
    t.start("Sales")
    result = t.stop()
    assert result is not None
    assert set(result.keys()) == {"date", "job_shift", "time_in", "time_out"}
    assert result["job_shift"] == "Sales"


def test_stop_resets_state(tmp_timer):
    t = WorkTimer()
    t.start("Sales")
    t.stop()
    assert t.is_running is False


def test_stop_when_idle_returns_none():
    t = WorkTimer()
    assert t.stop() is None


def test_elapsed_str_idle():
    assert WorkTimer().elapsed_str() == "00:00"


def test_elapsed_str_running(tmp_timer):
    t = WorkTimer()
    # Backdate start by 90 minutes
    start = datetime.now() - timedelta(minutes=90)
    t.start("Sales", start_time=start)
    assert t.elapsed_str() == "01:30"


def test_elapsed_seconds_idle():
    assert WorkTimer().elapsed_seconds() == pytest.approx(0.0)


def test_start_time_str_idle():
    assert WorkTimer().start_time_str() == ""


def test_start_time_str_running(tmp_timer):
    t = WorkTimer()
    fixed = datetime(2026, 5, 10, 9, 30, 0)
    t.start("Sales", start_time=fixed)
    assert t.start_time_str() == "09:30"


def test_custom_start_time(tmp_timer):
    t = WorkTimer()
    fixed = datetime(2026, 5, 10, 8, 0, 0)
    t.start("Sales", start_time=fixed)
    result = t.stop()
    assert result["time_in"] == "08:00"
    assert result["date"] == "2026-05-10"


# ── session persistence ───────────────────────────────────────────────────────

def test_session_written_on_start(tmp_timer):
    t = WorkTimer()
    t.start("Sales")
    session = load_saved_session()
    assert session is not None
    assert session["job_shift"] == "Sales"


def test_session_deleted_on_stop(tmp_timer):
    t = WorkTimer()
    t.start("Sales")
    t.stop()
    assert load_saved_session() is None


def test_load_saved_session_none_when_missing(tmp_timer):
    assert load_saved_session() is None


def test_clear_saved_session(tmp_timer):
    t = WorkTimer()
    t.start("Sales")
    assert load_saved_session() is not None
    clear_saved_session()
    assert load_saved_session() is None
