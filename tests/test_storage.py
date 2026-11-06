"""Tests for storage — entry CRUD, settings, shift list."""
import os

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
    """Unset: the first shift in the list (GPSR is no longer a default)."""
    assert storage.get_default_job_shift() == "Sales"


def test_default_job_shift_legacy_gpsr(tmp_storage):
    """Unset but GPSR is in use: keep the old default for those users."""
    storage.save_entry(_entry(shift="GPSR"))
    assert storage.get_default_job_shift() == "GPSR"


def test_default_job_shift_explicit_empty(tmp_storage):
    storage.save_entry(_entry(shift="GPSR"))
    storage.set_default_job_shift("")
    assert storage.get_default_job_shift() == ""


def test_default_job_shift_no_shifts(tmp_storage, monkeypatch):
    monkeypatch.setattr(storage, "get_job_shift_list", lambda: [])
    assert storage.get_default_job_shift() == ""


def test_default_job_shift_list_unreadable(tmp_storage, monkeypatch):
    def boom():
        raise OSError("locked")
    monkeypatch.setattr(storage, "get_job_shift_list", boom)
    assert storage.get_default_job_shift() == "Sales"


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


def test_sheet_names_default_blank(tmp_storage):
    assert storage.get_sheet_names() == {"employee_name": "", "manager_name": ""}


def test_sheet_names_saved_trimmed(tmp_storage):
    storage.save_settings({"employee_name": "  Aino   Virtanen ", "manager_name": "Pekka"})
    assert storage.get_sheet_names() == {"employee_name": "Aino Virtanen", "manager_name": "Pekka"}
    storage.save_settings({"manager_name": ""})
    assert storage.get_sheet_names() == {"employee_name": "Aino Virtanen", "manager_name": ""}


@pytest.mark.parametrize("bad", ["x" * 61, "bell\x07", "a‮b", 5, None])
def test_sheet_names_rejected_without_writing(tmp_storage, bad):
    with pytest.raises(ValueError):
        storage.save_settings({"pay_rate": 30.0, "employee_name": bad})
    assert not (tmp_storage / "data.json").exists()


def test_sheet_names_hand_edited_junk_reads_blank(tmp_storage):
    (tmp_storage / "data.json").write_text(
        '{"employee_name": 7, "manager_name": "' + "y" * 80 + '"}', encoding="utf-8")
    assert storage.get_sheet_names() == {"employee_name": "", "manager_name": ""}
    storage.save_settings({"employee_name": "x" * 60})
    assert storage.get_sheet_names()["employee_name"] == "x" * 60


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


def test_shift_list_reads_an_ansi_file(tmp_storage):
    """Notepad's ANSI save (cp1252) must not stop the app from starting."""
    (tmp_storage / "shifts.txt").write_bytes("Myymälä\r\nTyömaa\r\n".encode("cp1252"))
    assert storage.get_job_shift_list() == ["Myymälä", "Työmaa"]
    assert storage.get_default_job_shift() == "Myymälä"


def test_shift_list_reads_a_bom_file_without_a_junk_character(tmp_storage):
    (tmp_storage / "shifts.txt").write_bytes(b"\xef\xbb\xbfSales\r\nSupport")
    assert storage.get_job_shift_list() == ["Sales", "Support"]
    assert storage.add_job_shift("Sales") is False


def test_shift_list_ignores_case_when_adding_names_from_entries(tmp_storage):
    (tmp_storage / "shifts.txt").write_text("Sales\n", encoding="utf-8")
    storage.save_entry(_entry(shift="sales"))
    storage.save_entry(_entry(shift="Night"))
    storage.save_entry(_entry(shift="NIGHT"))
    assert storage.get_job_shift_list() == ["Sales", "Night"]


def test_add_job_shift_after_a_last_line_without_newline(tmp_storage):
    (tmp_storage / "shifts.txt").write_bytes(b"Sales\r\nSupport")
    assert storage.add_job_shift("Night") is True
    assert (tmp_storage / "shifts.txt").read_bytes() == b"Sales\r\nSupport\r\nNight\r\n"
    assert storage.get_job_shift_list() == ["Sales", "Support", "Night"]
    assert not (tmp_storage / "shifts.txt.tmp").exists()


