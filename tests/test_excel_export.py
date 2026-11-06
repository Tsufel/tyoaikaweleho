"""Tests for excel_export — _time_fraction, Simple and Full formats."""
from datetime import timedelta

import pytest
from openpyxl import load_workbook

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
    assert ws["B1"].value == "Shift"
    assert ws["C1"].value == "Start"
    assert ws["D1"].value == "End"
    assert ws["E1"].value == "Total (h)"
    assert ws["G1"].value == "Week (h)"


def test_simple_writes_the_shift(tmp_path):
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 5, str(out), fmt="Simple")
    ws = load_workbook(str(out)).active
    assert [ws["B2"].value, ws["B3"].value] == ["Sales", "Support"]


@pytest.mark.parametrize("fmt, cell", [("Simple", "B2"), ("Full", "B13")])
def test_shift_is_text_not_a_formula(tmp_path, fmt, cell):
    # a shift named "=Boss" must stay text: as a formula Excel shows #NAME?
    # and a re-import reads the cell as empty
    out = tmp_path / "out.xlsx"
    entries = [WorkEntry(id="1", date="2026-05-10", job_shift="=Boss",
                         time_in="09:00", time_out="17:00")]
    export_month(entries, 2026, 5, str(out), fmt=fmt)
    ws = load_workbook(str(out)).active
    assert ws[cell].value == "=Boss" and ws[cell].data_type == "s"


def test_simple_frozen_header_filter_and_properties(tmp_path):
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 3, str(out), fmt="Simple")
    wb = load_workbook(str(out))
    ws = wb.active
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref == "A1:E3"
    assert wb.properties.creator == "Työaikaweleho"
    assert wb.properties.title == "Hours March 2026"


def test_simple_week_subtotals(tmp_path):
    # Fri 1 May and Sun 3 May are ISO week 18, Mon 4 May is week 19
    entries = [
        WorkEntry(id="1", date="2026-05-01", job_shift="Sales", time_in="09:00", time_out="17:00"),
        WorkEntry(id="2", date="2026-05-03", job_shift="Sales", time_in="10:00", time_out="12:30"),
        WorkEntry(id="3", date="2026-05-04", job_shift="Sales", time_in="22:00", time_out="02:00"),
        WorkEntry(id="4", date="2026-05-05", job_shift="Sales", time_in="09:00", time_out=""),
    ]
    out = tmp_path / "out.xlsx"
    export_month(entries, 2026, 5, str(out), fmt="Simple")
    ws = load_workbook(str(out), data_only=True).active
    assert [ws[f"G{r}"].value for r in range(2, 6)] == [
        None, timedelta(hours=10, minutes=30), None, timedelta(hours=4)]
    # the month total is still where it was
    assert ws["G7"].value == "Total"
    assert ws["G8"].value == timedelta(hours=14, minutes=30)


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
    assert ws["E11"].value == "(HOURS)"
    assert ws["F11"].value == "NOTES"


def test_full_writes_notes_as_text(tmp_path):
    entries = [
        WorkEntry(id="1", date="2026-05-10", job_shift="Sales",
                  time_in="09:00", time_out="17:00", note="Covered for Aino"),
        WorkEntry(id="2", date="2026-05-11", job_shift="Sales",
                  time_in="09:00", time_out="17:00", note="=SUM(1,2)"),
        WorkEntry(id="3", date="2026-05-12", job_shift="Sales",
                  time_in="09:00", time_out="17:00"),
    ]
    out = tmp_path / "out.xlsx"
    export_month(entries, 2026, 5, str(out), fmt="Full")
    ws = load_workbook(str(out)).active
    # 05-10 is its own ISO week (row 13); 05-11/05-12 follow at rows 16-17
    assert ws["F13"].value == "Covered for Aino"
    assert ws["F16"].value == "=SUM(1,2)" and ws["F16"].data_type == "s"
    assert ws["F17"].value is None
    # the rest of the row layout is unchanged
    assert ws["E13"].value is not None and ws["E16"].value is not None


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


def _cells(ws) -> dict:
    return {c.coordinate: c.value for row in ws.iter_rows() for c in row if c.value is not None}


