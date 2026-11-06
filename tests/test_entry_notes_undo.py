"""Shift notes and the undo of adds / edits (docs/V2_UI_API.md §6.5, §6.6)."""
from datetime import datetime

import pytest

import storage
from timer import WorkTimer
from webapp.controller import ShiftController

DRAFT = {"date": "2026-09-23", "job_shift": "Sales", "time_in": "09:00", "time_out": "17:00"}


@pytest.fixture()
def ctrl(tmp_storage, tmp_timer):
    return ShiftController(timer=WorkTimer(), clock=lambda: datetime(2026, 9, 23, 10, 0))


def _delete(token):
    return [{"kind": "delete_entry", "choice": "delete", "token": token}]


def _row(id_):
    return next(r for r in storage._load_raw()["entries"] if r.get("id") == id_)


def _add(**kw):
    e = storage.WorkEntry(id=storage.new_entry_id(), **{**DRAFT, **kw})
    storage.save_entry(e)
    return e


# ── notes ────────────────────────────────────────────────────────

def test_save_entry_stores_trimmed_note(ctrl):
    r = ctrl.save_entry({**DRAFT, "note": "  Covered\nfor Sam  "})
    assert r["status"] == "saved" and r["entry"]["note"] == "Covered for Sam"
    assert _row(r["entry"]["id"])["note"] == "Covered for Sam"
    assert ctrl.list_month(2026, 9)["data"]["entries"][0]["note"] == "Covered for Sam"


def test_save_entry_without_note_keeps_plain_shape(ctrl):
    r = ctrl.save_entry(dict(DRAFT))
    assert r["entry"]["note"] == ""
    assert set(_row(r["entry"]["id"])) == set(storage.ENTRY_FIELDS)


def test_save_entry_rejects_long_note(ctrl):
    r = ctrl.save_entry({**DRAFT, "note": "x" * 201})
    assert r["status"] == "invalid" and r["field"] == "note"
    assert storage.load_all_entries() == []


def test_edit_keeps_note_unless_given(ctrl):
    id_ = ctrl.save_entry({**DRAFT, "note": "keep me"})["entry"]["id"]
    ctrl.save_entry({**DRAFT, "id": id_, "time_out": "18:00"})
    assert _row(id_)["note"] == "keep me"
    assert ctrl.update_entry_field(id_, "time_in", "08:00")["status"] == "saved"
    assert _row(id_)["note"] == "keep me"
    ctrl.save_entry({**DRAFT, "id": id_, "note": ""})
    assert "note" not in _row(id_)


def test_delete_and_restore_keep_note(ctrl):
    id_ = ctrl.save_entry({**DRAFT, "note": "hi"})["entry"]["id"]
    token = ctrl.delete_entry(id_)["confirm"]["token"]
    r = ctrl.delete_entry(id_, _delete(token))
    assert r["deleted"]["note"] == "hi"
    r = ctrl.restore_entry(r["deleted"])
    assert r["entry"]["note"] == "hi" and _row(id_)["note"] == "hi"


def test_old_file_without_notes_loads(ctrl):
    data = storage._load_raw()
    data["entries"] = [{"id": "old", **DRAFT}]
    storage._save_raw(data)
    [row] = ctrl.list_month(2026, 9)["data"]["entries"]
    assert row["note"] == ""


# ── undo of adds and edits ───────────────────────────────────────

def test_add_returns_token_and_no_before(ctrl):
    r = ctrl.save_entry(dict(DRAFT))
    assert r["before"] is None and isinstance(r["token"], str)


def test_undo_add_deletes_while_unchanged(ctrl):
    r = ctrl.save_entry(dict(DRAFT))
    u = ctrl.delete_entry(r["entry"]["id"], _delete(r["token"]))
    assert u["status"] == "ok" and storage.load_all_entries() == []


def test_undo_add_is_stale_after_another_change(ctrl):
    r = ctrl.save_entry(dict(DRAFT))
    ctrl.update_entry_field(r["entry"]["id"], "time_out", "18:00")
    u = ctrl.delete_entry(r["entry"]["id"], _delete(r["token"]))
    assert u["status"] == "error" and u["error"]["code"] == "stale"
    assert len(storage.load_all_entries()) == 1


def test_undo_add_is_stale_after_a_note_change(ctrl):
    r = ctrl.save_entry(dict(DRAFT))
    ctrl.save_entry({**DRAFT, "id": r["entry"]["id"], "note": "later"})
    u = ctrl.delete_entry(r["entry"]["id"], _delete(r["token"]))
    assert u["error"]["code"] == "stale"


def test_undo_modal_edit_puts_back_before_with_extras(ctrl):
    data = storage._load_raw()
    data["entries"] = [{"id": "fut1", **DRAFT, "break_minutes": 30, "note": "x"}]
    storage._save_raw(data)
    before = _row("fut1")
    r = ctrl.save_entry({**DRAFT, "id": "fut1", "time_out": "18:00", "note": "late"})
    assert r["before"] == before
    u = ctrl.revert_entry(r["before"], r["token"])
    assert u["status"] == "saved" and u["entry"]["time_out"] == "17:00"
    assert u["description"]
    assert _row("fut1") == before


def test_undo_inline_edit_puts_back_before(ctrl):
    e = _add()
    r = ctrl.update_entry_field(e.id, "time_in", "08:00")
    assert r["before"]["time_in"] == "09:00"
    assert ctrl.revert_entry(r["before"], r["token"])["status"] == "saved"
    assert storage.load_all_entries()[0].time_in == "09:00"


def test_revert_is_stale_when_entry_changed_again(ctrl):
    e = _add()
    r = ctrl.update_entry_field(e.id, "time_in", "08:00")
    ctrl.save_entry({**DRAFT, "id": e.id, "time_in": "08:00", "note": "changed"})
    u = ctrl.revert_entry(r["before"], r["token"])
    assert u["status"] == "error" and u["error"]["code"] == "stale"
    assert storage.load_all_entries()[0].note == "changed"


def test_revert_when_entry_gone_or_bad(ctrl):
    e = _add()
    r = ctrl.update_entry_field(e.id, "time_in", "08:00")
    assert ctrl.revert_entry(r["before"], None)["error"]["code"] == "stale"
    storage.delete_entry(e.id)
    u = ctrl.revert_entry(r["before"], r["token"])
    assert u["error"]["code"] == "not_found" and storage.load_all_entries() == []
    assert ctrl.revert_entry({"bad": 1}, "x")["status"] == "invalid"


def test_revert_save_failure(ctrl, monkeypatch):
    e = _add()
    r = ctrl.update_entry_field(e.id, "time_in", "08:00")

    def boom(_):
        raise OSError("locked")
    monkeypatch.setattr(storage, "save_entry", boom)
    u = ctrl.revert_entry(r["before"], r["token"])
    assert u["error"]["code"] == "save_failed"
    assert storage.load_all_entries()[0].time_in == "08:00"
