"""Tests for stats.summarize — buckets, totals, by-shift and records."""
from datetime import date

import pytest

from stats import summarize
from storage import WorkEntry


def _e(d, t_in, t_out, js="Sales"):
    return WorkEntry(id=f"{d}{t_in}", date=d, job_shift=js, time_in=t_in, time_out=t_out)


ENTRIES = [
    _e("2026-09-21", "09:00", "17:00"),               # Mon, 480
    _e("2026-09-21", "18:00", "20:00", "Support"),    # Mon, 120
    _e("2026-09-23", "22:00", "06:00", "Support"),    # Wed, overnight 480
    _e("2026-09-24", "09:00", ""),                    # open
    _e("2026-09-28", "09:00", "10:00"),               # next week, 60
    _e("2026-10-02", "09:00", "11:00"),               # out of range
    _e("bad-date", "09:00", "11:00"),
]


def test_day_buckets_zero_filled():
    s = summarize(ENTRIES, date(2026, 9, 21), date(2026, 9, 30), "day", 20.0)
    assert len(s["buckets"]) == 10
    assert s["buckets"][0] == {"key": "2026-09-21", "label": "Mon 21", "start": "2026-09-21",
                               "minutes": 600, "earnings": 200.0, "shifts": 2}
    assert s["buckets"][1]["minutes"] == 0
    assert s["totals"] == {"minutes": 1140, "earnings": 380.0, "shifts": 4, "worked_days": 3}
    assert s["open_entries"] == 1


def test_week_buckets_start_monday():
    s = summarize(ENTRIES, date(2026, 9, 23), date(2026, 9, 30), "week", 20.0)
    assert [b["key"] for b in s["buckets"]] == ["2026-W39", "2026-W40"]
    assert s["buckets"][0]["start"] == "2026-09-21" and s["buckets"][0]["label"] == "W39"
    # the range starts on the Wednesday, so Monday's entries are left out
    assert s["buckets"][0]["minutes"] == 480 and s["buckets"][1]["minutes"] == 60


def test_month_buckets_across_year():
    s = summarize([_e("2026-12-31", "09:00", "10:00"), _e("2027-01-01", "09:00", "11:00")],
                  date(2026, 11, 15), date(2027, 1, 10), "month", 10.0)
    assert [(b["key"], b["label"]) for b in s["buckets"]] == [
        ("2026-11", "Nov 2026"), ("2026-12", "Dec 2026"), ("2027-01", "Jan 2027")]
    assert [b["minutes"] for b in s["buckets"]] == [0, 60, 120]


def test_by_shift_avg_and_longest():
    s = summarize(ENTRIES, date(2026, 9, 21), date(2026, 9, 30), "day", 20.0)
    assert [(r["job_shift"], r["minutes"], r["shifts"]) for r in s["by_shift"]] == [
        ("Support", 600, 2), ("Sales", 540, 2)]
    assert s["avg_per_worked_day"] == {"minutes": 380, "earnings": 126.67}
    # 480-minute tie: the earlier entry wins
    assert s["longest"]["entry"]["date"] == "2026-09-21" and s["longest"]["minutes"] == 480


def test_empty_range():
    s = summarize([], date(2026, 9, 1), date(2026, 9, 1), "day", 20.0)
    assert s["totals"]["minutes"] == 0 and s["longest"] is None
    assert s["avg_per_worked_day"] == {"minutes": 0, "earnings": 0.0}


def test_bad_granularity():
    with pytest.raises(ValueError):
        summarize([], date(2026, 9, 1), date(2026, 9, 2), "year", 20.0)
