"""Tests for achievements.py — the pure achievements engine."""
from datetime import date, timedelta

import achievements
from achievements import CATALOGUE, evaluate, newly, norm_target
from storage import WorkEntry

TODAY = date(2026, 10, 30)  # a Friday
MON = date(2026, 10, 5)


def _e(d, t_in, t_out, js="Sales"):
    return WorkEntry(id=f"{d}{t_in}", date=str(d), job_shift=js, time_in=t_in, time_out=t_out)


def _by_id(entries, **kw):
    kw.setdefault("today", TODAY)
    return {i["id"]: i for i in evaluate(entries, **kw)}


def _days(start, n, t_in="08:00", t_out="16:00"):
    return [_e(start + timedelta(days=k), t_in, t_out) for k in range(n)]


def test_catalogue_ids_unique_and_have_medals():
    import os
    ids = [a["id"] for a in CATALOGUE]
    assert len(ids) == len(set(ids)) == 17
    medals = os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "assets", "medals")
    for name in ids + [f"hidden_{t}" for t in achievements.TIERS]:
        assert os.path.exists(os.path.join(medals, f"{name}.webp")), name
    assert {a["tier"] for a in CATALOGUE} == set(achievements.TIERS)


def test_empty_entries_nothing_met():
    items = evaluate([], today=TODAY)
    assert len(items) == len(CATALOGUE)
    assert all(i["met_on"] is None for i in items)
    assert all(i["progress"]["cur"] == 0 for i in items)
    assert newly(items, {}) == []


def test_item_shape():
    item = _by_id([_e(MON, "08:00", "16:00")])["hours_10"]
    assert item == {
        "id": "hours_10", "title": "10 hours", "desc": "Log 10 hours in total.",
        "icon": "hours_10", "tier": "bronze", "hidden": False,
        "progress": {"cur": 8.0, "goal": 10, "unit": "h"}, "met_on": None,
    }


def test_first_shift_met_on_earliest_date():
    a = _by_id([_e("2026-10-07", "08:00", "12:00"), _e("2026-10-06", "09:00", "10:00")])
    assert a["first_shift"]["met_on"] == "2026-10-06"
    assert a["first_shift"]["progress"] == {"cur": 1, "goal": 1, "unit": "shifts"}


def test_open_bad_date_future_and_zero_length_entries_ignored():
    entries = [
        _e(MON, "08:00", ""),               # running
        _e(MON, "", ""),                    # no times
        _e("not-a-date", "08:00", "16:00"),
        _e("2026-11-02", "08:00", "16:00"),  # after today
        _e(MON, "08:00", "08:00"),          # zero length
        _e(MON, "8x:00", "16:00"),          # garbage time
    ]
    a = _by_id(entries)
    assert all(i["met_on"] is None for i in a.values())


def test_entry_dated_today_counts():
    assert _by_id([_e(TODAY, "08:00", "16:00")])["first_shift"]["met_on"] == TODAY.isoformat()


def test_hours_thresholds_and_met_on_crossing_day():
    # 8 h + 2 h crosses 10 h on the second day.
    a = _by_id([_e(MON, "08:00", "16:00"), _e(MON + timedelta(1), "08:00", "10:00")])
    assert a["hours_10"]["met_on"] == "2026-10-06"
    assert a["hours_10"]["progress"]["cur"] == 10
    assert a["hours_100"]["progress"] == {"cur": 10.0, "goal": 100, "unit": "h"}


def test_hours_progress_floors_not_rounds():
    a = _by_id([_e(MON, "08:00", "17:59")])  # 9 h 59 min
    assert a["hours_10"]["met_on"] is None
    assert a["hours_10"]["progress"]["cur"] == 9.9


def test_progress_capped_at_goal_when_met():
    a = _by_id(_days(MON, 20))  # 160 h
    assert a["hours_10"]["progress"]["cur"] == 10
    assert a["hours_100"]["progress"]["cur"] == 100
    assert a["hours_500"]["progress"]["cur"] == 160.0


