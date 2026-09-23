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


# ── atomic write & corruption recovery ───────────────────────────────────────

def test_save_leaves_no_temp_file(tmp_storage):
    storage.save_entry(_entry())
    assert not (tmp_storage / "data.json.tmp").exists()
    assert (tmp_storage / "data.json").exists()


def test_save_keeps_backup_of_previous_file(tmp_storage):
    e1 = _entry(date="2026-05-10")
    e2 = _entry(date="2026-05-11")
    storage.save_entry(e1)
    storage.save_entry(e2)
    backup = tmp_storage / "data.json.bak"
    assert backup.exists()
    # Backup holds the state before the latest write (only e1)
    import json
    data = json.loads(backup.read_text(encoding="utf-8"))
    assert len(data["entries"]) == 1
    assert data["entries"][0]["id"] == e1.id


def test_corrupt_data_file_recovers_from_backup(tmp_storage):
    e1 = _entry(date="2026-05-10")
    e2 = _entry(date="2026-05-11")
    storage.save_entry(e1)
    storage.save_entry(e2)  # creates .bak containing e1
    (tmp_storage / "data.json").write_text("{ not valid json", encoding="utf-8")
    entries = storage.load_all_entries()
    assert len(entries) == 1
    assert entries[0].id == e1.id


def test_corrupt_data_file_without_backup_raises(tmp_storage):
    import json
    (tmp_storage / "data.json").write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        storage.load_all_entries()


# ── daily snapshots ─────────────────────────────────────────────────────────

def test_daily_snapshot_created_once_per_day(tmp_storage):
    import datetime as dt
    storage.save_entry(_entry(date="2026-05-10"))   # first write: nothing to snapshot yet
    snap_dir = tmp_storage / "backups"
    assert not snap_dir.exists()
    storage.save_entry(_entry(date="2026-05-11"))
    storage.save_entry(_entry(date="2026-05-12"))
    snaps = list(snap_dir.iterdir())
    assert [p.name for p in snaps] == [f"data-{dt.date.today().isoformat()}.json"]
    # Snapshot holds the state before the day's first overwrite (one entry)
    import json
    data = json.loads(snaps[0].read_text(encoding="utf-8"))
    assert len(data["entries"]) == 1


def test_daily_snapshots_pruned(tmp_storage):
    snap_dir = tmp_storage / "backups"
    snap_dir.mkdir()
    for day in range(1, 21):
        (snap_dir / f"data-2026-01-{day:02d}.json").write_text("{}", encoding="utf-8")
    storage.save_entry(_entry(date="2026-05-10"))
    storage.save_entry(_entry(date="2026-05-11"))   # triggers today's snapshot + prune
    names = sorted(p.name for p in snap_dir.iterdir())
    assert len(names) == storage._SNAPSHOT_KEEP
    assert "data-2026-01-01.json" not in names


# ── appearance mode ───────────────────────────────────────────────────────────

def test_appearance_default_is_system(tmp_storage):
    assert storage.get_appearance_mode() == "System"


def test_appearance_round_trip_keeps_other_settings(tmp_storage):
    storage.set_pay_rate(25.0)
    storage.set_appearance_mode("Dark")
    assert storage.get_appearance_mode() == "Dark"
    assert storage.get_pay_rate() == 25.0


def test_appearance_invalid_stored_value_falls_back(tmp_storage):
    data = storage._load_raw()
    data["appearance_mode"] = "Neon"
    storage._save_raw(data)
    assert storage.get_appearance_mode() == "System"


@pytest.mark.parametrize("mode", ["dark", "Neon", "", None])
def test_appearance_set_rejects_invalid(tmp_storage, mode):
    with pytest.raises(ValueError):
        storage.set_appearance_mode(mode)
    assert storage.get_appearance_mode() == "System"


# ── window geometry ───────────────────────────────────────────────────────────

def test_window_geometry_default_none(tmp_storage):
    assert storage.get_window_geometry() is None


@pytest.mark.parametrize("geom, zoomed", [
    ("860x700+120+80", False),
    ("1024x768+-1500+100", True),   # window on a monitor left of the primary
])
def test_window_geometry_round_trip(tmp_storage, geom, zoomed):
    storage.set_window_geometry(geom, zoomed)
    assert storage.get_window_geometry() == (geom, zoomed)


@pytest.mark.parametrize("stored", [
    "860x700+0+0",                       # not a dict
    {"geometry": "garbage", "zoomed": False},
    {"geometry": 42},
    {},
])
def test_window_geometry_bad_stored_value(tmp_storage, stored):
    data = storage._load_raw()
    data["window_geometry"] = stored
    storage._save_raw(data)
    assert storage.get_window_geometry() is None


# ── pay rate sanitising ───────────────────────────────────────────────────────

@pytest.mark.parametrize("stored", [float("nan"), float("inf"), -5, 0, "20", True])
def test_get_pay_rate_sanitises(tmp_storage, stored):
    data = storage._load_raw()
    data["pay_rate"] = stored
    storage._save_raw(data)
    assert storage.get_pay_rate() == 20.0


def test_get_pay_rate_int_is_float(tmp_storage):
    data = storage._load_raw()
    data["pay_rate"] = 25
    storage._save_raw(data)
    rate = storage.get_pay_rate()
    assert rate == 25.0 and isinstance(rate, float)


# ── date normalisation ────────────────────────────────────────────────────────

def test_save_entry_normalises_date(tmp_storage):
    storage.save_entry(_entry(date="20260602"))
    assert storage._load_raw()["entries"][0]["date"] == "2026-06-02"
    assert len(storage.load_month(2026, 6)) == 1


def test_load_month_finds_raw_stored_date(tmp_storage):
    e = _entry(date="2026-06-02")
    data = storage._load_raw()
    data["entries"].append({**e.__dict__, "date": "20260602"})
    storage._save_raw(data)
    found = storage.load_month(2026, 6)
    assert [x.id for x in found] == [e.id]
    assert found[0].date == "2026-06-02"
    assert storage.load_all_entries()[0].date == "2026-06-02"


def test_save_entry_fixes_other_bad_dates(tmp_storage):
    bad = _entry(date="2026-06-02")
    data = storage._load_raw()
    data["entries"].append({**bad.__dict__, "date": "20260602"})
    storage._save_raw(data)
    storage.save_entry(_entry(date="2026-06-05"))
    dates = [e["date"] for e in storage._load_raw()["entries"]]
    assert dates == ["2026-06-02", "2026-06-05"]


# ── error log ─────────────────────────────────────────────────────────────────

def test_append_error_log_writes_header_and_text(tmp_storage):
    storage.append_error_log("Traceback: boom\n")
    text = (tmp_storage / "error.log").read_text(encoding="utf-8")
    assert text.startswith("--- ")
    assert "Traceback: boom" in text


def test_append_error_log_never_raises(tmp_storage, monkeypatch):
    monkeypatch.setattr(storage, "ERROR_LOG",
                        str(tmp_storage / "missing" / "dir" / "error.log"))
    storage.append_error_log("boom")   # must not raise


def test_append_error_log_truncates(tmp_storage, monkeypatch):
    monkeypatch.setattr(storage, "_ERROR_LOG_MAX", 200)
    log = tmp_storage / "error.log"
    for i in range(20):
        storage.append_error_log(f"entry {i:02d} " + "x" * 20)
    text = log.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 400
    assert "entry 19" in text
    assert "entry 00" not in text
