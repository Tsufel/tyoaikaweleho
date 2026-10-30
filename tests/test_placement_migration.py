"""Tests for the v2 window placement (with v1 geometry migration), ui_prefs
and the save_settings transaction in storage."""
import json

import pytest

import storage


def _write(tmp_storage, data):
    (tmp_storage / "data.json").write_text(json.dumps(data), encoding="utf-8")


def test_no_placement(tmp_storage):
    assert storage.get_window_placement() is None


def test_migrates_v1_geometry(tmp_storage):
    _write(tmp_storage, {"entries": [], "window_geometry": {"geometry": "1200x800+-1500+40",
                                                            "zoomed": True}})
    assert storage.get_window_placement() == {"v": 2, "left": -1500, "top": 40, "right": -300,
                                              "bottom": 840, "maximized": True}


@pytest.mark.parametrize("geom", ["garbage", "0x800+0+0", 42])
def test_bad_v1_geometry(tmp_storage, geom):
    _write(tmp_storage, {"entries": [], "window_geometry": {"geometry": geom}})
    assert storage.get_window_placement() is None


def test_set_placement_writes_both(tmp_storage):
    storage.set_window_placement({"left": 10, "top": 20, "right": 1010, "bottom": 720,
                                  "maximized": False})
    assert storage.get_window_placement()["right"] == 1010
    assert storage.get_window_geometry() == ("1000x700+10+20", False)


def test_v2_wins_over_v1(tmp_storage):
    _write(tmp_storage, {"entries": [],
                         "window_geometry": {"geometry": "100x100+0+0"},
                         "window_placement": {"v": 2, "left": 5, "top": 5, "right": 50,
                                              "bottom": 60, "maximized": True}})
    assert storage.get_window_placement()["left"] == 5


@pytest.mark.parametrize("p", [
    {"left": 10, "top": 0, "right": 10, "bottom": 100},
    {"left": 0, "top": 0, "right": 1.5, "bottom": 100},
    {"left": True, "top": 0, "right": 10, "bottom": 100},
    None,
])
def test_set_placement_invalid(tmp_storage, p):
    with pytest.raises(ValueError):
        storage.set_window_placement(p)
    assert not (tmp_storage / "data.json").exists()


def test_unknown_placement_version_falls_back(tmp_storage):
    _write(tmp_storage, {"entries": [], "window_placement": {"v": 3, "left": 0, "top": 0,
                                                             "right": 9, "bottom": 9}})
    assert storage.get_window_placement() is None


# ── ui_prefs ──────────────────────────────────────────────────────────────────

def test_ui_prefs_defaults_and_lenient_read(tmp_storage):
    assert storage.get_ui_prefs() == storage.UI_PREF_DEFAULTS
    _write(tmp_storage, {"entries": [], "ui_prefs": {"lulz": "yes", "target_hours": 99,
                                                     "reduce_effects": True, "lulz_sound": "yes",
                                                     "liquid_glass": "x"}})
    assert storage.get_ui_prefs() == {"lulz": False, "reduce_effects": True,
                                      "lulz_sound": False, "liquid_glass": False,
                                      "target_hours": 8.0}


def test_set_ui_prefs_partial(tmp_storage):
    storage.set_ui_prefs({"lulz": True})
    assert storage.set_ui_prefs({"target_hours": 6}) == {"lulz": True, "reduce_effects": False,
                                                         "lulz_sound": False, "liquid_glass": False,
                                                         "target_hours": 6.0}


def test_set_ui_prefs_lulz_sound_round_trips(tmp_storage):
    assert storage.set_ui_prefs({"lulz_sound": True})["lulz_sound"] is True
    assert storage.get_ui_prefs()["lulz_sound"] is True
    storage.set_ui_prefs({"lulz_sound": False})
    assert storage.get_ui_prefs()["lulz_sound"] is False


def test_set_ui_prefs_liquid_glass_round_trips(tmp_storage):
    assert storage.set_ui_prefs({"liquid_glass": True})["liquid_glass"] is True
    assert storage.get_ui_prefs()["liquid_glass"] is True
    storage.set_ui_prefs({"liquid_glass": False})
    assert storage.get_ui_prefs()["liquid_glass"] is False


@pytest.mark.parametrize("changes", [{"target_hours": 0.5}, {"target_hours": float("nan")},
                                     {"lulz": 1}, {"lulz_sound": "yes"}, {"lulz_sound": None},
                                     {"liquid_glass": "yes"}, {"liquid_glass": None},
                                     {"nope": True}, "x"])
def test_set_ui_prefs_invalid(tmp_storage, changes):
    with pytest.raises(ValueError):
        storage.set_ui_prefs(changes)


# ── save_settings ─────────────────────────────────────────────────────────────

def test_save_settings_all_at_once(tmp_storage):
    storage.save_settings({"pay_rate": 21, "default_start_time": "07:30",
                           "default_job_shift": "Support", "export_format": "Full",
                           "export_include_pay": True, "appearance_mode": "Light",
                           "ui_prefs": {"lulz": True, "lulz_sound": True,
                                        "liquid_glass": True}})
    data = json.loads((tmp_storage / "data.json").read_text(encoding="utf-8"))
    assert data["pay_rate"] == 21.0 and isinstance(data["pay_rate"], float)
    assert storage.get_default_start_time() == "07:30"
    assert storage.get_appearance_mode() == "Light"
    assert storage.get_ui_prefs()["lulz"] is True and storage.get_ui_prefs()["lulz_sound"] is True
    assert storage.get_ui_prefs()["liquid_glass"] is True


@pytest.mark.parametrize("values", [
    {"pay_rate": 0}, {"pay_rate": True}, {"default_start_time": "7:30"},
    {"export_format": "Fancy"}, {"export_include_pay": "yes"},
    {"appearance_mode": "Neon"}, {"mystery": 1},
])
def test_save_settings_rejects_without_writing(tmp_storage, values):
    with pytest.raises(ValueError):
        storage.save_settings({"default_job_shift": "Support", **values})
    assert not (tmp_storage / "data.json").exists()


def test_save_settings_bad_ui_prefs_writes_nothing(tmp_storage):
    with pytest.raises(ValueError):
        storage.save_settings({"pay_rate": 30.0, "ui_prefs": {"target_hours": 40}})
    assert storage.get_pay_rate() == 20.0
