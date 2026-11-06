"""Finnish public holidays, computed locally (no network, no stored data).

Pure: every function takes a year or a date and returns plain values. The
frontend has a TypeScript twin (frontend/src/lib/holidays.ts); both are
checked against tests/fixtures/fi_holidays.json so they cannot drift apart.

Juhannusaatto (Midsummer Eve) and Jouluaatto (Christmas Eve) are not
statutory holidays, but almost every workplace treats them as days off, so
they are listed too.
"""
from datetime import date, timedelta
from functools import lru_cache


def easter_sunday(year: int) -> date:
    """Western (Gregorian) Easter Sunday: the anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    month, day = divmod(h + ll - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _weekday_between(year: int, month: int, first_day: int, weekday: int) -> date:
    """The first *weekday* (Mon=0) on or after *month*/*first_day*."""
    d = date(year, month, first_day)
    return d + timedelta(days=(weekday - d.weekday()) % 7)


@lru_cache(maxsize=64)
def _year(year: int) -> tuple[tuple[date, str], ...]:
    easter = easter_sunday(year)
    midsummer = _weekday_between(year, 6, 20, 5)       # Sat 20-26 June
    all_saints = _weekday_between(year, 10, 31, 5)     # Sat 31 Oct-6 Nov
    days = [
        (date(year, 1, 1), "Uudenvuodenpäivä"),
        (date(year, 1, 6), "Loppiainen"),
        (easter - timedelta(days=2), "Pitkäperjantai"),
        (easter, "Pääsiäispäivä"),
        (easter + timedelta(days=1), "2. pääsiäispäivä"),
        (date(year, 5, 1), "Vappu"),
        (easter + timedelta(days=39), "Helatorstai"),
        (midsummer - timedelta(days=1), "Juhannusaatto"),
        (midsummer, "Juhannuspäivä"),
        (all_saints, "Pyhäinpäivä"),
        (date(year, 12, 6), "Itsenäisyyspäivä"),
        (date(year, 12, 24), "Jouluaatto"),
        (date(year, 12, 25), "Joulupäivä"),
        (date(year, 12, 26), "Tapaninpäivä"),
    ]
    # Two can share a date (Helatorstai fell on Vappu in 2008): one entry
    # naming both.
    merged: dict[date, str] = {}
    for d, name in days:
        merged[d] = f"{merged[d]} / {name}" if d in merged else name
    return tuple(sorted(merged.items()))


def holidays_in_year(year: int) -> dict[date, str]:
    """Every holiday of *year*, date -> Finnish name, in date order."""
    return dict(_year(year))


def holidays_in_month(year: int, month: int) -> dict[str, str]:
    """ISO date -> name for the holidays in one month (list_month's `holidays`)."""
    return {d.isoformat(): name for d, name in _year(year) if d.month == month}


def holiday_name(d: date) -> str | None:
    """The holiday's name when *d* is one, else None."""
    for day, name in _year(d.year):
        if day == d:
            return name
    return None


def is_holiday(d: date) -> bool:
    return holiday_name(d) is not None
