"""Tests for utils.parse_time_input, is_valid_time, entry_minutes, is_overnight,
resolve_start_time, week_key, parse_date_input, parse_pay_rate,
start_time_needs_confirm, is_long_shift, add_hours, format_duration, get_app_dir."""
import os
import sys
from datetime import date, datetime

import pytest
from utils import (parse_time_input, is_valid_time, entry_minutes, is_overnight,
                   resolve_start_time, week_key, parse_date_input, parse_pay_rate,
                   start_time_needs_confirm, is_long_shift, add_hours,
                   format_duration, get_app_dir)


@pytest.mark.parametrize("inp, expected", [
    # Already normalised
    ("09:30", "09:30"),
    ("00:00", "00:00"),
    ("23:59", "23:59"),
    # Leading zero added
    ("9:30",  "09:30"),
    ("0:00",  "00:00"),
    # Dot separator
    ("9.30",  "09:30"),
    ("09.30", "09:30"),
    ("17.00", "17:00"),
    # bare hours
    ("9",     "09:00"),
    ("13",    "13:00"),
    ("0",     "00:00"),
    ("23",    "23:00"),
    ("12",    "12:00"),
    # 3-digit compact
    ("930",   "09:30"),
    ("000",   "00:00"),
    # 4-digit compact
    ("1345",  "13:45"),
    ("0900",  "09:00"),
    ("2359",  "23:59"),
    # Whitespace stripped
    ("  9:30 ", "09:30"),
    ("  1345  ", "13:45"),
])
def test_parse_valid(inp, expected):
    assert parse_time_input(inp) == expected


@pytest.mark.parametrize("inp", [
    "",          # empty
    "abc",       # letters
    "24",        # bare hour out of range
    "99",        # bare hour out of range
    "24:00",     # hour out of range
    "9:60",      # minute out of range
    "99:99",     # both out of range
    "9:30:00",   # too many parts
    "12345",     # 5-digit — unrecognisable
    "--",
])
def test_parse_invalid(inp):
    assert parse_time_input(inp) is None


def test_is_valid_time_true():
    assert is_valid_time("09:30") is True


def test_is_valid_time_false():
    assert is_valid_time("bad") is False


# ── entry_minutes ─────────────────────────────────────────────────────────────

def test_entry_minutes_same_day():
    assert entry_minutes("09:00", "17:00") == 480

def test_entry_minutes_overnight():
    assert entry_minutes("22:00", "06:00") == 480

def test_entry_minutes_overnight_short():
    assert entry_minutes("23:00", "00:30") == 90

def test_entry_minutes_zero():
    assert entry_minutes("09:00", "09:00") == 0

def test_entry_minutes_bad_input():
    assert entry_minutes("", "") == 0


# ── is_overnight ──────────────────────────────────────────────────────────────

def test_is_overnight_true():
    assert is_overnight("22:00", "06:00") is True

def test_is_overnight_false_same_day():
    assert is_overnight("09:00", "17:00") is False

def test_is_overnight_same_time():
    assert is_overnight("09:00", "09:00") is False

def test_is_overnight_bad_input():
    assert is_overnight("", "") is False


# ── resolve_start_time ──────────────────────────────────────────────────────

def test_resolve_start_time_earlier_today():
    now = datetime(2026, 9, 23, 10, 15, 42)
    assert resolve_start_time(9, 30, now) == datetime(2026, 9, 23, 9, 30)


def test_resolve_start_time_future_means_yesterday():
    # Picking 22:00 at 01:00 backdates an overnight shift
    now = datetime(2026, 9, 23, 1, 0)
    assert resolve_start_time(22, 0, now) == datetime(2026, 9, 22, 22, 0)


def test_resolve_start_time_crosses_month_boundary():
    now = datetime(2026, 10, 1, 0, 30)
    assert resolve_start_time(23, 0, now) == datetime(2026, 9, 30, 23, 0)


def test_resolve_start_time_same_minute_is_today():
    now = datetime(2026, 9, 23, 9, 30, 0)
    assert resolve_start_time(9, 30, now) == now


# ── week_key ────────────────────────────────────────────────────────────────

def test_week_key_orders_across_year_boundary():
    # 2027-01-01 (Fri) is in ISO week 53 of 2026 and must sort before 2027-01-04 (week 1)
    jan1, jan4 = date(2027, 1, 1), date(2027, 1, 4)
    assert week_key(jan1) == (2026, 53)
    assert week_key(jan4) == (2027, 1)
    assert sorted([week_key(jan4), week_key(jan1)]) == [(2026, 53), (2027, 1)]


# ── parse_date_input ────────────────────────────────────────────────────────

_TODAY = date(2026, 9, 23)