def test_add_job_shift_to_an_ansi_file_keeps_every_name(tmp_storage):
    (tmp_storage / "shifts.txt").write_bytes("Myymälä\r\n\r\n  Varasto  \r\n".encode("cp1252"))
    assert storage.add_job_shift("Yövuoro") is True
    # rewritten as UTF-8 with the lines as they were (blank line, spaces kept)
    text = (tmp_storage / "shifts.txt").read_bytes().decode("utf-8")
    assert text == "Myymälä\r\n\r\n  Varasto  \r\nYövuoro\r\n"
    assert storage.get_job_shift_list() == ["Myymälä", "Varasto", "Yövuoro"]


def test_add_job_shift_failure_keeps_the_file(tmp_storage, monkeypatch):
    (tmp_storage / "shifts.txt").write_bytes(b"Sales\n")

    def locked(src, dst):
        raise PermissionError(13, "locked")

    monkeypatch.setattr(storage.os, "replace", locked)
    monkeypatch.setattr(storage, "_REPLACE_WAIT", 0)
    with pytest.raises(PermissionError):
        storage.add_job_shift("Night")
    assert (tmp_storage / "shifts.txt").read_bytes() == b"Sales\n"
    assert not (tmp_storage / "shifts.txt.tmp").exists()


# ── atomic write & corruption recovery ───────────────────────────────────────

def test_identical_save_does_not_touch_the_files(tmp_storage):
    storage.save_entry(_entry(date="2026-05-10"))
    storage.save_entry(_entry(date="2026-05-11"))
    bak = (tmp_storage / "data.json.bak").read_bytes()
    data = storage._load_raw()
    storage._save_raw(data)
    # .bak still holds the state from one real save ago
    assert (tmp_storage / "data.json.bak").read_bytes() == bak
    assert len(storage._load_raw()["entries"]) == 2


def test_identical_setting_does_not_rewrite(tmp_storage, monkeypatch):
    storage.set_pay_rate(22.0)
    calls = []
    monkeypatch.setattr(storage.os, "replace", lambda *a: calls.append(a))
    storage.set_pay_rate(22.0)
    assert calls == []


def test_save_format_matches_the_old_text_mode_write(tmp_storage):
    import json
    import os
    data = {"entries": [], "pay_rate": 20.0, "x": "ä\nb"}
    storage._save_raw(data)
    expected = json.dumps(data, indent=2, ensure_ascii=False).replace("\n", os.linesep)
    assert (tmp_storage / "data.json").read_bytes() == expected.encode("utf-8")


def test_unencodable_text_leaves_data_and_no_temp_file(tmp_storage):
    storage.save_entry(_entry(date="2026-05-10"))
    before = (tmp_storage / "data.json").read_bytes()
    with pytest.raises(UnicodeEncodeError):
        storage.save_entry(_entry(shift="Sales \ud83d"))   # half an emoji
    assert (tmp_storage / "data.json").read_bytes() == before
    assert not (tmp_storage / "data.json.tmp").exists()


def test_save_retries_while_data_json_is_briefly_locked(tmp_storage, monkeypatch):
    storage.save_entry(_entry(date="2026-05-10"))
    real = storage.os.replace
    fails = [PermissionError(32, "in use"), PermissionError(5, "denied")]

    def flaky(src, dst):
        if fails:
            raise fails.pop(0)
        real(src, dst)

    monkeypatch.setattr(storage.os, "replace", flaky)
    monkeypatch.setattr(storage, "_REPLACE_WAIT", 0)
    storage.save_entry(_entry(date="2026-05-11"))
    assert len(storage.load_all_entries()) == 2
    assert not (tmp_storage / "data.json.tmp").exists()


