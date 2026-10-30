"""Achievements engine — derives every badge from the stored entries.

Pure: no I/O and no stored counters. Progress is recomputed from the entries
each time, the same way `stats.summarize` works; only "already celebrated" is
stored (by the API layer). See docs/V2_GAMIFICATION_PLAN.md.

Rules shared by every achievement:
- An entry counts on its start date (overnight shifts included), as in Stats.
- Open entries (no time_in/time_out), unparsable dates, zero-length shifts and
  entries dated after *today* are ignored.
- `met_on` is the date the condition first became true when replaying the
  entries in (date, time_in) order, or None.
"""
import math
from datetime import date, timedelta

from utils import entry_minutes
from webapp.results import money

TIERS = ("bronze", "silver", "gold", "legendary")

EARLY_BIRD_BEFORE = 6 * 60      # start before 06:00
NIGHT_OWL_AFTER = 22 * 60       # still working after 22:00
MARATHON_MINUTES = 12 * 60
INFERNO_RATIO = 1.25            # fireBadge: p >= 1.25 -> "inferno"
# Blue overtime: the clock-out blast burns blue once the shift is past the
# target (FxDirector onBlast / FireLayer: minutes > target * 60).

# Hidden ones show as "???" with the hidden_<tier> medal until met.
# unit: how the UI labels progress.cur / progress.goal.
CATALOGUE = [
    {"id": "first_shift", "tier": "bronze", "goal": 1, "unit": "shifts",
     "title": "First shift", "desc": "Save your first shift."},
    {"id": "hours_10", "tier": "bronze", "goal": 10, "unit": "h",
     "title": "10 hours", "desc": "Log 10 hours in total."},
    {"id": "target_10", "tier": "bronze", "goal": 10, "unit": "days",
     "title": "On target", "desc": "Hit your daily target on 10 days."},
    {"id": "first_overnight", "tier": "bronze", "goal": 1, "unit": "shifts", "hidden": True,
     "title": "Through the night", "desc": "Work a shift past midnight."},
    {"id": "hours_100", "tier": "silver", "goal": 100, "unit": "h",
     "title": "100 hours", "desc": "Log 100 hours in total."},
    {"id": "streak_5", "tier": "silver", "goal": 5, "unit": "days",
     "title": "Full week", "desc": "Hit your target on 5 workdays in a row (weekends don't count)."},
    {"id": "weeks_4", "tier": "silver", "goal": 4, "unit": "weeks",
     "title": "Regular", "desc": "Work at least one shift in 4 weeks in a row."},
    {"id": "early_bird", "tier": "silver", "goal": 1, "unit": "shifts", "hidden": True,
     "title": "Early bird", "desc": "Start a shift before 06:00."},
    {"id": "night_owl", "tier": "silver", "goal": 1, "unit": "shifts", "hidden": True,
     "title": "Night owl", "desc": "Keep working past 22:00."},
    {"id": "earned_1k", "tier": "silver", "goal": 1000, "unit": "€",
     "title": "€1 000 earned", "desc": "Earn €1 000 in total."},
    {"id": "hours_500", "tier": "gold", "goal": 500, "unit": "h",
     "title": "500 hours", "desc": "Log 500 hours in total."},
    {"id": "target_50", "tier": "gold", "goal": 50, "unit": "days",
     "title": "Bullseye", "desc": "Hit your daily target on 50 days."},
    {"id": "marathon_12h", "tier": "gold", "goal": 12, "unit": "h", "hidden": True,
     "title": "Marathon", "desc": "Work a single 12-hour shift."},
    {"id": "earned_10k", "tier": "gold", "goal": 10000, "unit": "€",
     "title": "€10 000 earned", "desc": "Earn €10 000 in total."},
    {"id": "hours_1000", "tier": "legendary", "goal": 1000, "unit": "h",
     "title": "1000 hours", "desc": "Log 1000 hours in total."},
    {"id": "lulz_inferno", "tier": "legendary", "goal": None, "unit": "h", "hidden": True,
     "title": "Inferno", "desc": "Work a single shift long enough to reach the ☄️ inferno fire (125% of your target)."},
    {"id": "lulz_blue_overtime", "tier": "legendary", "goal": None, "unit": "h", "hidden": True,
     "title": "Blue flame", "desc": "Clock out in blue overtime fire (past your daily target)."},
]
IDS = frozenset(a["id"] for a in CATALOGUE)


def norm_target(target_hours) -> float:
    """Daily target in hours, as the timer reads it (timerLogic `normTarget`)."""
    ok = (isinstance(target_hours, (int, float)) and not isinstance(target_hours, bool)
          and math.isfinite(target_hours) and target_hours > 0)
    return max(1.0, float(target_hours) if ok else 8.0)


