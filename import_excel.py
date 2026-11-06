import re
import unicodedata
from datetime import datetime, date, time as dt_time, timedelta
from openpyxl import load_workbook

import storage
from utils import parse_date_input, parse_time_input

# The Full (EAS) export writes column A as text in this format
_EXPORT_DATE_FORMAT = "%a %d %b %Y"
_HAS_YEAR = re.compile(r"\d{4}")


def _shift_name(raw) -> str:
    """A shift cell as a name storage.clean_job_shift accepts: line breaks
    and tabs (Alt+Enter in Excel) become spaces, other control characters
    are dropped and the name is cut to storage.JOB_SHIFT_MAX."""
    s = " ".join(str(raw).split())
    s = "".join(c for c in s if unicodedata.category(c) not in storage._BAD_NAME_CATEGORIES
                and c not in storage._BIDI_CONTROLS)
    return " ".join(s.split())[:storage.JOB_SHIFT_MAX].rstrip()


def _hhmm(minutes: int) -> str | None:
    if not 0 <= minutes < 24 * 60:
        return None
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _number_time(f: float) -> str | None:
    """16.45 → '16:45' (hours.minutes, the Finnish way of typing a time).
    None when the minutes part isn't 0-59 or the hour isn't 0-23."""
    if f < 0:
        return None
    hours = int(f)
    minutes = round((f - hours) * 100)
    if minutes >= 60 or hours > 23:
        return None
    return _hhmm(hours * 60 + minutes)


def _normalise_time(val) -> str | None:
    """Convert any time representation to HH:MM string, or None when the
    value isn't a valid time of day (never clamped into a wrong one)."""
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (dt_time, datetime)):
        return f"{val.hour:02d}:{val.minute:02d}"
    if isinstance(val, timedelta):
        return _hhmm(round(val.total_seconds() / 60))
    if isinstance(val, (int, float)):
        if 0 < val < 1:
            # a time cell without a time format: a fraction of a day
            return _hhmm(round(val * 24 * 60) % (24 * 60))
        t = _number_time(float(val))
        if t is None and float(val).is_integer():
            t = parse_time_input(str(int(val)))  # 930 → '09:30'
        return t
    s = str(val).strip()
    if not s:
        return None
    if ":" not in s:
        try:
            t = _number_time(float(s.replace(",", ".")))
        except ValueError:
            t = None
        if t is not None:
            return t
    # '8:30', '930', '1345'
    return parse_time_input(s)


def _normalise_date(val) -> str | None:
    """Column A as ISO 'YYYY-MM-DD': a date cell, the Full export's own text
    ('Mon 02 Mar 2026') or a typed date with a year ('2.3.2026')."""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.isoformat()
    if not isinstance(val, str):
        return None
    s = val.strip()
    try:
        return datetime.strptime(s, _EXPORT_DATE_FORMAT).date().isoformat()
    except ValueError:
        pass
    if not _HAS_YEAR.search(s):
        return None  # '2.3' alone could be anything; don't guess a year
    return parse_date_input(s)


def _detect_format(ws) -> str:
    """Return 'simple' (date|time_in|time_out) or 'eas' (date|shift|time_in|time_out)."""
    for row in ws.iter_rows(min_row=1, values_only=True):
        if row and _normalise_date(row[0]) is not None and len(row) > 1:
            return "simple" if _normalise_time(row[1]) is not None else "eas"
    return "eas"


def import_from_file(path: str, report: dict | None = None) -> tuple[int, int]:
    """Parse a timesheet Excel file and insert entries into storage.

    Handles two formats automatically:
    - EAS format:    date | job_shift | time_in | time_out
    - Simple format: date | time_in   | time_out | (anything)

    Returns (imported_count, skipped_count).
    Skips duplicates (same date + time_in already in storage).
    New rows are written in one save, after a pre-import copy of data.json
    (a failed copy aborts the import with nothing written).

    *report*, when given, is filled with 'dated_rows' (rows with a date in
    column A) and 'unreadable' (of those, rows with something in the start
    time column that isn't a valid time), so the caller can say why a file
    gave nothing.
    """
    wb = load_workbook(path, data_only=True)

    existing = storage.load_all_entries()
    existing_keys = {(e.date, e.time_in) for e in existing}
    # rows with no shift column (Simple) or an empty one (EAS)
    default_js = storage.get_default_job_shift()

    new_entries: list[storage.WorkEntry] = []
    skipped = 0
    dated_rows = 0
    unreadable = 0

    for ws in wb.worksheets:
        fmt = _detect_format(ws)
        last_date_str: str | None = None

        for row in ws.iter_rows(min_row=1, values_only=True):
            date_val = row[0] if row else None
            parsed_date = _normalise_date(date_val)

            if parsed_date is not None:
                last_date_str = parsed_date
                date_str = last_date_str
                dated_rows += 1
            elif date_val is None and last_date_str is not None:
                date_str = last_date_str
            else:
                last_date_str = None
                continue

            if fmt == "simple":
                job_shift = default_js
                raw_in = row[1] if len(row) > 1 else None
                time_out = _normalise_time(row[2]) if len(row) > 2 else None
            else:  # eas
                raw_shift = row[1] if len(row) > 1 else None
                job_shift = _shift_name(raw_shift) if raw_shift is not None else ""
                if not job_shift or job_shift.lower() == "none":
                    job_shift = default_js
                raw_in = row[2] if len(row) > 2 else None
                time_out = _normalise_time(row[3]) if len(row) > 3 else None
            time_in = _normalise_time(raw_in)

            if not time_in:
                if parsed_date is not None and raw_in is not None and str(raw_in).strip():
                    unreadable += 1
                continue

            key = (date_str, time_in)
            if key in existing_keys:
                skipped += 1
                continue

            entry = storage.WorkEntry(
                id=storage.new_entry_id(),
                date=date_str,
                job_shift=job_shift,
                time_in=time_in,
                time_out=time_out or "",
            )
            new_entries.append(entry)
            existing_keys.add(key)

    if report is not None:
        report["dated_rows"] = dated_rows
        report["unreadable"] = unreadable
    if new_entries:
        storage.pre_import_snapshot()
        storage.add_entries(new_entries)
    return len(new_entries), skipped