@pytest.mark.parametrize("raw, expected", [
    ("2026-06-02", "2026-06-02"),
    ("2026-6-2", "2026-06-02"),
    ("20260602", "2026-06-02"),
    ("2.6.2026", "2026-06-02"),
    ("02.06.2026", "2026-06-02"),
    ("2.6.", "2026-06-02"),
    ("2.6", "2026-06-02"),
    ("  23.9.  ", "2026-09-23"),
])
def test_parse_date_input_valid(raw, expected):
    assert parse_date_input(raw, today=_TODAY) == expected


def test_parse_date_input_short_form_uses_todays_year():
    assert parse_date_input("1.1.", today=date(2031, 5, 5)) == "2031-01-01"


@pytest.mark.parametrize("raw", [
    "", "abc", "31.2.2026", "2026-13-01", "32.1.", "1.1.0999", "2026/06/02",
])
def test_parse_date_input_invalid(raw):
    assert parse_date_input(raw, today=_TODAY) is None


# ── parse_pay_rate ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, expected", [
    ("20", 20.0), ("20,50", 20.5), ("20.50 €", 20.5), (" 15 ", 15.0),
])
def test_parse_pay_rate_valid(raw, expected):
    assert parse_pay_rate(raw) == expected


@pytest.mark.parametrize("raw", ["nan", "inf", "-5", "0", "", "abc", "10001"])
def test_parse_pay_rate_invalid(raw):
    assert parse_pay_rate(raw) is None


# ── start_time_needs_confirm ────────────────────────────────────────────────

_NOW = datetime(2026, 9, 23, 9, 20)


@pytest.mark.parametrize("hour, minute", [(9, 30), (15, 19)])
def test_start_time_slightly_ahead_needs_confirm(hour, minute):
    assert start_time_needs_confirm(hour, minute, _NOW)


@pytest.mark.parametrize("hour, minute", [
    (16, 20),   # 7 h ahead: clearly yesterday
    (15, 20),   # exactly 6 h ahead
    (9, 0),     # in the past
    (9, 20),    # now
])
def test_start_time_no_confirm(hour, minute):
    assert not start_time_needs_confirm(hour, minute, _NOW)


def test_start_time_confirm_around_midnight():
    # 23:00 picked at 00:10 is last night's start, not "about now"
    assert not start_time_needs_confirm(23, 0, datetime(2026, 9, 23, 0, 10))
    # 00:15 picked at 23:50 is 25 min ahead, not a start 23 h ago
    assert start_time_needs_confirm(0, 15, datetime(2026, 9, 23, 23, 50))
    # 18:00 picked at 23:50 is this evening's start
    assert not start_time_needs_confirm(18, 0, datetime(2026, 9, 23, 23, 50))


# ── get_app_dir ─────────────────────────────────────────────────────────────

def test_app_dir_from_source(monkeypatch):
    import utils
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert get_app_dir() == os.path.dirname(os.path.abspath(utils.__file__))


def test_app_dir_frozen_uses_bundle_dir(monkeypatch, tmp_path):
    # assets are bundled into _internal\, not next to the exe
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "_internal"), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Tyoaikaweleho.exe"))
    assert get_app_dir() == str(tmp_path / "_internal")


def test_app_dir_frozen_without_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Tyoaikaweleho.exe"))
    assert get_app_dir() == str(tmp_path)


# ── small helpers ───────────────────────────────────────────────────────────

def test_is_long_shift_threshold():
    assert not is_long_shift(14 * 60)
    assert is_long_shift(14 * 60 + 1)


@pytest.mark.parametrize("t, hours, expected", [
    ("09:30", 8, "17:30"), ("20:00", 8, "04:00"), ("23:15", 1, "00:15"),
])
def test_add_hours(t, hours, expected):
    assert add_hours(t, hours) == expected


@pytest.mark.parametrize("minutes, expected", [
    (480, "8h 00m"), (0, "0h 00m"), (605, "10h 05m"), (1500, "25h 00m"),
])
def test_format_duration(minutes, expected):
    assert format_duration(minutes) == expected


# ── time picker slot rounding ───────────────────────────────────────────────

@pytest.mark.parametrize("t, expected", [
    ("09:30", 19), ("09:14", 18), ("09:15", 19), ("09:45", 20),
    ("00:00", 0), ("23:44", 47), ("23:50", 0),
])
def test_nearest_slot(t, expected):
    from ui.time_picker_popup import nearest_slot
    assert nearest_slot(t) == expected


@pytest.mark.parametrize("t", [None, "", "abc"])
def test_nearest_slot_invalid(t):
    from ui.time_picker_popup import nearest_slot
    assert nearest_slot(t) is None