def _clock(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _closed_shifts(entries, today: date):
    """(day, start minute, minutes) for every countable entry, in replay order."""
    out = []
    for e in entries:
        if not e.time_in or not e.time_out:
            continue
        try:
            d = date.fromisoformat(e.date)
            start = _clock(e.time_in)
            _clock(e.time_out)
        except (TypeError, ValueError, AttributeError):
            continue
        mins = entry_minutes(e.time_in, e.time_out)
        if d > today or mins <= 0:
            continue
        out.append((d, start, mins))
    out.sort(key=lambda s: (s[0], s[1]))
    return out


PET_WINDOW_DAYS = 56


def pet_stats(entries, today: date | None = None) -> dict:
    """What the pet is derived from (petLogic.ts): lifetime minutes, and minutes
    per start date for the last 8 weeks (today included, days without a shift
    left out). Open and future entries don't count, as for achievements."""
    today = today or date.today()
    first = today - timedelta(days=PET_WINDOW_DAYS - 1)
    lifetime = 0
    days: dict[str, int] = {}
    for d, _start, mins in _closed_shifts(entries, today):
        lifetime += mins
        if d >= first:
            key = d.isoformat()
            days[key] = days.get(key, 0) + mins
    return {"lifetime_minutes": lifetime, "days": days}


def _prev_workday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _floor(x: float, places: int = 1) -> float:
    f = 10 ** places
    return math.floor(x * f + 1e-9) / f


def evaluate(entries, target_hours=8.0, pay_rate=0.0, today: date | None = None) -> list[dict]:
    """Every catalogue achievement with its progress and `met_on` (ISO date or None)."""
    today = today or date.today()
    target = norm_target(target_hours)
    target_min = target * 60
    rate = pay_rate if (isinstance(pay_rate, (int, float)) and not isinstance(pay_rate, bool)
                        and math.isfinite(pay_rate) and pay_rate > 0) else 0.0
    goals = {a["id"]: a["goal"] for a in CATALOGUE}
    goals["lulz_inferno"] = _floor(target * INFERNO_RATIO, 2)
    goals["lulz_blue_overtime"] = target

    met: dict[str, date] = {}

    def hit(aid: str, d: date) -> None:
        met.setdefault(aid, d)

    shifts = _closed_shifts(entries, today)
    total_min = 0
    longest = 0
    day_min: dict[date, int] = {}
    for d, start, mins in shifts:
        total_min += mins
        longest = max(longest, mins)
        day_min[d] = day_min.get(d, 0) + mins
        hit("first_shift", d)
        for aid in ("hours_10", "hours_100", "hours_500", "hours_1000"):
            if total_min >= goals[aid] * 60:
                hit(aid, d)
        for aid in ("earned_1k", "earned_10k"):
            if rate and money(total_min / 60 * rate) >= goals[aid]:
                hit(aid, d)
        # Actually past midnight: a shift ending at 00:00 is not overnight here.
        if start + mins > 24 * 60:
            hit("first_overnight", d)
        if start < EARLY_BIRD_BEFORE:
            hit("early_bird", d)
        if start + mins > NIGHT_OWL_AFTER:
            hit("night_owl", d)
        if mins >= MARATHON_MINUTES:
            hit("marathon_12h", d)
        if mins >= target_min * INFERNO_RATIO:
            hit("lulz_inferno", d)
        if mins > target_min:
            hit("lulz_blue_overtime", d)

    # Per-day rules: replayed after each day's total is known.
    target_days = 0
    run = best_run = 0
    last_run_day = None
    weeks = best_weeks = 0
    last_week = None
    for d in sorted(day_min):
        if day_min[d] >= target_min:
            target_days += 1
            if target_days >= goals["target_10"]:
                hit("target_10", d)
            if target_days >= goals["target_50"]:
                hit("target_50", d)
            if d.weekday() < 5:
                # Only worked days are replayed, so a weekday with no shift at
                # all shows up as a gap to the previous workday and breaks it.
                run = run + 1 if last_run_day == _prev_workday(d) else 1
                last_run_day = d
                best_run = max(best_run, run)
                if run >= goals["streak_5"]:
                    hit("streak_5", d)
        elif d.weekday() < 5:
            run, last_run_day = 0, None
        monday = d - timedelta(days=d.weekday())
        if monday != last_week:
            weeks = weeks + 1 if last_week == monday - timedelta(weeks=1) else 1
            last_week = monday
            best_weeks = max(best_weeks, weeks)
            if weeks >= goals["weeks_4"]:
                hit("weeks_4", d)

    hours = total_min / 60
    earned = math.floor(money(hours * rate))  # same rounding as Stats
    longest_h = longest / 60
    cur = {
        "first_shift": len(shifts),
        "hours_10": _floor(hours), "hours_100": _floor(hours),
        "hours_500": _floor(hours), "hours_1000": _floor(hours),
        "target_10": target_days, "target_50": target_days,
        "streak_5": best_run, "weeks_4": best_weeks,
        "first_overnight": int("first_overnight" in met),
        "early_bird": int("early_bird" in met),
        "night_owl": int("night_owl" in met),
        "marathon_12h": _floor(longest_h),
        "earned_1k": earned, "earned_10k": earned,
        "lulz_inferno": _floor(longest_h), "lulz_blue_overtime": _floor(longest_h),
    }

    items = []
    for a in CATALOGUE:
        aid = a["id"]
        goal = goals[aid]
        done = aid in met
        items.append({
            "id": aid,
            "title": a["title"],
            "desc": a["desc"],
            "icon": aid,
            "tier": a["tier"],
            "hidden": a.get("hidden", False),
            "progress": {"cur": goal if done else min(cur[aid], goal), "goal": goal,
                         "unit": a["unit"]},
            "met_on": met[aid].isoformat() if done else None,
        })
    return items


def with_seen(items: list[dict], seen: dict) -> list[dict]:
    """Seen achievements stay unlocked on the date they were stored with, even
    if entries were edited or deleted (or the pay rate changed) since."""
    out = []
    for i in items:
        if i["id"] in seen:
            goal = i["progress"]["goal"]
            i = {**i, "met_on": seen[i["id"]], "progress": {**i["progress"], "cur": goal}}
        out.append(i)
    return out


def newly(items: list[dict], seen) -> list[str]:
    """Ids that are met but not yet in *seen* (the stored `achievements_seen`)."""
    return [i["id"] for i in items if i["met_on"] and i["id"] not in seen]
