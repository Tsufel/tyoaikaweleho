"""storage.read_cache(): one API call reads and parses data.json once, and
still sees every change made to the file (by this process or another)."""

import json
import os
import threading
from datetime import datetime

import pytest

import storage
from timer import WorkTimer
from webapp.api import Api
from webapp.controller import ShiftController


def _entry(id_, day="2026-09-02", t_in="09:00", t_out="17:00"):
    return {"id": id_, "date": day, "job_shift": "Sales", "time_in": t_in, "time_out": t_out}


def _write(path, data, mtime_ns=None):
    """Write data.json the way another program would (not through storage)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    if mtime_ns is not None:
        os.utime(path, ns=(mtime_ns, mtime_ns))


@pytest.fixture()
def data_file(tmp_storage):
    path = storage.DATA_FILE
    _write(path, {"entries": [_entry("a"), _entry("b", "2026-08-31")], "pay_rate": 15.0})
    return path


@pytest.fixture()
def api(tmp_storage, tmp_timer):
    clock = lambda: datetime(2026, 9, 23, 10, 0, 0)  # noqa: E731
    return Api(ShiftController(timer=WorkTimer(), clock=clock), version="2.0.0",
               frozen=False, dev=True)


def _loads(fn):
    before = storage.load_count
    fn()
    return storage.load_count - before


# ── storage layer ────────────────────────────────────────────────────────────

def test_without_a_scope_every_read_parses(data_file):
    assert _loads(lambda: (storage.load_month(2026, 9), storage.get_pay_rate(),
                           storage.load_all_entries())) == 3


def test_inside_a_scope_reads_parse_once(data_file):
    with storage.read_cache():
        n = _loads(lambda: (storage.load_month(2026, 9), storage.get_pay_rate(),
                            storage.load_all_entries(), storage.get_ui_prefs(),
                            storage.get_sheet_names(), storage.get_window_placement()))
    assert n == 1


def test_the_cache_ends_with_the_scope(data_file):
    with storage.read_cache():
        storage.get_pay_rate()
    assert _loads(storage.get_pay_rate) == 1


def test_nested_scopes_share_the_cache_until_the_outer_one_ends(data_file):
    with storage.read_cache():
        storage.get_pay_rate()
        with storage.read_cache():
            assert _loads(storage.get_pay_rate) == 0
        assert _loads(storage.get_pay_rate) == 0
    assert _loads(storage.get_pay_rate) == 1


def test_a_save_in_the_scope_is_seen_by_the_next_read(data_file):
    with storage.read_cache():
        assert storage.get_pay_rate() == 15.0
        storage.set_pay_rate(22.5)
        assert storage.get_pay_rate() == 22.5
        storage.add_entries([storage.WorkEntry("c", "2026-09-03", "Sales", "08:00", "12:00")])
        assert {e.id for e in storage.load_month(2026, 9)} == {"a", "c"}


def test_a_change_by_another_program_is_seen(data_file):
    with storage.read_cache():
        assert storage.get_pay_rate() == 15.0
        _write(data_file, {"entries": [], "pay_rate": 31.0})
        assert storage.get_pay_rate() == 31.0
        assert storage.load_all_entries() == []


def test_same_size_rewrite_with_a_new_mtime_is_seen(data_file):
    st = os.stat(data_file)
    with storage.read_cache():
        assert storage.get_pay_rate() == 15.0
        # same byte count, different content, a later timestamp
        _write(data_file, {"entries": [_entry("a"), _entry("b", "2026-08-31")],
                           "pay_rate": 16.0}, mtime_ns=st.st_mtime_ns + 1_000_000_000)
        assert os.stat(data_file).st_size == st.st_size
        assert storage.get_pay_rate() == 16.0


def test_a_failed_save_does_not_leave_a_changed_copy_cached(data_file, monkeypatch):
    def locked(src, dst):
        raise PermissionError("locked")
    with storage.read_cache():
        storage.get_pay_rate()
        monkeypatch.setattr(storage, "_replace", locked)
        with pytest.raises(PermissionError):
            storage.set_pay_rate(99.0)
        assert storage.get_pay_rate() == 15.0


def test_writers_get_their_own_copy(data_file):
    with storage.read_cache():
        shared = storage._read_raw()
        mine = storage._load_raw()
        assert mine is not shared and mine == shared
        mine["pay_rate"] = 1.0
        assert storage.get_pay_rate() == 15.0


def test_a_missing_file_is_not_cached(tmp_storage):
    with storage.read_cache():
        assert storage.load_all_entries() == []
        _write(storage.DATA_FILE, {"entries": [_entry("a")]})
        assert [e.id for e in storage.load_all_entries()] == ["a"]


def test_a_damaged_file_is_restored_and_then_cached(data_file):
    with open(data_file, "rb") as f:
        good = f.read()
    with open(data_file + ".bak", "wb") as f:
        f.write(good)
    with open(data_file, "wb") as f:
        f.write(b"{not json")
    with storage.read_cache():
        assert storage.get_pay_rate() == 15.0
        assert {e.id for e in storage.load_all_entries()} == {"a", "b"}
        assert _loads(storage.get_pay_rate) == 0
    assert storage.last_recovery is not None


def test_scopes_are_per_thread(data_file):
    seen = {}

    def other():
        seen["loads"] = _loads(storage.get_pay_rate)

    with storage.read_cache():
        storage.get_pay_rate()
        t = threading.Thread(target=other)
        t.start()
        t.join()
    assert seen["loads"] == 1


# ── through the API: one call, one parse ─────────────────────────────────────

def test_list_month_parses_once(data_file, api):
    assert _loads(lambda: api.list_month(2026, 9)) == 1


@pytest.mark.parametrize("call", [
    lambda a: a.get_settings(),
    lambda a: a.get_stats("2026-09-01", "2026-09-30", "day"),
    lambda a: a.get_stats_span(),
    lambda a: a.bootstrap(),
])
def test_read_calls_parse_once(data_file, api, call):
    result = call(api)
    assert result["ok"], result
    assert _loads(lambda: call(api)) == 1


def test_calls_pick_up_changes_between_them(data_file, api):
    first = api.list_month(2026, 9)
    assert [r["id"] for r in first["data"]["entries"]] == ["a"]
    _write(data_file, {"entries": [_entry("a"), _entry("z", "2026-09-05")], "pay_rate": 15.0})
    second = api.list_month(2026, 9)
    assert [r["id"] for r in second["data"]["entries"]] == ["a", "z"]
