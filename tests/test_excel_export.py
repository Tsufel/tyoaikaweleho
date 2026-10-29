"""Tests for excel_export — _time_fraction, Simple and Full formats."""
from datetime import timedelta

import pytest
from openpyxl import load_workbook

import storage
from storage import WorkEntry
from excel_export import _time_fraction, export_month


# ── _time_fraction ────────────────────────────────────────────────────────────

def test_time_fraction_midnight():
    assert _time_fraction("00:00") == pytest.approx(0.0)


def test_time_fraction_noon():
    assert _time_fraction("12:00") == pytest.approx(0.5)


def test_time_fraction_nine_thirty():
    assert _time_fraction("09:30") == pytest.approx(9.5 / 24)


def test_time_fraction_end_of_day():
    assert _time_fraction("23:59") == pytest.approx((23 * 60 + 59) / (24 * 60))


# ── helpers ───────────────────────────────────────────────────────────────────

def _sample_entries():
    return [
        WorkEntry(id="1", date="2026-05-10", job_shift="Sales",
                  time_in="09:00", time_out="17:00"),
        WorkEntry(id="2", date="2026-05-11", job_shift="Support",
                  time_in="10:00", time_out="18:00"),
    ]


# ── Simple format ─────────────────────────────────────────────────────────────

def test_simple_headers(tmp_path):
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 5, str(out), fmt="Simple")
    ws = load_workbook(str(out)).active
    assert ws["A1"].value == "PVM"
    assert ws["C1"].value == "Start"
    assert ws["D1"].value == "End"
    assert ws["E1"].value == "Total (h)"


def test_simple_data_rows(tmp_path):
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 5, str(out), fmt="Simple")
    ws = load_workbook(str(out)).active
    # Row 2 should have a date value (openpyxl returns Python date objects)
    assert ws["A2"].value is not None


def test_simple_hours_and_total_are_values(tmp_path):
    """Hours and total must be stored as numbers, not formulas: openpyxl
    writes no cached result, so non-recalculating viewers show blanks."""
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 5, str(out), fmt="Simple")
    ws = load_workbook(str(out), data_only=True).active
    assert ws["E2"].value == timedelta(hours=8)
    assert ws["E3"].value == timedelta(hours=8)
    # 2 data rows → label at G5, total at G6
    assert ws["G5"].value == "Total"
    assert ws["G6"].value == timedelta(hours=16)


def test_simple_overnight_shift_hours(tmp_path):
    entries = [WorkEntry(id="1", date="2026-05-10", job_shift="Night",
                         time_in="22:00", time_out="06:00")]
    out = tmp_path / "out.xlsx"
    export_month(entries, 2026, 5, str(out), fmt="Simple")
    ws = load_workbook(str(out), data_only=True).active
    assert ws["E2"].value == timedelta(hours=8)


def test_simple_in_progress_excluded_from_total(tmp_path):
    entries = _sample_entries() + [
        WorkEntry(id="3", date="2026-05-12", job_shift="Sales",
                  time_in="09:00", time_out=""),
    ]
    out = tmp_path / "out.xlsx"
    export_month(entries, 2026, 5, str(out), fmt="Simple")
    ws = load_workbook(str(out), data_only=True).active
    # 3 data rows → total at G7
    assert ws["G7"].value == timedelta(hours=16)


def test_simple_earned_value(tmp_path):
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 5, str(out),
                 fmt="Simple", include_pay=True, pay_rate=22.5)
    ws = load_workbook(str(out), data_only=True).active
    # total at G6 → Rate at G8/H8, Earned at G9/H9
    assert ws["G9"].value == "Earned"
    assert ws["H9"].value == pytest.approx(16 * 22.5)


def test_simple_include_pay_adds_rows(tmp_path):
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 5, str(out),
                 fmt="Simple", include_pay=True, pay_rate=22.5)
    ws = load_workbook(str(out)).active
    # Find "Rate" and "Earned" labels somewhere in column G
    col_g = [ws.cell(row=r, column=7).value for r in range(1, ws.max_row + 1)]
    assert "Rate"   in col_g
    assert "Earned" in col_g


