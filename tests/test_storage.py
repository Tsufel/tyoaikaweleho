"""Tests for storage — entry CRUD, settings, shift list."""
import pytest
import storage
from storage import WorkEntry


# ── helpers ───────────────────────────────────────────────────────────────────

def _entry(date="2026-05-10", shift="Sales", time_in="09:00", time_out="17:00"):
    return WorkEntry(
        id=storage.new_entry_id(),
        date=date,
        job_shift=shift,
        time_in=time_in,
        time_out=time_out,
    )


# ── entry CRUD ────────────────────────────────────────────────────────────────

def test_save_and_load_month(tmp_storage):
    e = _entry()
    storage.save_entry(e)
    entries = storage.load_month(2026, 5)
    assert len(entries) == 1
    assert entries[0].id       == e.id
    assert entries[0].date     == "2026-05-10"
    assert entries[0].job_shift == "Sales"
    assert entries[0].time_in  == "09:00"
    assert entries[0].time_out == "17:00"


def test_load_month_filters_correctly(tmp_storage):
    storage.save_entry(_entry(date="2026-05-10"))
    storage.save_entry(_entry(date="2026-06-01"))
    assert len(storage.load_month(2026, 5)) == 1
    assert len(storage.load_month(2026, 6)) == 1
    assert len(storage.load_month(2026, 7)) == 0


def test_delete_entry(tmp_storage):
    e1 = _entry(date="2026-05-10")
    e2 = _entry(date="2026-05-11")
    storage.save_entry(e1)
    storage.save_entry(e2)
    storage.delete_entry(e1.id)
    remaining = storage.load_month(2026, 5)
    assert len(remaining) == 1
    assert remaining[0].id == e2.id


def test_update_entry(tmp_storage):
    e = _entry()
    storage.save_entry(e)
    e.time_out = "18:30"
    storage.update_entry(e)
    assert storage.load_month(2026, 5)[0].time_out == "18:30"


def test_load_all_entries(tmp_storage):
    storage.save_entry(_entry(date="2026-05-01"))
    storage.save_entry(_entry(date="2026-06-01"))
    assert len(storage.load_all_entries()) == 2


# ── settings ──────────────────────────────────────────────────────────────────

def test_pay_rate_default(tmp_storage):
    assert storage.get_pay_rate() == pytest.approx(20.0)


def test_pay_rate_roundtrip(tmp_storage):
    storage.set_pay_rate(22.5)
    assert storage.get_pay_rate() == pytest.approx(22.5)


def test_default_start_time(tmp_storage):
    assert storage.get_default_start_time() == "09:30"


def test_default_start_time_roundtrip(tmp_storage):
    storage.set_default_start_time("08:00")
    assert storage.get_default_start_time() == "08:00"


def test_default_job_shift_default(tmp_storage):
    assert storage.get_default_job_shift() == "GPSR"


def test_default_job_shift_roundtrip(tmp_storage):
    storage.set_default_job_shift("Sales")
    assert storage.get_default_job_shift() == "Sales"


def test_export_format_default(tmp_storage):
    assert storage.get_export_format() == "Simple"


def test_export_format_roundtrip(tmp_storage):
    storage.set_export_format("Full")
    assert storage.get_export_format() == "Full"


def test_export_include_pay_default(tmp_storage):
    assert storage.get_export_include_pay() is False


def test_export_include_pay_roundtrip(tmp_storage):
    storage.set_export_include_pay(True)
    assert storage.get_export_include_pay() is True


# ── shifts ────────────────────────────────────────────────────────────────────

def test_add_job_shift_new(tmp_storage):
    assert storage.add_job_shift("Logistics") is True


def test_add_job_shift_duplicate(tmp_storage):
    storage.add_job_shift("Logistics")
    assert storage.add_job_shift("Logistics") is False


def test_add_job_shift_case_insensitive_dedup(tmp_storage):
    storage.add_job_shift("Logistics")
    assert storage.add_job_shift("logistics") is False
    assert storage.add_job_shift("LOGISTICS") is False


def test_get_job_shift_list_creates_defaults(tmp_storage):
    shifts = storage.get_job_shift_list()
    assert len(shifts) > 0
    # Default list should include common shifts
    assert any("Sales" in s for s in shifts)


def test_get_job_shift_list_includes_entry_shifts(tmp_storage):
    """Previously-used shifts not in shifts.txt should still appear."""
    e = _entry(shift="CustomShift")
    storage.save_entry(e)
    shifts = storage.get_job_shift_list()
    assert "CustomShift" in shifts
