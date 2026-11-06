"""Personal records for the Hall of fame (docs/V2_UI_API.md §10.3).

Pure, like stats.py and achievements.py: everything is derived from the
stored entries on each call, nothing is stored. The shifts counted are the
ones achievements count (achievements.countable_shifts): closed, readable,
not zero-length and not dated after *today*, each on its start date.
Ties go to the earliest.
"""
from datetime import date, timedelta

from achievements import countable_shifts, is_workday, norm_target, prev_workday
from utils import week_key
from webapp.results import entry_row

DAY = 24 * 60


def _hhmm(minute: int) -> str:
    m = minute % DAY
    return f"{m // 60:02d}:{m % 60:02d}"


def _streaks(day_min: dict[date, int], target_min: float, today: date) -> dict:
    """Workdays at target in a row (achievements' streak_5 rules): Mon-Fri only,
    weekends and public holidays neither count nor break a run, a workday
    below target or without a shift breaks it. `current` ends today, and
    today doesn't break it before it is done."""
    best = run = 0
    last = None
    for d in sorted(day_min):
        if not is_workday(d):
            continue
        if day_min[d] >= target_min:
            run = run + 1 if last == prev_workday(d) else 1
            last = d
            best = max(best, run)
        else:
            run, last = 0, None

    current = 0
    d = today
    if not is_workday(d) or day_min.get(d, 0) < target_min:
        d = prev_workday(d)  # today: counts once done, never breaks it
    first = min(day_min) if day_min else today
    while d >= first and day_min.get(d, 0) >= target_min:
        current += 1
        d = prev_workday(d)
    return {"current": current, "best": best}


def records(entries, target_hours=8.0, today: date | None = None) -> dict:
    """RecordsData: every record is None (streaks 0) when nothing counts yet."""
    today = today or date.today()
    target_min = norm_target(target_hours) * 60
    shifts = countable_shifts(entries, today)

    longest = earliest = latest = None
    day_min: dict[date, int] = {}
    week: dict[tuple[int, int], list] = {}   # key -> [minutes, shifts, monday]
    month: dict[str, int] = {}
    for d, start, mins, e in shifts:
        if longest is None or mins > longest[1]:
            longest = (e, mins)
        if earliest is None or start < earliest[1]:
            earliest = (e, start)
        # minutes past the start date's midnight, so 02:40 the next morning
        # finishes later than 23:00
        finish = start + mins
        if latest is None or finish > latest[1]:
            latest = (e, finish)
        day_min[d] = day_min.get(d, 0) + mins
        w = week.setdefault(week_key(d), [0, 0, d - timedelta(days=d.weekday())])
        w[0] += mins
        w[1] += 1
        mk = d.strftime("%Y-%m")
        month[mk] = month.get(mk, 0) + mins

    def best(items, value):
        # sorted keys first, so a tie keeps the earliest
        top = None
        for k in sorted(items):
            if value(k) > 0 and (top is None or value(k) > value(top)):
                top = k
        return top

    bd = best(day_min, lambda k: day_min[k])
    bw = best(week, lambda k: week[k][0])
    bs = best(week, lambda k: week[k][1])
    bm = best(month, lambda k: month[k])
    wk = lambda k: f"{k[0]}-W{k[1]:02d}"  # noqa: E731
    first = shifts[0][0] if shifts else None
    return {
        "total_shifts": len(shifts),
        "first_shift_date": first.isoformat() if first else None,
        "days_since_first": (today - first).days if first else None,
        "longest_shift": ({"entry": entry_row(longest[0]), "minutes": longest[1]}
                          if longest else None),
        "best_day": {"date": bd.isoformat(), "minutes": day_min[bd]} if bd else None,
        "best_week": ({"key": wk(bw), "start": week[bw][2].isoformat(), "minutes": week[bw][0]}
                      if bw else None),
        "most_shifts_week": ({"key": wk(bs), "start": week[bs][2].isoformat(),
                              "shifts": week[bs][1]} if bs else None),
        "best_month": {"key": bm, "minutes": month[bm]} if bm else None,
        "earliest_start": ({"entry": entry_row(earliest[0]), "time": _hhmm(earliest[1])}
                           if earliest else None),
        "latest_finish": ({"entry": entry_row(latest[0]), "time": _hhmm(latest[1]),
                           "next_day": latest[1] >= DAY} if latest else None),
        "streak": _streaks(day_min, target_min, today),
    }
