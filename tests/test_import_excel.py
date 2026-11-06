"""Tests for import_excel — both formats, dedup, edge cases."""
import pytest
from datetime import datetime, time as dt_time, timedelta
from openpyxl import Workbook

import storage
from import_excel import import_from_file, _normalise_time


# ── _normalise_time ───────────────────────────────────────────────────────────

def test_normalise_time_object():
    assert _normalise_time(dt_time(9, 30)) == "09:30"


def test_normalise_datetime_object():
    assert _normalise_time(datetime(2026, 5, 10, 17, 0)) == "17:00"


def test_normalise_float():
    # 9.30 means 09:30 in Finnish spreadsheet convention
    assert _normalise_time(9.30) == "09:30"


def test_normalise_float_string():
    assert _normalise_time("16.45") == "16:45"


def test_normalise_none():
    assert _normalise_time(None) is None


def test_normalise_invalid_string():
    assert _normalise_time("abc") is None


# ── import helpers ────────────────────────────────────────────────────────────

def _make_simple_xlsx(path, rows):
    """Create a Simple-format xlsx: date | time_in | time_out."""
    wb = Workbook(); ws = wb.active
    for date, t_in, t_out in rows:
        ws.append([date, t_in, t_out])
    wb.save(path)


def _make_eas_xlsx(path, rows):
    """Create an EAS-format xlsx: date | job_shift | time_in | time_out."""
    wb = Workbook(); ws = wb.active
    for date, shift, t_in, t_out in rows:
        ws.append([date, shift, t_in, t_out])
    wb.save(path)


# ── Simple format ─────────────────────────────────────────────────────────────

def test_import_simple_one_row(tmp_path, tmp_storage):
    p = str(tmp_path / "t.xlsx")
    _make_simple_xlsx(p, [(datetime(2026, 5, 10), dt_time(9, 0), dt_time(17, 0))])
    imported, skipped = import_from_file(p)
    assert imported == 1
    assert skipped == 0


def test_import_simple_multiple_rows(tmp_path, tmp_storage):
    p = str(tmp_path / "t.xlsx")
    _make_simple_xlsx(p, [
        (datetime(2026, 5, 10), dt_time(9, 0), dt_time(17, 0)),
        (datetime(2026, 5, 11), dt_time(8, 0), dt_time(16, 0)),
    ])
    imported, skipped = import_from_file(p)
    assert imported == 2
    assert skipped == 0


def test_import_simple_entry_saved(tmp_path, tmp_storage):
    p = str(tmp_path / "t.xlsx")
    _make_simple_xlsx(p, [(datetime(2026, 5, 10), dt_time(9, 0), dt_time(17, 0))])
    import_from_file(p)
    entries = storage.load_month(2026, 5)
    assert len(entries) == 1
    assert entries[0].time_in  == "09:00"
    assert entries[0].time_out == "17:00"


# ── EAS format ────────────────────────────────────────────────────────────────

def test_import_eas_preserves_shift(tmp_path, tmp_storage):
    p = str(tmp_path / "t.xlsx")
    _make_eas_xlsx(p, [
        (datetime(2026, 5, 10), "Sales", dt_time(9, 0), dt_time(17, 0)),
    ])
    import_from_file(p)
    entries = storage.load_month(2026, 5)
    assert entries[0].job_shift == "Sales"


def test_import_eas_multiple_shifts(tmp_path, tmp_storage):
    p = str(tmp_path / "t.xlsx")
    _make_eas_xlsx(p, [
        (datetime(2026, 5, 10), "Sales",   dt_time(9,  0), dt_time(17, 0)),
        (datetime(2026, 5, 11), "Support", dt_time(10, 0), dt_time(18, 0)),
    ])
    imported, _ = import_from_file(p)
    assert imported == 2
    entries = storage.load_month(2026, 5)
    shifts = {e.job_shift for e in entries}
    assert shifts == {"Sales", "Support"}


# ── Duplicate detection ───────────────────────────────────────────────────────

def test_duplicate_on_second_import(tmp_path, tmp_storage):
    p = str(tmp_path / "t.xlsx")
    _make_simple_xlsx(p, [(datetime(2026, 5, 10), dt_time(9, 0), dt_time(17, 0))])
    import_from_file(p)
    imported, skipped = import_from_file(p)
    assert imported == 0
    assert skipped == 1


def test_no_duplicate_different_time(tmp_path, tmp_storage):
    p1 = str(tmp_path / "a.xlsx")
    p2 = str(tmp_path / "b.xlsx")
    _make_simple_xlsx(p1, [(datetime(2026, 5, 10), dt_time(9, 0), dt_time(17, 0))])
    _make_simple_xlsx(p2, [(datetime(2026, 5, 10), dt_time(10, 0), dt_time(18, 0))])
    import_from_file(p1)
    imported, skipped = import_from_file(p2)
    assert imported == 1
    assert skipped == 0


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_missing_time_in_skipped(tmp_path, tmp_storage):
    """Rows with no time_in must be skipped without crashing."""
    wb = Workbook(); ws = wb.active
    ws.append([datetime(2026, 5, 10), None, None])   # no times
    p = str(tmp_path / "t.xlsx")
    wb.save(p)
    imported, _ = import_from_file(p)
    assert imported == 0


def test_non_date_rows_ignored(tmp_path, tmp_storage):
    """Header rows and text rows must not crash the importer."""
    wb = Workbook(); ws = wb.active
    ws.append(["Date", "Time In", "Time Out"])          # header row
    ws.append([datetime(2026, 5, 10), dt_time(9, 0), dt_time(17, 0)])
    p = str(tmp_path / "t.xlsx")
    wb.save(p)
    imported, _ = import_from_file(p)
    assert imported == 1


