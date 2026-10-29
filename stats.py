"""Totals for the Stats view (docs/V2_UI_API.md §10). Pure: takes entries,
returns the StatsData dict."""
from datetime import date, timedelta

from utils import entry_minutes, week_key
from webapp.results import entry_row, money

GRANULARITIES = ("day", "week", "month")


def _bucket_start(d: date, granularity: str) -> date:
    if granularity == "week":
        return d - timedelta(days=d.weekday())
    if granularity == "month":
        return d.replace(day=1)
    return d


def _next_start(d: date, granularity: str) -> date:
    if granularity == "week":
        return d + timedelta(weeks=1)
    if granularity == "month":
        return date(d.year + d.month // 12, d.month % 12 + 1, 1)
    return d + timedelta(days=1)


def _key_label(d: date, granularity: str) -> tuple[str, str]:
    if granularity == "week":
        y, w = week_key(d)
        return f"{y}-W{w:02d}", f"W{w}"
    if granularity == "month":
        return d.strftime("%Y-%m"), d.strftime("%b %Y")
    return d.isoformat(), f"{d:%a} {d.day}"


def summarize(entries, start: date, end: date, granularity: str,
              pay_rate: float) -> dict:
    """StatsData for entries dated start..end (inclusive). An entry counts
    on its start date; entries without a time_out are only counted in
    open_entries."""
    if granularity not in GRANULARITIES:
        raise ValueError(f"granularity must be one of {GRANULARITIES}")

    buckets, index = [], {}
    b = _bucket_start(start, granularity)
    while b <= end:
        key, label = _key_label(b, granularity)
        index[key] = len(buckets)
        buckets.append({"key": key, "label": label, "start": b.isoformat(),
                        "minutes": 0, "earnings": 0.0, "shifts": 0})
        b = _next_start(b, granularity)

    open_entries = 0
    by_shift: dict[str, dict] = {}
    day_minutes: dict[str, int] = {}
    longest = None
    total_minutes = shifts = 0
    for e in entries:
        try:
            d = date.fromisoformat(e.date)
        except ValueError:
            continue
        if not start <= d <= end:
            continue
        if not (e.time_in and e.time_out):
            open_entries += 1
            continue
        minutes = entry_minutes(e.time_in, e.time_out)
        total_minutes += minutes
        shifts += 1
        bucket = buckets[index[_key_label(_bucket_start(d, granularity), granularity)[0]]]
        bucket["minutes"] += minutes
        bucket["shifts"] += 1
        s = by_shift.setdefault(e.job_shift, {"job_shift": e.job_shift, "minutes": 0,
                                              "earnings": 0.0, "shifts": 0})
        s["minutes"] += minutes
        s["shifts"] += 1
        day_minutes[e.date] = day_minutes.get(e.date, 0) + minutes
        if longest is None or minutes > longest[1] or (
                minutes == longest[1] and (e.date, e.time_in) < (longest[0].date, longest[0].time_in)):
            longest = (e, minutes)

    for row in buckets + list(by_shift.values()):
        row["earnings"] = money(row["minutes"] / 60 * pay_rate)

    worked_days = sum(1 for m in day_minutes.values() if m > 0)
    avg = total_minutes / worked_days if worked_days else 0
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "granularity": granularity,
        "pay_rate": pay_rate,
        "buckets": buckets,
        "totals": {"minutes": total_minutes,
                   "earnings": money(total_minutes / 60 * pay_rate),
                   "shifts": shifts, "worked_days": worked_days},
        "by_shift": sorted(by_shift.values(), key=lambda s: (-s["minutes"], s["job_shift"])),
        "avg_per_worked_day": {"minutes": round(avg),
                               "earnings": money(avg / 60 * pay_rate)},
        "longest": ({"entry": entry_row(longest[0]), "minutes": longest[1]}
                    if longest else None),
        "open_entries": open_entries,
    }