def test_save_gives_up_on_a_lasting_lock_and_keeps_data(tmp_storage, monkeypatch):
    storage.save_entry(_entry(date="2026-05-10"))
    before = (tmp_storage / "data.json").read_bytes()

    def locked(src, dst):
        raise PermissionError(32, "in use")

    monkeypatch.setattr(storage.os, "replace", locked)
    monkeypatch.setattr(storage, "_REPLACE_WAIT", 0)
    with pytest.raises(PermissionError):
        storage.save_entry(_entry(date="2026-05-11"))
    assert (tmp_storage / "data.json").read_bytes() == before
    assert not (tmp_storage / "data.json.tmp").exists()


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
    (tmp_storage / "data.json").write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(storage.DataFileCorrupt) as err:
        storage.load_all_entries()
    # the message names the kept copy so the user can find it
    damaged = list(tmp_storage.glob("data.damaged-*.json"))
    assert len(damaged) == 1
    assert str(damaged[0]) in str(err.value)
    assert damaged[0].read_text(encoding="utf-8") == "{ not valid json"


def test_corrupt_data_file_keeps_damaged_copy_and_rewrites(tmp_storage):
    e1 = _entry(date="2026-05-10")
    storage.save_entry(e1)
    storage.save_entry(_entry(date="2026-05-11"))   # .bak holds e1
    (tmp_storage / "data.json").write_bytes(b"\x00\x00garbage")
    assert [e.id for e in storage.load_all_entries()] == [e1.id]
    # damaged bytes kept once, data.json rewritten from the backup
    [damaged] = tmp_storage.glob("data.damaged-*.json")
    assert damaged.read_bytes() == b"\x00\x00garbage"
    import json
    assert json.loads((tmp_storage / "data.json").read_text(encoding="utf-8"))["entries"][0]["id"] == e1.id
    assert storage.last_recovery == {"source": str(tmp_storage / "data.json.bak"),
                                     "damaged_copy": str(damaged), "reason": "damaged"}
    assert "restored from" in (tmp_storage / "error.log").read_text(encoding="utf-8")


def test_corrupt_data_file_does_not_overwrite_good_backup(tmp_storage):
    """The rewrite after recovery must not copy the damaged file over .bak."""
    e1 = _entry(date="2026-05-10")
    storage.save_entry(e1)
    storage.save_entry(_entry(date="2026-05-11"))
    (tmp_storage / "data.json").write_text("{ broken", encoding="utf-8")
    storage.load_all_entries()
    import json
    bak = json.loads((tmp_storage / "data.json.bak").read_text(encoding="utf-8"))
    assert bak["entries"][0]["id"] == e1.id


def test_save_skips_backup_of_damaged_file(tmp_storage):
    storage.save_entry(_entry(date="2026-05-10"))
    storage.save_entry(_entry(date="2026-05-11"))
    good_bak = (tmp_storage / "data.json.bak").read_bytes()
    (tmp_storage / "data.json").write_text("[1, 2]", encoding="utf-8")   # not an object
    storage._save_raw({"entries": [], "pay_rate": 20.0})
    assert (tmp_storage / "data.json.bak").read_bytes() == good_bak


def test_corrupt_data_and_bak_falls_back_to_snapshot(tmp_storage):
    import json
    snap_dir = tmp_storage / "backups"
    snap_dir.mkdir()
    older = {"entries": [], "pay_rate": 11.0}
    newer = {"entries": [], "pay_rate": 12.0}
    (snap_dir / "data-2026-05-01.json").write_text(json.dumps(older), encoding="utf-8")
    (snap_dir / "data-2026-05-02.json").write_text(json.dumps(newer), encoding="utf-8")
    (snap_dir / "data-2026-05-03.json").write_text("{ also broken", encoding="utf-8")
    (tmp_storage / "data.json").write_text("{ broken", encoding="utf-8")
    (tmp_storage / "data.json.bak").write_text("{ broken too", encoding="utf-8")
    assert storage.get_pay_rate() == 12.0
    assert storage.last_recovery["source"] == str(snap_dir / "data-2026-05-02.json")


