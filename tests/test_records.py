"""Tests for records.py — personal records (the Hall of fame)."""
from datetime import date, timedelta

from records import records
from storage import WorkEntry

TODAY = date(2026, 10, 30)  # a Friday


def _e(d, t_in, t_out, js="Sales"):
    return WorkEntry(id=f"{d}{t_in}{js}", date=str(d), job_shift=js, time_in=t_in, time_out=t_out)


def _r(entries, **kw):
    kw.setdefault("today", TODAY)
    return records(entries, **kw)


def test_empty_input_returns_nulls():
    r = _r([])
    assert r == {
        "total_shifts": 0, "first_shift_date": None, "days_since_first": None,
        "longest_shift": None, "best_day": None, "best_week": None,
        "most_shifts_week": None, "best_month": None, "earliest_start": None,
        "latest_finish": None, "streak": {"current": 0, "best": 0},
    }


def test_open_zero_length_bad_and_future_entries_are_skipped():
    r = _r([_e("2026-10-05", "08:00", ""), _e("2026-10-05", "09:00", "09:00"),
            _e("bad", "08:00", "16:00"), _e("2026-11-02", "08:00", "20:00")])
    assert r["total_shifts"] == 0 and r["longest_shift"] is None


def test_longest_shift_ties_go_to_the_earliest():
    r = _r([_e("2026-10-07", "08:00", "16:00", "Bar"), _e("2026-10-06", "10:00", "18:00", "Cafe"),
            _e("2026-10-08", "08:00", "12:00")])
    assert r["longest_shift"]["minutes"] == 480
    assert r["longest_shift"]["entry"]["date"] == "2026-10-06"
    assert r["longest_shift"]["entry"]["job_shift"] == "Cafe"
    assert r["total_shifts"] == 3


def test_best_day_sums_split_shifts():
    r = _r([_e("2026-10-06", "08:00", "12:00"), _e("2026-10-06", "13:00", "18:00"),
            _e("2026-10-07", "08:00", "16:00")])
    assert r["best_day"] == {"date": "2026-10-06", "minutes": 540}


def test_best_week_and_month_span_boundaries():
    # Mon 28 Sep - Sun 4 Oct 2026 crosses a month boundary: one ISO week (W40)
    entries = [_e("2026-09-30", "08:00", "16:00"), _e("2026-10-02", "08:00", "18:00"),
               _e("2026-10-20", "08:00", "12:00")]
    r = _r(entries)
    assert r["best_week"] == {"key": "2026-W40", "start": "2026-09-28", "minutes": 1080}
    assert r["best_month"] == {"key": "2026-10", "minutes": 840}
    assert r["most_shifts_week"] == {"key": "2026-W40", "start": "2026-09-28", "shifts": 2}


def test_week_53_and_year_boundary():
    # Thu 31 Dec 2026 is in 2026-W53; Fri 1 Jan 2027 too (same ISO week)
    entries = [_e("2026-12-31", "08:00", "16:00"), _e("2027-01-01", "08:00", "16:00"),
               _e("2027-01-05", "08:00", "17:00")]
    r = _r(entries, today=date(2027, 2, 1))
    assert r["best_week"] == {"key": "2026-W53", "start": "2026-12-28", "minutes": 960}
    assert r["best_month"] == {"key": "2027-01", "minutes": 1020}
    # Fri 1 Jan is Uudenvuodenpäivä: no count, no break; the missed Mon 4 Jan breaks
    assert r["streak"] == {"current": 0, "best": 1}


def test_best_week_tie_goes_to_the_earliest_week():
    r = _r([_e("2026-10-13", "08:00", "16:00"), _e("2026-10-06", "08:00", "16:00")])
    assert r["best_week"]["key"] == "2026-W41"


def test_earliest_start_and_overnight_latest_finish():
    entries = [_e("2026-10-05", "05:12", "13:00"), _e("2026-10-06", "14:00", "23:00"),
               _e("2026-10-07", "18:00", "02:40"), _e("2026-10-08", "06:00", "14:00")]
    r = _r(entries)
    assert r["earliest_start"]["time"] == "05:12"
    assert r["earliest_start"]["entry"]["date"] == "2026-10-05"
    # 02:40 the next morning is later than 23:00
    assert r["latest_finish"]["time"] == "02:40"
    assert r["latest_finish"]["next_day"] is True
    assert r["latest_finish"]["entry"]["date"] == "2026-10-07"


def test_latest_finish_same_day():
    r = _r([_e("2026-10-05", "08:00", "16:00"), _e("2026-10-06", "08:00", "17:30")])
    assert r["latest_finish"]["time"] == "17:30" and r["latest_finish"]["next_day"] is False


def test_first_shift_and_days_since():
    r = _r([_e("2026-10-20", "08:00", "10:00"), _e("2026-03-03", "08:00", "10:00")])
    assert r["first_shift_date"] == "2026-03-03"
    assert r["days_since_first"] == (TODAY - date(2026, 3, 3)).days


def _days(start, n):
    return [_e(start + timedelta(days=k), "08:00", "16:00") for k in range(n)]


def test_current_streak_not_broken_by_today_without_a_shift():
    # Mon-Thu at target, today (Fri) nothing yet
    r = _r(_days(date(2026, 10, 26), 4))
    assert r["streak"] == {"current": 4, "best": 4}
    # once today is at target it counts
    r = _r(_days(date(2026, 10, 26), 5))
    assert r["streak"] == {"current": 5, "best": 5}
    # today below target doesn't break it either
    r = _r(_days(date(2026, 10, 26), 4) + [_e("2026-10-30", "08:00", "10:00")])
    assert r["streak"]["current"] == 4


def test_current_streak_skips_weekends_and_breaks_on_a_missed_weekday():
    # Thu, Fri, (weekend), Mon 2 Nov as today
    r = _r(_days(date(2026, 10, 29), 2) + _days(date(2026, 11, 2), 1), today=date(2026, 11, 2))
    assert r["streak"]["current"] == 3
    # on a Sunday the run up to Friday stands
    r = _r(_days(date(2026, 10, 29), 2), today=date(2026, 11, 1))
    assert r["streak"]["current"] == 2
    # Wed missed: only Thu counts
    r = _r(_days(date(2026, 10, 26), 2) + _days(date(2026, 10, 29), 1), today=date(2026, 10, 29))
    assert r["streak"] == {"current": 1, "best": 2}


def test_streak_skips_public_holidays():
    # Mon 30 Mar - Thu 2 Apr 2026, Easter off (Fri 3 - Mon 6 Apr), Tue 7 Apr today
    entries = _days(date(2026, 3, 30), 4) + _days(date(2026, 4, 7), 1)
    assert _r(entries, today=date(2026, 4, 7))["streak"] == {"current": 5, "best": 5}
    # on Easter Monday itself the run up to Thursday stands
    assert _r(entries[:4], today=date(2026, 4, 6))["streak"]["current"] == 4


def test_best_streak_survives_a_break_and_uses_target():
    entries = _days(date(2026, 10, 5), 5) + _days(date(2026, 10, 13), 2)
    assert _r(entries)["streak"] == {"current": 0, "best": 5}
    assert _r(entries, target_hours=9)["streak"] == {"current": 0, "best": 0}


def test_input_order_does_not_matter():
    entries = [_e("2026-10-07", "18:00", "02:40"), _e("2026-10-05", "05:12", "13:00"),
               _e("2026-10-06", "14:00", "23:00")]
    assert _r(entries) == _r(list(reversed(entries)))
