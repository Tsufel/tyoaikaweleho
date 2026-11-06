"""The payload shapes Python sends must match the interfaces in
frontend/src/lib/api/types.ts, and the docs must name every field."""
import os
import re
from datetime import datetime

import pytest

import storage
from timer import WorkTimer
from webapp.controller import ShiftController

ROOT = os.path.join(os.path.dirname(__file__), "..")
TYPES_TS = os.path.join(ROOT, "frontend", "src", "lib", "api", "types.ts")
API_DOC = os.path.join(ROOT, "docs", "V2_UI_API.md")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _ts_keys(interface: str) -> tuple[set[str], set[str]]:
    """(required, optional) top-level field names of `export interface X {...}`."""
    m = re.search(rf"^export interface {interface}\b[^{{]*\{{\n(.*?)^\}}", _read(TYPES_TS),
                  re.S | re.M)
    assert m, f"interface {interface} not found in types.ts"
    required, optional = set(), set()
    for name, q in re.findall(r"^  (\w+)(\??):", m.group(1), re.M):
        (optional if q else required).add(name)
    return required, optional


def _ts_union(type_name: str) -> set[str]:
    m = re.search(rf"^export type {type_name} =(.*?);", _read(TYPES_TS), re.S | re.M)
    assert m, f"type {type_name} not found in types.ts"
    return set(re.findall(r"'([^']*)'", m.group(1)))


def _assert_shape(interface: str, payload: dict):
    required, optional = _ts_keys(interface)
    keys = set(payload)
    assert required - keys == set(), f"{interface}: Python omits {sorted(required - keys)}"
    extra = keys - required - optional
    assert extra == set(), f"{interface}: types.ts lacks {sorted(extra)}"


@pytest.fixture()
def ctrl(tmp_storage, tmp_timer):
    return ShiftController(timer=WorkTimer(), clock=lambda: datetime(2026, 9, 23, 10, 0))


def test_ts_parser_reads_optional_fields():
    required, optional = _ts_keys("ConfirmRequest")
    assert {"kind", "title", "options"} <= required
    assert {"token", "details"} <= optional


def test_ui_prefs_match(ctrl):
    _assert_shape("UiPrefs", storage.UI_PREF_DEFAULTS)
    assert set(storage.PETS) == _ts_union("PetKind")
    assert set(storage.PET_SKINS) == _ts_union("PetSkinId")


def test_settings_match(ctrl):
    settings = ctrl._settings()
    _assert_shape("Settings", settings)
    _assert_shape("UiPrefs", settings["ui_prefs"])


def test_bootstrap_matches(ctrl):
    data = ctrl.bootstrap("2.0.0")["data"]
    _assert_shape("Bootstrap", data)
    _assert_shape("TimerState", data["timer"])
    _assert_shape("DlcStatus", data["dlc"])


def test_timer_state_matches_idle_and_running(ctrl):
    _assert_shape("TimerState", ctrl.timer_state())
    ctrl.timer_start("now")
    state = ctrl.timer_state()
    assert state["running"] is True
    _assert_shape("TimerState", state)


def test_dlc_status_matches(ctrl):
    _assert_shape("DlcStatus", ctrl.dlc_status())


def test_month_matches(ctrl):
    _assert_shape("MonthData", ctrl.list_month(2026, 9)["data"])


# ── docs ─────────────────────────────────────────────────────────

def _doc_section(start: str, end: str) -> str:
    doc = _read(API_DOC)
    return doc[doc.index(start):doc.index(end)]


def test_doc_bootstrap_names_every_field(ctrl):
    section = _doc_section("## 7. Bootstrap payload", "## 8.")
    data = ctrl.bootstrap("2.0.0")["data"]
    missing = [k for k in data if not re.search(rf"\b{k}\b", section)]
    assert missing == [], f"docs/V2_UI_API.md §7 omits {missing}"


def test_doc_ui_prefs_name_every_pref():
    section = _doc_section("## 8. Shared shapes", "## 9.")
    ui = section[section.index("ui_prefs:"):]
    missing = [k for k in storage.UI_PREF_DEFAULTS if f"{k}:" not in ui]
    assert missing == [], f"docs/V2_UI_API.md §8 ui_prefs omits {missing}"