def test_missing_data_file_restored_from_backup(tmp_storage):
    import json
    e1 = _entry(date="2026-05-10")
    storage.save_entry(e1)
    storage.save_entry(_entry(date="2026-05-11"))   # .bak holds e1
    (tmp_storage / "data.json").unlink()
    assert [e.id for e in storage.load_all_entries()] == [e1.id]
    assert storage.last_recovery == {"source": str(tmp_storage / "data.json.bak"),
                                     "damaged_copy": "", "reason": "missing"}
    # written back, so the next save backs up the restored data, not nothing
    assert json.loads((tmp_storage / "data.json").read_text(encoding="utf-8"))["entries"][0]["id"] == e1.id
    assert "was missing; restored from" in (tmp_storage / "error.log").read_text(encoding="utf-8")
    assert not list(tmp_storage.glob("data.damaged-*.json"))


def test_missing_data_file_falls_back_to_snapshot(tmp_storage):
    import json
    snap_dir = tmp_storage / "backups"
    snap_dir.mkdir()
    (snap_dir / "data-2026-05-02.json").write_text(
        json.dumps({"entries": [], "pay_rate": 13.0}), encoding="utf-8")
    assert storage.get_pay_rate() == 13.0
    assert storage.last_recovery["reason"] == "missing"


def test_first_run_without_backups_starts_empty(tmp_storage):
    assert storage.load_all_entries() == []
    assert storage.last_recovery is None
    assert not (tmp_storage / "data.json").exists()


def test_locked_data_file_is_not_treated_as_damaged(tmp_storage, monkeypatch):
    storage.save_entry(_entry())
    import builtins
    real_open = builtins.open

    def locked(path, *a, **k):
        if str(path) == storage.DATA_FILE:
            raise PermissionError(13, "locked")
        return real_open(path, *a, **k)

    with monkeypatch.context() as m:
        m.setattr(builtins, "open", locked)
        with pytest.raises(PermissionError):
            storage.load_all_entries()
    assert not list(tmp_storage.glob("data.damaged-*.json"))
    assert storage.last_recovery is None


def test_data_file_with_bom_reads(tmp_storage):
    (tmp_storage / "data.json").write_bytes(b'\xef\xbb\xbf{"entries": [], "pay_rate": 15.5}')
    assert storage.get_pay_rate() == 15.5
    assert storage.last_recovery is None


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
    # the newest 14 days, plus Jan 4 as the newest of ISO week 2026-W01
    assert len(names) == storage._SNAPSHOT_KEEP + 1
    assert "data-2026-01-04.json" in names
    assert "data-2026-01-01.json" not in names
    assert "data-2026-01-07.json" not in names


def test_snapshot_retention_keeps_daily_weekly_and_monthly(tmp_storage):
    import datetime as dt
    snap_dir = tmp_storage / "backups"
    snap_dir.mkdir()
    today = dt.date.today()
    days = [today - dt.timedelta(days=n) for n in range(1, 401)]
    for d in days:
        (snap_dir / f"data-{d.isoformat()}.json").write_text("{}", encoding="utf-8")
    storage.save_entry(_entry(date="2026-05-10"))
    storage.save_entry(_entry(date="2026-05-11"))   # today's snapshot + prune
    kept = {dt.date.fromisoformat(p.name[5:15]) for p in snap_dir.iterdir()}
    everything = set(days) | {today}
    newest = sorted(everything, reverse=True)
    # nothing from the newest 14 days went
    assert set(newest[:storage._SNAPSHOT_KEEP]) <= kept
    weeks = {d.isocalendar()[:2] for d in kept}
    months = {(d.year, d.month) for d in kept}
    assert len(weeks) >= storage._SNAPSHOT_WEEKS
    assert len(months) == storage._SNAPSHOT_MONTHS
    # each kept month / week is represented by its newest day
    for d in kept:
        same_month = [x for x in everything if (x.year, x.month) == (d.year, d.month)]
        same_week = [x for x in everything if x.isocalendar()[:2] == d.isocalendar()[:2]]
        assert d in newest[:storage._SNAPSHOT_KEEP] or d == max(same_month) or d == max(same_week)
    assert len(kept) <= storage._SNAPSHOT_KEEP + storage._SNAPSHOT_WEEKS + storage._SNAPSHOT_MONTHS
    # a year-old Monday that isn't a month's newest day is gone
    assert len(kept) < 50