def test_simple_no_pay_no_rate_row(tmp_path):
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 5, str(out),
                 fmt="Simple", include_pay=False)
    ws = load_workbook(str(out)).active
    col_g = [ws.cell(row=r, column=7).value for r in range(1, ws.max_row + 1)]
    assert "Rate" not in col_g


def test_simple_empty_entries(tmp_path):
    """Empty entry list must not raise and must still produce a valid file."""
    out = tmp_path / "out.xlsx"
    export_month([], 2026, 5, str(out), fmt="Simple")
    wb = load_workbook(str(out))
    assert wb.active is not None


def test_simple_full_calc_on_load(tmp_path):
    """Formulas must be forced to recalculate on open, or Excel can show
    stale/blank cached values (e.g. the Total (h) column) until manually
    recalculated."""
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 5, str(out), fmt="Simple")
    wb = load_workbook(str(out))
    assert wb.calculation.fullCalcOnLoad is True


def test_simple_in_progress_shift_marked(tmp_path):
    entries = _sample_entries() + [
        WorkEntry(id="3", date="2026-05-12", job_shift="Sales",
                  time_in="09:00", time_out=""),
    ]
    out = tmp_path / "out.xlsx"
    export_month(entries, 2026, 5, str(out), fmt="Simple")
    ws = load_workbook(str(out)).active
    # Sorted by (date, time_in) — the in-progress shift is the 3rd/last row.
    assert ws["D4"].value == "In progress"
    assert ws["E4"].value is None


# ── Full format ───────────────────────────────────────────────────────────────

def test_full_sheet_name(tmp_path):
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 5, str(out), fmt="Full")
    wb = load_workbook(str(out))
    assert wb.active.title == "MONTHLY TIMESHEET"


def test_full_column_headers(tmp_path):
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 5, str(out), fmt="Full")
    ws = load_workbook(str(out)).active
    # Headers are in row 11
    assert ws["A11"].value == "DATE"
    assert ws["C11"].value == "TIME IN"
    assert ws["D11"].value == "TIME OUT"


def test_full_totals_are_values(tmp_path):
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 5, str(out), fmt="Full", pay_rate=20.0)
    ws = load_workbook(str(out), data_only=True).active
    # Rows 13 and 16 (week spacer); current_row ends at 19 → summary_start 20
    assert ws["E13"].value == timedelta(hours=8)
    assert ws["E16"].value == timedelta(hours=8)
    assert ws["I21"].value == timedelta(hours=16)
    assert ws["E25"].value == pytest.approx(16 * 20.0)
    assert ws["M27"].value == pytest.approx(16 * 20.0)


def test_full_empty_entries(tmp_path):
    out = tmp_path / "out.xlsx"
    export_month([], 2026, 5, str(out), fmt="Full")
    assert load_workbook(str(out)).active is not None


def test_full_full_calc_on_load(tmp_path):
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 5, str(out), fmt="Full")
    wb = load_workbook(str(out))
    assert wb.calculation.fullCalcOnLoad is True


def test_full_in_progress_shift_marked(tmp_path):
    entries = _sample_entries() + [
        WorkEntry(id="3", date="2026-05-12", job_shift="Sales",
                  time_in="09:00", time_out=""),
    ]
    out = tmp_path / "out.xlsx"
    export_month(entries, 2026, 5, str(out), fmt="Full")
    ws = load_workbook(str(out)).active
    # Data rows start at 13, grouped/spaced by ISO week; 2026-05-10 is its own
    # week (row 13), then a 2-row spacer, then 05-11/05-12 in the next week
    # (rows 16-17) — the in-progress shift (05-12) is the last of those.
    assert ws["D17"].value == "In progress"
    assert ws["E17"].value is None