def test_target_days_counts_day_totals_split_across_shifts():
    # Two 4 h shifts on the same day hit an 8 h target.
    entries = []
    for k in range(10):
        d = MON + timedelta(k)
        entries += [_e(d, "08:00", "12:00"), _e(d, "13:00", "17:00")]
    a = _by_id(entries)
    assert a["target_10"]["met_on"] == (MON + timedelta(9)).isoformat()
    assert a["target_50"]["progress"]["cur"] == 10


def test_target_uses_target_hours():
    a = _by_id(_days(MON, 10, "08:00", "14:00"), target_hours=6)
    assert a["target_10"]["met_on"] is not None
    a = _by_id(_days(MON, 10, "08:00", "14:00"), target_hours=8)
    assert a["target_10"]["met_on"] is None


def test_norm_target_matches_timer():
    assert norm_target(7.5) == 7.5
    assert norm_target(0) == 8.0
    assert norm_target(-3) == 8.0
    assert norm_target(float("nan")) == 8.0
    assert norm_target(float("inf")) == 8.0
    assert norm_target(None) == 8.0
    assert norm_target(True) == 8.0
    assert norm_target(0.5) == 1.0


# --- streak_5: workdays in a row at target ----------------------------------

def test_streak_mon_to_fri():
    a = _by_id(_days(MON, 5))
    assert a["streak_5"]["met_on"] == "2026-10-09"


def test_streak_weekend_does_not_break_run():
    # Wed, Thu, Fri, (weekend off), Mon, Tue
    entries = _days(date(2026, 10, 7), 3) + _days(date(2026, 10, 12), 2)
    a = _by_id(entries)
    assert a["streak_5"]["met_on"] == "2026-10-13"


def test_streak_weekend_work_neither_counts_nor_breaks():
    # Thu, Fri, Sat, Sun at target + Mon, Tue -> 4 workdays, not 5.
    entries = _days(date(2026, 10, 8), 6)
    a = _by_id(entries)
    assert a["streak_5"]["met_on"] is None
    assert a["streak_5"]["progress"]["cur"] == 4
    # Weekend below target doesn't break it either.
    entries = (_days(date(2026, 10, 7), 3) + [_e("2026-10-10", "10:00", "11:00")]
               + _days(date(2026, 10, 12), 2))
    assert _by_id(entries)["streak_5"]["met_on"] == "2026-10-13"


def test_streak_broken_by_missed_weekday():
    # Mon, Tue, (Wed off), Thu, Fri, Mon
    entries = _days(MON, 2) + _days(date(2026, 10, 8), 2) + _days(date(2026, 10, 12), 1)
    a = _by_id(entries)
    assert a["streak_5"]["met_on"] is None
    assert a["streak_5"]["progress"]["cur"] == 3


def test_streak_broken_by_weekday_below_target():
    entries = _days(MON, 2) + [_e("2026-10-07", "08:00", "12:00")] + _days(date(2026, 10, 8), 2)
    a = _by_id(entries)
    assert a["streak_5"]["met_on"] is None
    assert a["streak_5"]["progress"]["cur"] == 2


def test_streak_uses_best_run_for_progress():
    entries = _days(MON, 4) + _days(date(2026, 10, 13), 2)  # Mon-Thu, (Fri, Mon off), Tue-Wed
    assert _by_id(entries)["streak_5"]["progress"]["cur"] == 4


# --- weeks_4 ----------------------------------------------------------------

def test_weeks_in_a_row():
    entries = [_e(MON + timedelta(weeks=k, days=k % 3), "08:00", "09:00") for k in range(4)]
    a = _by_id(entries)
    assert a["weeks_4"]["met_on"] == (MON + timedelta(weeks=3, days=0)).isoformat()


def test_weeks_gap_resets():
    start = date(2026, 9, 7)
    entries = [_e(start + timedelta(weeks=k), "08:00", "09:00") for k in (0, 1, 2, 4, 5)]
    a = _by_id(entries)
    assert a["weeks_4"]["met_on"] is None
    assert a["weeks_4"]["progress"]["cur"] == 3