def test_pruning_and_recovery_ignore_files_the_app_did_not_make(tmp_storage):
    snap_dir = tmp_storage / "backups"
    snap_dir.mkdir()
    for day in range(1, 21):
        (snap_dir / f"data-2026-01-{day:02d}.json").write_text("{}", encoding="utf-8")
    own = ["data-2026-01-01 - Copy.json", "data-before-restore-x.json", "data-2026-13-45.json",
           "manual-20260101-120000.json", "pre-restore-20260101-120000.json", "notes.txt"]
    for name in own:
        (snap_dir / name).write_text('{"entries": []}', encoding="utf-8")
    storage.save_entry(_entry(date="2026-05-10"))
    storage.save_entry(_entry(date="2026-05-11"))
    names = {p.name for p in snap_dir.iterdir()}
    assert set(own) <= names
    candidates = [os.path.basename(c) for c in storage._backup_candidates()]
    assert "data-2026-01-01 - Copy.json" not in candidates
    assert "data-before-restore-x.json" not in candidates


# ── backups list / back up now / restore ─────────────────────────────────────

def test_list_backups_empty_and_read_only(tmp_storage):
    assert storage.list_backups() == []
    assert not (tmp_storage / "backups").exists()
    assert not (tmp_storage / "data.json").exists()


def test_list_backups_kinds_and_summary(tmp_storage):
    storage.save_entry(_entry(date="2026-05-10"))
    storage.save_entry(_entry(date="2026-05-12"))   # .bak + today's snapshot
    snap_dir = tmp_storage / "backups"
    (snap_dir / "data-2020-01-01.json").write_text("{not json", encoding="utf-8")
    (snap_dir / "data-2026-01-01 - Copy.json").write_text('{"entries": []}', encoding="utf-8")
    upd = snap_dir / "pre-update-v2.1.3-to-v2.1.4"
    upd.mkdir()
    (upd / "data.json").write_text('{"entries": []}', encoding="utf-8")
    manual = storage.manual_backup()
    assert os.path.basename(manual).startswith("manual-")
    before = {p.name: p.read_bytes() for p in snap_dir.iterdir() if p.is_file()}
    listed = {b["name"]: b for b in storage.list_backups()}
    assert {b["kind"] for b in listed.values()} == {"bak", "daily", "manual", "pre-update"}
    assert "data-2026-01-01 - Copy.json" not in listed
    assert listed["data.json.bak"]["entries"] == 1
    assert listed["data.json.bak"]["last_entry_date"] == "2026-05-10"
    assert listed[os.path.basename(manual)]["entries"] == 2
    assert listed["data-2020-01-01.json"]["ok"] is False
    assert listed["data-2020-01-01.json"]["entries"] is None
    assert listed["pre-update-v2.1.3-to-v2.1.4/data.json"]["ok"] is True
    assert {p.name: p.read_bytes() for p in snap_dir.iterdir() if p.is_file()} == before


def test_manual_backup_without_data_is_empty(tmp_storage):
    assert storage.manual_backup() == ""
    assert not (tmp_storage / "backups").exists()


def test_manual_backups_in_the_same_second_do_not_overwrite(tmp_storage):
    storage.save_entry(_entry())
    a = storage.manual_backup()
    b = storage.manual_backup()
    assert a != b and os.path.exists(a) and os.path.exists(b)