def test_full_names_fill_b3_b5_only(tmp_path):
    blank, named = tmp_path / "blank.xlsx", tmp_path / "named.xlsx"
    export_month(_sample_entries(), 2026, 5, str(blank), fmt="Full")
    export_month(_sample_entries(), 2026, 5, str(named), fmt="Full",
                 employee_name="Aino Virtanen", manager_name="=Boss")
    before, after = _cells(load_workbook(str(blank)).active), _cells(load_workbook(str(named)).active)
    assert "B3" not in before and "B5" not in before
    before.pop("H3"), after.pop("H3")  # today's date: could tick over between the two
    assert after.pop("B3") == "Aino Virtanen"
    assert after.pop("B5") == "=Boss"  # text, not a formula
    assert after == before
    ws = load_workbook(str(named)).active
    assert ws["B5"].data_type == "s"


def test_simple_ignores_names(tmp_path):
    out = tmp_path / "out.xlsx"
    export_month(_sample_entries(), 2026, 5, str(out), employee_name="Aino", manager_name="Boss")
    values = set(_cells(load_workbook(str(out)).active).values())
    assert "Aino" not in values and "Boss" not in values


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


def _range_entries():
    return [
        WorkEntry(id="1", date="2026-02-28", job_shift="Sales", time_in="09:00", time_out="17:00"),
        WorkEntry(id="2", date="2026-03-02", job_shift="Support", time_in="09:00", time_out="16:30"),
        WorkEntry(id="3", date="2026-03-31", job_shift="Sales", time_in="22:00", time_out="02:15"),
        WorkEntry(id="4", date="2026-03-31", job_shift="Sales", time_in="08:00", time_out=""),
        WorkEntry(id="5", date="2026-04-01", job_shift="Sales", time_in="09:00", time_out="17:00"),
    ]


def test_range_label():
    from datetime import date
    from excel_export import range_label
    assert range_label(date(2026, 1, 1), date(2026, 12, 31)) == "1.1.–31.12.2026"
    assert range_label(date(2025, 12, 1), date(2026, 1, 31)) == "1.12.2025–31.1.2026"


def test_csv_range_bytes(tmp_path):
    from datetime import date
    from excel_export import export_range
    out = tmp_path / "out.csv"
    export_range(_range_entries(), date(2026, 3, 1), date(2026, 3, 31), str(out),
                 kind="csv", include_pay=True, pay_rate=20.0)
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert raw.decode("utf-8-sig").split("\r\n") == [
        "Date;Shift;Start;End;Hours;Earnings",
        "2.3.2026;Support;09:00;16:30;7,50;150,00",
        "31.3.2026;Sales;08:00;;;",
        "31.3.2026;Sales;22:00;02:15;4,25;85,00",
        "",
    ]


def test_csv_without_pay_has_no_earnings(tmp_path):
    from excel_export import export_csv
    out = tmp_path / "out.csv"
    export_csv(_range_entries()[:1], str(out))
    assert out.read_text(encoding="utf-8-sig").splitlines() == [
        "Date;Shift;Start;End;Hours", "28.2.2026;Sales;09:00;17:00;8,00"]


def test_xlsx_range_is_a_simple_sheet_of_the_range(tmp_path):
    from datetime import date
    from excel_export import export_range
    out = tmp_path / "out.xlsx"
    export_range(_range_entries(), date(2026, 2, 28), date(2026, 3, 2), str(out), kind="xlsx")
    wb = load_workbook(str(out))
    ws = wb.active
    assert wb.properties.title == "Hours 28.2.–2.3.2026"
    assert [ws[f"B{r}"].value for r in (2, 3, 4)] == ["Sales", "Support", None]


def _full_dates(ws) -> list[str]:
    return [ws[f"A{r}"].value for r in range(13, ws.max_row + 1)
            if isinstance(ws[f"A{r}"].value, str) and ws[f"A{r}"].value[:3].isalpha()]


@pytest.mark.parametrize("year, month, days", [
    # 29-31 Dec 2025 are ISO week 1 of 2026
    (2025, 12, ["2025-12-01", "2025-12-15", "2025-12-30"]),
    # 1-3 Jan 2027 are ISO week 53 of 2026
    (2027, 1, ["2027-01-01", "2027-01-04", "2027-01-20"]),
])
def test_full_weeks_in_date_order_at_year_end(tmp_path, year, month, days):
    from datetime import date
    entries = [WorkEntry(id=str(i), date=d, job_shift="Sales", time_in="09:00", time_out="17:00")
               for i, d in enumerate(reversed(days))]
    out = tmp_path / "out.xlsx"
    export_month(entries, year, month, str(out), fmt="Full")
    ws = load_workbook(str(out)).active
    assert _full_dates(ws) == [date.fromisoformat(d).strftime("%a %d %b %Y") for d in days]
