"""Shared pure-logic utilities.

Kept separate from app.py so the test suite can import them without
pulling in customtkinter (which needs a display).
"""
import math
import os
import re
import sys
from datetime import date, datetime, timedelta


# A shift longer than this asks for confirmation before it's saved
LONG_SHIFT_MINUTES = 14 * 60
# A timer stopped sooner than this was almost certainly a mis-click
MIN_SHIFT_SECONDS = 60
# A picked start time up to this far in the future is ambiguous: a typo for
# "now", or an overnight shift started yesterday
_CONFIRM_AHEAD = timedelta(hours=6)

_DOTTED_DATE = re.compile(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4})?)?")
_DASHED_DATE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")


def parse_date_input(s: str, today: date | None = None) -> str | None:
    """Normalise a loose date string to ISO 'YYYY-MM-DD'. Returns None if
    unrecognisable.

    Accepted: '2026-06-02', '2026-6-2', '20260602', '2.6.2026', '2.6.' and
    '2.6' (the last two take the year from *today*).
    """
    s = s.strip()
    try:
        m = _DOTTED_DATE.fullmatch(s)
        if m:
            year = int(m.group(3)) if m.group(3) else (today or date.today()).year
            d = date(year, int(m.group(2)), int(m.group(1)))
        else:
            m = _DASHED_DATE.fullmatch(s)
            if m:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            else:
                d = date.fromisoformat(s)
    except ValueError:
        return None
    if not 1900 <= d.year <= 9999:
        return None
    return d.isoformat()


def parse_pay_rate(s: str) -> float | None:
    """Parse an hourly rate like '20', '20,50' or '20.50 €'. Returns None
    unless it's a finite number above zero (and not absurdly large)."""
    s = s.strip().replace("€", "").strip().replace(",", ".")
    try:
        rate = float(s)
    except ValueError:
        return None
    if not math.isfinite(rate) or not 0 < rate <= 10_000:
        return None
    return rate


def parse_time_input(t: str) -> str | None:
    """Normalise loose time strings to 'HH:MM'. Returns None if unrecognisable.

    Accepted (24 h): '9:30', '09:30', '9.30', '09.30', '930', '1345'
    """
    t = t.strip().replace(".", ":")
    if t.isdigit():
        if len(t) <= 2:       # "9" → "9:00", "13" → "13:00"
            t = t + ":00"
        elif len(t) == 3:     # "930"  → "9:30"
            t = t[0] + ":" + t[1:]
        elif len(t) == 4:     # "1345" → "13:45"
            t = t[:2] + ":" + t[2:]
        else:
            return None
    parts = t.split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
    except ValueError:
        pass
    return None


def is_valid_time(t: str) -> bool:
    return parse_time_input(t) is not None


def entry_minutes(time_in: str, time_out: str) -> int:
    """Duration in minutes between two HH:MM strings; handles overnight (time_out < time_in)."""
    try:
        ih, im = map(int, time_in.split(":"))
        oh, om = map(int, time_out.split(":"))
        diff = (oh * 60 + om) - (ih * 60 + im)
        if diff < 0:
            diff += 24 * 60
        return diff
    except Exception:
        return 0


def is_overnight(time_in: str, time_out: str) -> bool:
    """True when time_out is on the next calendar day (time_out < time_in)."""
    try:
        ih, im = map(int, time_in.split(":"))
        oh, om = map(int, time_out.split(":"))
        return (oh * 60 + om) < (ih * 60 + im)
    except Exception:
        return False


def resolve_start_time(hour: int, minute: int, now: datetime) -> datetime:
    """Start datetime for a picked HH:MM. A time later than *now* is taken
    to mean yesterday, so an overnight shift can be started after midnight."""
    start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if start > now:
        start -= timedelta(days=1)
    return start


def start_time_needs_confirm(hour: int, minute: int, now: datetime) -> bool:
    """True when the next HH:MM is a little later than *now* (also across
    midnight: 00:15 at 23:50) — resolve_start_time would read it as the
    previous one, nearly a day back, but the user more likely meant
    "about now"."""
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    ahead = (target - now) % timedelta(days=1)
    return timedelta(0) < ahead < _CONFIRM_AHEAD


def is_long_shift(minutes: int) -> bool:
    return minutes > LONG_SHIFT_MINUTES


def add_hours(t: str, hours: int) -> str:
    """'HH:MM' plus whole hours, wrapping past midnight."""
    h, m = map(int, t.split(":"))
    return f"{(h + hours) % 24:02d}:{m:02d}"


def format_duration(minutes: int) -> str:
    """480 → '8h 00m'."""
    return f"{minutes // 60}h {minutes % 60:02d}m"


def week_key(d: date) -> tuple[int, int]:
    """(ISO year, ISO week) — sorts correctly across a year boundary."""
    iso = d.isocalendar()
    return iso[0], iso[1]


def get_app_dir() -> str:
    """Directory where app assets (splash.png, toolbar.png, icon.ico) live.
    Works both when running from source and when frozen by PyInstaller."""
    if getattr(sys, "frozen", False):
        # PyInstaller 6 puts --add-data files in _internal\ (sys._MEIPASS),
        # not next to the exe; user data stays next to the exe (storage.DATA_DIR)
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))