def test_restore_backup_round_trip_with_safety_copy(tmp_storage):
    import json
    keep = _entry(date="2026-05-10")
    storage.save_entry(keep)
    copy = os.path.basename(storage.manual_backup())
    storage.save_entry(_entry(date="2026-05-11"))
    storage.set_pay_rate(31.0)
    current = (tmp_storage / "data.json").read_bytes()
    safety = storage.restore_backup(copy)
    assert os.path.basename(safety).startswith("pre-restore-")
    with open(safety, "rb") as f:
        assert f.read() == current
    assert [e.id for e in storage.load_all_entries()] == [keep.id]
    assert storage.get_pay_rate() == 20.0
    # the safety copy is itself listed, so the restore can be undone
    assert any(b["name"] == os.path.basename(safety) and b["kind"] == "pre-restore"
               for b in storage.list_backups())
    json.loads((tmp_storage / "data.json").read_text(encoding="utf-8"))


def test_restore_backup_rejects_unknown_and_damaged(tmp_storage):
    storage.save_entry(_entry())
    snap_dir = tmp_storage / "backups"
    snap_dir.mkdir(exist_ok=True)
    (snap_dir / "data-2020-01-01.json").write_text('{"entries": {"x": 1}}', encoding="utf-8")
    (snap_dir / "mine.json").write_text('{"entries": []}', encoding="utf-8")
    before = (tmp_storage / "data.json").read_bytes()
    for name in ("data-2020-01-01.json", "mine.json", "../data.json", "nope.json"):
        with pytest.raises(LookupError):
            storage.restore_backup(name)
    assert (tmp_storage / "data.json").read_bytes() == before
    assert not list(snap_dir.glob("pre-restore-*"))


def test_restore_backup_keeps_data_when_the_safety_copy_fails(tmp_storage, monkeypatch):
    storage.save_entry(_entry())
    copy = os.path.basename(storage.manual_backup())
    storage.save_entry(_entry(date="2026-05-11"))
    before = (tmp_storage / "data.json").read_bytes()

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(storage, "_stamped_copy", boom)
    with pytest.raises(OSError):
        storage.restore_backup(copy)
    assert (tmp_storage / "data.json").read_bytes() == before


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
    data["entries"].append({**e.to_dict(), "date": "20260602"})
    storage._save_raw(data)
    found = storage.load_month(2026, 6)
    assert [x.id for x in found] == [e.id]
    assert found[0].date == "2026-06-02"
    assert storage.load_all_entries()[0].date == "2026-06-02"


def test_save_entry_fixes_other_bad_dates(tmp_storage):
    bad = _entry(date="2026-06-02")
    data = storage._load_raw()
    data["entries"].append({**bad.to_dict(), "date": "20260602"})
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


# ── achievements_seen ────────────────────────────────────────────────────────

def test_achievements_seen_absent_is_none(tmp_storage):
    assert storage.get_achievements_seen() is None


def test_achievements_seen_merge_keeps_earliest(tmp_storage):
    storage.add_achievements_seen({"first_shift": "2026-09-21"})
    merged = storage.add_achievements_seen({"first_shift": "2026-10-01",
                                            "hours_10": "2026-09-25"})
    assert merged == {"first_shift": "2026-09-21", "hours_10": "2026-09-25"}
    storage.add_achievements_seen({"first_shift": "2026-09-01"})
    assert storage.get_achievements_seen()["first_shift"] == "2026-09-01"


def test_achievements_seen_empty_is_stored(tmp_storage):
    assert storage.add_achievements_seen({}) == {}
    assert storage.get_achievements_seen() == {}


def test_achievements_seen_cleaned_on_read(tmp_storage):
    data = storage._load_raw()
    data["achievements_seen"] = {"ok": "2026-09-21", "bad": "21.9.2026", "num": 3, "x": None}
    storage._save_raw(data)
    assert storage.get_achievements_seen() == {"ok": "2026-09-21"}
    data["achievements_seen"] = ["not", "a", "dict"]
    storage._save_raw(data)
    assert storage.get_achievements_seen() == {}