def test_weeks_are_iso_weeks_starting_monday():
    # Sun 18th and Mon 19th are in different ISO weeks: 41, 42, 43, 44.
    entries = [_e(d, "08:00", "09:00") for d in
               ("2026-10-05", "2026-10-18", "2026-10-19", "2026-10-26")]
    assert _by_id(entries)["weeks_4"]["met_on"] == "2026-10-26"


def test_weeks_across_iso_year_with_week_53():
    # 2026 has an ISO week 53: weeks 51, 52, 53, then 2027 week 1.
    entries = [_e(d, "08:00", "09:00") for d in
               ("2026-12-16", "2026-12-21", "2026-12-31", "2027-01-08")]
    a = _by_id(entries, today=date(2027, 6, 1))
    assert a["weeks_4"]["met_on"] == "2027-01-08"


# --- shift types ------------------------------------------------------------

def test_overnight_counts_on_start_date_and_toward_hours():
    a = _by_id([_e("2026-10-09", "22:00", "06:00")])
    assert a["first_overnight"]["met_on"] == "2026-10-09"
    assert a["hours_10"]["progress"]["cur"] == 8.0
    assert a["night_owl"]["met_on"] == "2026-10-09"


def test_shift_ending_at_midnight_is_not_overnight():
    assert _by_id([_e(MON, "16:00", "00:00")])["first_overnight"]["met_on"] is None
    assert _by_id([_e(MON, "16:00", "00:01")])["first_overnight"]["met_on"] == MON.isoformat()


def test_early_bird_boundary():
    assert _by_id([_e(MON, "05:59", "08:00")])["early_bird"]["met_on"] == MON.isoformat()
    assert _by_id([_e(MON, "06:00", "08:00")])["early_bird"]["met_on"] is None


def test_night_owl_boundary():
    assert _by_id([_e(MON, "14:00", "22:00")])["night_owl"]["met_on"] is None
    assert _by_id([_e(MON, "14:00", "22:01")])["night_owl"]["met_on"] == MON.isoformat()
    assert _by_id([_e(MON, "23:30", "01:00")])["night_owl"]["met_on"] == MON.isoformat()


def test_marathon_boundary_and_progress():
    a = _by_id([_e(MON, "06:00", "17:59")])
    assert a["marathon_12h"]["met_on"] is None
    assert a["marathon_12h"]["progress"] == {"cur": 11.9, "goal": 12, "unit": "h"}
    assert _by_id([_e(MON, "06:00", "18:00")])["marathon_12h"]["met_on"] == MON.isoformat()
    # Overnight 20:00 -> 08:00 is 12 h too.
    assert _by_id([_e(MON, "20:00", "08:00")])["marathon_12h"]["met_on"] == MON.isoformat()


def test_marathon_is_one_shift_not_a_day_total():
    a = _by_id([_e(MON, "06:00", "12:00"), _e(MON, "12:30", "18:30")])
    assert a["marathon_12h"]["met_on"] is None
    for aid in ("marathon_12h", "lulz_inferno", "lulz_blue_overtime"):
        assert a[aid]["progress"]["cur"] == 6.0, aid


# --- earnings ---------------------------------------------------------------

def test_earnings_use_pay_rate():
    entries = _days(MON, 10)  # 80 h
    a = _by_id(entries, pay_rate=12.5)  # 1000 € exactly on day 10
    assert a["earned_1k"]["met_on"] == (MON + timedelta(9)).isoformat()
    assert a["earned_10k"]["progress"] == {"cur": 1000, "goal": 10000, "unit": "€"}


def test_earnings_round_to_cents_like_stats():
    # 4971 min at 12.07 = 999.9995 -> Stats shows 1000.00, so the badge unlocks.
    entries = _days(MON, 10, "00:00", "08:00") + [_e(MON + timedelta(10), "00:00", "02:51")]
    a = _by_id(entries, pay_rate=12.07)
    assert a["earned_1k"]["met_on"] == (MON + timedelta(10)).isoformat()
    assert a["earned_10k"]["progress"]["cur"] == 1000


def test_earnings_without_valid_pay_rate():
    entries = _days(MON, 10)
    for rate in (0, -5, float("nan"), None, True):
        a = _by_id(entries, pay_rate=rate)
        assert a["earned_1k"]["met_on"] is None
        assert a["earned_1k"]["progress"]["cur"] == 0


