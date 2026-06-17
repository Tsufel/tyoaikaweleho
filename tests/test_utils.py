"""Tests for utils.parse_time_input, is_valid_time, entry_minutes, is_overnight."""
import pytest
from utils import parse_time_input, is_valid_time, entry_minutes, is_overnight


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