def test_achievements_seen_keeps_entries(tmp_storage):
    e = storage.WorkEntry(id=storage.new_entry_id(), date="2026-09-21", job_shift="Sales",
                          time_in="09:00", time_out="17:00")
    storage.save_entry(e)
    storage.add_achievements_seen({"first_shift": "2026-09-21"})
    assert [x.id for x in storage.load_all_entries()] == [e.id]
    storage.save_entry(WorkEntry(id=storage.new_entry_id(), date="2026-09-22",
                                 job_shift="Sales", time_in="09:00", time_out="17:00"))
    storage.set_ui_prefs({"lulz": True})
    storage.set_pay_rate(15.0)
    assert storage.get_achievements_seen() == {"first_shift": "2026-09-21"}


def test_ui_prefs_pet_defaults_and_bad_stored_values(tmp_storage):
    prefs = storage.get_ui_prefs()
    assert prefs["pet"] == "off" and prefs["pet_name"] == ""
    data = storage._load_raw()
    data["ui_prefs"] = {"pet": "dragon", "pet_name": "x" * 40, "lulz": True}
    storage._save_raw(data)
    prefs = storage.get_ui_prefs()
    assert prefs["pet"] == "off" and prefs["pet_name"] == "" and prefs["lulz"] is True
    data["ui_prefs"] = {"pet": "familiar", "pet_name": " Tähti "}
    storage._save_raw(data)
    prefs = storage.get_ui_prefs()
    assert prefs["pet"] == "familiar" and prefs["pet_name"] == "Tähti"


def test_set_ui_prefs_pet_keeps_other_prefs(tmp_storage):
    storage.set_ui_prefs({"lulz": True, "target_hours": 7.5})
    storage.set_ui_prefs({"pet": "wizard", "pet_name": "Weleho"})
    prefs = storage.get_ui_prefs()
    assert prefs["lulz"] is True and prefs["target_hours"] == 7.5
    assert prefs["pet"] == "wizard" and prefs["pet_name"] == "Weleho"
    with pytest.raises(ValueError):
        storage.set_ui_prefs({"pet": "cat"})
    with pytest.raises(ValueError):
        storage.set_ui_prefs({"pet_name": "x" * 25})
    assert storage.get_ui_prefs()["pet"] == "wizard"


def test_ui_prefs_pet_skin(tmp_storage):
    assert storage.get_ui_prefs()["pet_skin"] == "classic"
    assert storage.set_ui_prefs({"pet_skin": "gilded"})["pet_skin"] == "gilded"
    assert storage.get_ui_prefs()["pet_skin"] == "gilded"
    for bad in ("plaid", "", None, 3, "Gilded"):
        with pytest.raises(ValueError):
            storage.set_ui_prefs({"pet_skin": bad})
    assert storage.get_ui_prefs()["pet_skin"] == "gilded"
    data = storage._load_raw()
    data["ui_prefs"]["pet_skin"] = "plaid"
    storage._save_raw(data)
    assert storage.get_ui_prefs()["pet_skin"] == "classic"


# ── tolerant reader (2.1.4): unknown entry keys ──────────────────────────────

def _raw_append(*rows):
    data = storage._load_raw()
    data["entries"].extend(rows)
    storage._save_raw(data)


def _future_row(id_="f1", date="2026-06-02"):
    return {"id": id_, "date": date, "job_shift": "Sales", "time_in": "09:00",
            "time_out": "17:00", "break_minutes": 30, "note": "covered",
            "updated_at": "2026-06-02T17:00:00Z"}


def test_unknown_entry_keys_load(tmp_storage):
    _raw_append(_future_row())
    [e] = storage.load_month(2026, 6)
    assert (e.id, e.date, e.time_in, e.time_out) == ("f1", "2026-06-02", "09:00", "17:00")
    assert e.extra == {"break_minutes": 30, "note": "covered",
                       "updated_at": "2026-06-02T17:00:00Z"}
    assert storage.load_all_entries()[0].extra["note"] == "covered"