# ── default shift (2.1.4: no hard-coded GPSR) ────────────────────────────────

def test_import_simple_uses_default_shift(tmp_path, tmp_storage):
    storage.set_default_job_shift("Training")
    p = str(tmp_path / "t.xlsx")
    _make_simple_xlsx(p, [(datetime(2026, 5, 10), dt_time(9, 0), dt_time(17, 0))])
    import_from_file(p)
    assert storage.load_month(2026, 5)[0].job_shift == "Training"


def test_import_eas_empty_shift_uses_default(tmp_path, tmp_storage):
    p = str(tmp_path / "t.xlsx")
    _make_eas_xlsx(p, [
        (datetime(2026, 5, 10), None,   dt_time(9, 0),  dt_time(17, 0)),
        (datetime(2026, 5, 11), "None", dt_time(10, 0), dt_time(18, 0)),
    ])
    import_from_file(p)
    assert {e.job_shift for e in storage.load_month(2026, 5)} == {"Sales"}


# ── loose times and dates (text times, decimals, fractions) ─────────────────

@pytest.mark.parametrize("raw, want", [
    ("8:30", "08:30"), ("16:45", "16:45"), (" 9.30 ", "09:30"), ("9,30", "09:30"),
    ("930", "09:30"), ("1345", "13:45"), (930, "09:30"), (17, "17:00"),
    (0.6875, "16:30"), (0.5, "12:00"), (timedelta(hours=7, minutes=15), "07:15"),
])
def test_normalise_loose_times(raw, want):
    assert _normalise_time(raw) == want


@pytest.mark.parametrize("raw", [8.75, 25.5, -3, "25:00", "9:75", "", True,
                                 timedelta(hours=30)])
def test_normalise_rejects_invalid_times(raw):
    """Never clamp into a wrong time (8.75 used to become 08:59, 25.5 25:50)."""
    assert _normalise_time(raw) is None


def test_import_text_times_and_dates(tmp_path, tmp_storage):
    p = str(tmp_path / "t.xlsx")
    _make_eas_xlsx(p, [
        ("2.3.2026", "Sales", "8:30", "16:45"),
        ("2026-03-03", "Support", "9.15", "17.00"),
        ("Wed 04 Mar 2026", "Sales", 0.375, 0.6875),
    ])
    imported, _ = import_from_file(p)
    assert imported == 3
    got = sorted((e.date, e.job_shift, e.time_in, e.time_out)
                 for e in storage.load_month(2026, 3))
    assert got == [("2026-03-02", "Sales", "08:30", "16:45"),
                   ("2026-03-03", "Support", "09:15", "17:00"),
                   ("2026-03-04", "Sales", "09:00", "16:30")]


def test_import_simple_text_times(tmp_path, tmp_storage):
    p = str(tmp_path / "t.xlsx")
    _make_simple_xlsx(p, [(datetime(2026, 5, 10), "8:30", "16:00")])
    import_from_file(p)
    e = storage.load_month(2026, 5)[0]
    assert (e.job_shift, e.time_in, e.time_out) == ("Sales", "08:30", "16:00")


def test_import_never_stores_invalid_times(tmp_path, tmp_storage):
    p = str(tmp_path / "t.xlsx")
    _make_eas_xlsx(p, [(datetime(2026, 5, 10), "Sales", 25.5, -3),
                       (datetime(2026, 5, 11), "Sales", 9, 26)])
    report = {}
    imported, _ = import_from_file(p, report)
    assert imported == 1
    e = storage.load_month(2026, 5)[0]
    assert (e.date, e.time_in, e.time_out) == ("2026-05-11", "09:00", "")
    assert report == {"dated_rows": 2, "unreadable": 1}


def test_yearless_text_dates_are_not_guessed(tmp_path, tmp_storage):
    p = str(tmp_path / "t.xlsx")
    _make_eas_xlsx(p, [("2.3", "Sales", "8:30", "16:45")])
    report = {}
    assert import_from_file(p, report) == (0, 0)
    assert report == {"dated_rows": 0, "unreadable": 0}


# ── round trip: the app's own exports import back unchanged ─────────────────

_ROUND_TRIP = [
    ("2026-05-04", "Support", "09:00", "17:00"),
    ("2026-05-04", "Sales", "18:00", "20:30"),
    ("2026-05-12", "Training", "22:00", "06:00"),
    ("2026-05-31", "Support", "08:15", ""),
]


@pytest.mark.parametrize("fmt", ["Simple", "Full"])
def test_reimport_own_export(tmp_path, tmp_storage, fmt):
    from excel_export import export_month
    entries = [storage.WorkEntry(id=str(i), date=d, job_shift=js, time_in=a, time_out=b)
               for i, (d, js, a, b) in enumerate(_ROUND_TRIP)]
    p = str(tmp_path / f"{fmt}.xlsx")
    export_month(entries, 2026, 5, p, fmt=fmt, include_pay=True)
    imported, skipped = import_from_file(p)
    assert (imported, skipped) == (len(_ROUND_TRIP), 0)
    got = sorted((e.date, e.job_shift, e.time_in, e.time_out)
                 for e in storage.load_month(2026, 5))
    assert got == sorted(_ROUND_TRIP)
    # and a second import finds them all as duplicates
    assert import_from_file(p) == (0, len(_ROUND_TRIP))