# --- Lulz -------------------------------------------------------------------

def test_inferno_at_125_percent_of_target():
    # 8 h target -> 10 h.
    assert _by_id([_e(MON, "08:00", "17:59")])["lulz_inferno"]["met_on"] is None
    assert _by_id([_e(MON, "08:00", "18:00")])["lulz_inferno"]["met_on"] == MON.isoformat()
    # 6 h target -> 7.5 h.
    a = _by_id([_e(MON, "08:00", "15:30")], target_hours=6)
    assert a["lulz_inferno"]["met_on"] == MON.isoformat()
    assert a["lulz_inferno"]["progress"]["goal"] == 7.5


def test_blue_overtime_once_past_target():
    # Same rule as the blue clock-out blast: minutes > target * 60.
    assert _by_id([_e(MON, "08:00", "16:00")])["lulz_blue_overtime"]["met_on"] is None
    a = _by_id([_e(MON, "08:00", "16:01")])
    assert a["lulz_blue_overtime"]["met_on"] == MON.isoformat()
    assert a["lulz_blue_overtime"]["progress"] == {"cur": 8, "goal": 8, "unit": "h"}
    # Past target but short of inferno.
    a = _by_id([_e(MON, "08:00", "09:10")], target_hours=1)
    assert a["lulz_blue_overtime"]["met_on"] == MON.isoformat()
    assert a["lulz_inferno"]["met_on"] is None


def test_met_progress_snaps_to_fractional_goal():
    a = _by_id([_e(MON, "08:00", "15:30")], target_hours=7.25)
    assert a["lulz_blue_overtime"]["progress"] == {"cur": 7.25, "goal": 7.25, "unit": "h"}


def test_fractional_target():
    assert _by_id(_days(MON, 10, "08:00", "15:30"), target_hours=7.5)["target_10"]["met_on"] \
        == (MON + timedelta(9)).isoformat()
    a = _by_id([_e(MON, "08:00", "15:29")], target_hours=7.5)
    assert a["target_10"]["progress"]["cur"] == 0
    # Inferno at 7.5 * 1.25 = 9.375 h = 562.5 min.
    assert _by_id([_e(MON, "08:00", "17:22")], target_hours=7.5)["lulz_inferno"]["met_on"] is None
    assert _by_id([_e(MON, "08:00", "17:23")], target_hours=7.5)["lulz_inferno"]["met_on"] \
        == MON.isoformat()


def test_lulz_is_per_shift_not_per_day():
    a = _by_id([_e(MON, "08:00", "13:00"), _e(MON, "14:00", "19:00")])
    assert a["lulz_inferno"]["met_on"] is None
    assert a["lulz_blue_overtime"]["met_on"] is None


def test_invalid_target_falls_back_to_8h():
    a = _by_id([_e(MON, "08:00", "18:00")], target_hours=0)
    assert a["lulz_inferno"]["met_on"] == MON.isoformat()


# --- replay order and newly -------------------------------------------------

def test_input_order_does_not_matter():
    entries = _days(MON, 12) + [_e("2026-10-02", "05:00", "18:00")]
    a = evaluate(entries, pay_rate=15, today=TODAY)
    b = evaluate(list(reversed(entries)), pay_rate=15, today=TODAY)
    assert a == b


def test_newly_excludes_seen_and_unmet():
    items = evaluate(_days(MON, 2), today=TODAY)
    assert newly(items, {}) == ["first_shift", "hours_10"]
    assert newly(items, {"first_shift": "2026-10-05"}) == ["hours_10"]


def test_hidden_flags():
    hidden = {a["id"] for a in CATALOGUE if a.get("hidden")}
    assert hidden == {"first_overnight", "early_bird", "night_owl", "marathon_12h",
                      "lulz_inferno", "lulz_blue_overtime"}
    # Every tier has at least one hidden achievement (for its hidden_<tier> medal).
    assert {a["tier"] for a in CATALOGUE if a.get("hidden")} == set(achievements.TIERS)
    assert {i["id"] for i in evaluate([], today=TODAY) if i["hidden"]} == hidden