def test_unknown_entry_keys_survive_save(tmp_storage):
    _raw_append(_future_row())
    [e] = storage.load_all_entries()
    e.time_out = "18:00"
    storage.save_entry(e)
    [row] = storage._load_raw()["entries"]
    assert row == {**_future_row(), "time_out": "18:00"}


def test_unknown_entry_keys_survive_other_saves(tmp_storage):
    _raw_append(_future_row())
    storage.save_entry(_entry(date="2026-06-01"))
    storage.delete_entry(storage.load_month(2026, 6)[0].id)  # the 1 June one
    assert storage._load_raw()["entries"] == [_future_row()]


def test_known_fields_win_over_extra(tmp_storage):
    e = _entry()
    e.extra = {"time_in": "01:00", "note": "x"}
    storage.save_entry(e)
    [row] = storage._load_raw()["entries"]
    assert row["time_in"] == "09:00" and row["note"] == "x"


def test_plain_entry_stays_five_keys(tmp_storage):
    storage.save_entry(_entry())
    [row] = storage._load_raw()["entries"]
    assert set(row) == set(storage.ENTRY_FIELDS)


def test_extra_not_compared(tmp_storage):
    a = _entry()
    b = WorkEntry(**{k: getattr(a, k) for k in storage.ENTRY_FIELDS}, extra={"note": "x"})
    assert a == b


def test_tombstones_and_bad_rows_skipped_and_kept(tmp_storage):
    bad = [{"id": "t1", "deleted": True, "updated_at": "2026-06-03T00:00:00Z"},
           {"id": "t2", "date": "2026-06-04", "deleted": True},
           {"id": "n1"},                       # no date
           {"date": "2026-06-05"},             # no id
           {"id": 7, "date": "2026-06-06"},    # id not a string
           "junk", None, 5]
    _raw_append(_future_row(), *bad)
    assert [e.id for e in storage.load_all_entries()] == ["f1"]
    assert [e.id for e in storage.load_month(2026, 6)] == ["f1"]
    storage.save_entry(_entry(date="2026-06-07"))
    rows = storage._load_raw()["entries"]
    for b in bad:
        assert b in rows
    assert len(rows) == len(bad) + 2
    storage.delete_entry("f1")
    rows = storage._load_raw()["entries"]
    assert all(b in rows for b in bad) and len(rows) == len(bad) + 1


def test_missing_or_null_fields_load_as_empty(tmp_storage):
    _raw_append({"id": "m1", "date": "2026-06-02", "time_in": "09:00",
                 "time_out": None})
    [e] = storage.load_all_entries()
    assert e.job_shift == "" and e.time_out == "" and e.extra == {}


def test_job_shift_list_tolerates_odd_entries(tmp_storage):
    _raw_append({"id": "m1", "date": "2026-06-02", "job_shift": 5,
                 "time_in": "09:00", "time_out": "17:00"},
                {"id": "t", "deleted": True, "job_shift": "Ghost"})
    shifts = storage.get_job_shift_list()
    assert "Ghost" not in shifts and 5 not in shifts


def test_save_leaves_skipped_rows_byte_for_byte(tmp_storage):
    tomb = {"id": "t2", "date": "4.6.2026", "deleted": True}
    _raw_append(tomb, {"id": "old", "date": "20260602", "job_shift": "Sales",
                       "time_in": "09:00", "time_out": "17:00"})
    storage.save_entry(_entry(date="2026-06-07"))
    rows = storage._load_raw()["entries"]
    assert tomb in rows                                   # not rewritten
    assert {"id": "old", "date": "2026-06-02", "job_shift": "Sales",
            "time_in": "09:00", "time_out": "17:00"} in rows  # still normalised


def test_default_job_shift_legacy_gpsr_when_list_unreadable(tmp_storage, monkeypatch):
    storage.save_entry(_entry(shift="GPSR"))
    def boom():
        raise OSError("locked")
    monkeypatch.setattr(storage, "get_job_shift_list", boom)
    assert storage.get_default_job_shift() == "GPSR"
