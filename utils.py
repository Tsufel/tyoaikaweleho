"""Shared pure-logic utilities.

Kept free of UI imports so the test suite and the webapp controller can
import them without a display.
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
# A start time this far back (⏰ pressed late in the day) is asked about
# before the timer starts with that many hours already on it
_CONFIRM_BEHIND = timedelta(hours=6)

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


# Settings → Round shift times: how a timer shift's length is rounded, and to what
ROUND_MODES = ("nearest", "up", "down")
ROUND_STEPS = (15, 30, 60)


def round_shift(time_in: str, time_out: str, mode: str, step: int) -> tuple[str, str] | None:
    """The shift time_in–time_out rounded for Settings → Round shift times:
    its length goes to a whole *step* of minutes (*mode* up, down, or
    nearest with a half step going up) and its start to the nearest step,
    or the step before when that would pass midnight, so the shift keeps
    its date. The end is the rounded start plus the rounded length.

    None when nothing changes, and when the rounded length would be zero
    or a whole day: those shifts keep their exact times."""
    if mode not in ROUND_MODES or type(step) is not int or step not in ROUND_STEPS:
        return None
    minutes = entry_minutes(time_in, time_out)
    if minutes <= 0:
        return None
    if mode == "up":
        length = -(-minutes // step) * step
    elif mode == "down":
        length = minutes // step * step
    else:
        length = (minutes + step // 2) // step * step
    if not 0 < length < 24 * 60:
        return None
    h, m = map(int, time_in.split(":"))
    start = h * 60 + m
    snapped = (start + step // 2) // step * step
    if snapped >= 24 * 60:
        snapped = start // step * step
    end = (snapped + length) % (24 * 60)
    out = (f"{snapped // 60:02d}:{snapped % 60:02d}", f"{end // 60:02d}:{end % 60:02d}")
    return None if out == (time_in, time_out) else out


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


def start_far_behind(start: datetime, now: datetime) -> bool:
    """True when a resolved start lies so far back that the shift would
    begin with most of a working day already counted (⏰ at 22:00 for a
    09:30 default)."""
    return now - start >= _CONFIRM_BEHIND


def entry_span(date_iso: str, time_in: str, time_out: str) -> tuple[datetime, datetime] | None:
    """(start, end) of a closed entry; an overnight end is on the next day.
    None for open or unreadable entries (a hand-edited data.json can hold
    numbers or nulls in these fields)."""
    if not (date_iso and time_in and time_out):
        return None
    if not all(isinstance(v, str) for v in (date_iso, time_in, time_out)):
        return None
    try:
        start = datetime.strptime(f"{date_iso} {time_in}", "%Y-%m-%d %H:%M")
        datetime.strptime(time_out, "%H:%M")
    except ValueError:
        return None
    return start, start + timedelta(minutes=entry_minutes(time_in, time_out))


def overlapping(entry, others) -> list:
    """Entries in *others* (not *entry* itself, matched by id) whose time
    overlaps *entry*'s by at least a minute. Shifts that only touch
    (one ends at 12:00, the next starts at 12:00) don't count, and neither
    do zero-length entries on either side."""
    span = entry_span(entry.date, entry.time_in, entry.time_out)
    if span is None or span[0] == span[1]:
        return []
    found = []
    for o in others:
        # an id-less (hand-edited) row is only matched to its own copy
        if o is entry or (o.id == entry.id if entry.id else o == entry):
            continue
        s = entry_span(o.date, o.time_in, o.time_out)
        if s is not None and s[0] != s[1] and s[0] < span[1] and span[0] < s[1]:
            found.append(o)
    return found


def is_long_shift(minutes: int) -> bool:
    return minutes > LONG_SHIFT_MINUTES


def add_hours(t: str, hours: int) -> str:
    """'HH:MM' plus whole hours, wrapping past midnight."""
    h, m = map(int, t.split(":"))
    return f"{(h + hours) % 24:02d}:{m:02d}"


def format_duration(minutes: int) -> str:
    """480 → '8h 00m'."""
    return f"{minutes // 60}h {minutes % 60:02d}m"


SLOTS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]


def nearest_slot(t: str | None) -> int | None:
    """Index in SLOTS of the half-hour closest to *t* (ties round up), or
    None if *t* isn't a time. 23:50 rounds to 00:00."""
    t = parse_time_input(t) if t else None
    if t is None:
        return None
    h, m = map(int, t.split(":"))
    return (h * 60 + m + 15) // 30 % len(SLOTS)


def format_rate(rate: float) -> str:
    """20.0 → '20', 20.5 → '20.5' (how Settings shows the pay rate)."""
    text = repr(float(rate))
    return text[:-2] if text.endswith(".0") else text


def week_key(d: date) -> tuple[int, int]:
    """(ISO year, ISO week) — sorts correctly across a year boundary."""
    iso = d.isocalendar()
    return iso[0], iso[1]


def get_app_dir() -> str:
    """Directory where bundled app files (icon.ico, the webui/ frontend) live.
    Works both when running from source and when frozen by PyInstaller."""
    if getattr(sys, "frozen", False):
        # PyInstaller 6 puts --add-data files in _internal\ (sys._MEIPASS),
        # not next to the exe; user data stays next to the exe (storage.DATA_DIR)
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))
