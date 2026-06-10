"""Tests for image_ocr — date/time regex parsing, normalisation, OCR glue."""
import datetime as _dt

import pytest
from PIL import Image
from winrt.windows.media.ocr import OcrEngine

import storage
import image_ocr
from image_ocr import (
    _parse_line,
    _normalise_time,
    _DATE_DM,
    _TIME_PAIR,
    extract_entries_from_image,
)


# ── _normalise_time ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("inp, expected", [
    ("09:00", "09:00"),
    ("9:00",  "09:00"),
    ("17:20", "17:20"),
    ("9:30",  "09:30"),
    ("9.30",  "09:30"),    # dot separator (existing behaviour)
    # bare hours (new)
    ("10", "10:00"),
    ("16", "16:00"),
    ("9",  "09:00"),
    ("0",  "00:00"),
    ("23", "23:00"),
    # invalid
    ("24", ""),
    ("25:00", ""),
    ("9:60", ""),
    ("abc", ""),
    ("", ""),
])
def test_normalise_time(inp, expected):
    assert _normalise_time(inp) == expected


# ── _DATE_DM regex ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("line, expected", [
    ("Monday 4.5. 10-16",            ("4", "5")),
    ("Thursday 7.5. 10-17:20",       ("7", "5")),
    ("Friday 22.5. 9:30-16",         ("22", "5")),
    ("Thursday 14.5. Ascension day", ("14", "5")),
    ("Friday 15.5. holdiay",         ("15", "5")),
])
def test_date_dm_matches(line, expected):
    m = _DATE_DM.search(line)
    assert m is not None
    assert m.groups() == expected


def test_date_dm_rejects_three_component_date():
    """(?!\\d) lookahead: '12.5.2026' must not match as '12.5.'"""
    assert _DATE_DM.search("12.5.2026 09:00-17:00") is None


# ── _TIME_PAIR regex ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("10-16",       ("10", "16")),
    ("10-17:20",    ("10", "17:20")),
    ("9:30-16",     ("9:30", "16")),
    ("10:00-16:00", ("10:00", "16:00")),
    ("10–16",       ("10", "16")),   # en dash
    ("10—16",       ("10", "16")),   # em dash
])
def test_time_pair_matches(text, expected):
    m = _TIME_PAIR.search(text)
    assert m is not None
    assert m.groups() == expected


# ── _parse_line: new "D.M." format (real sample lines) ────────────────────────

def test_parse_dm_bare_hours(tmp_storage):
    e = _parse_line("Monday 4.5. 10-16")
    assert e["date"] == f"{_dt.date.today().year}-05-04"
    assert e["time_in"]  == "10:00"
    assert e["time_out"] == "16:00"
    assert e["_confidence"] == "ok"


def test_parse_dm_mixed_minutes_out(tmp_storage):
    e = _parse_line("Thursday 7.5. 10-17:20")
    assert e["date"].endswith("-05-07")
    assert e["time_in"]  == "10:00"
    assert e["time_out"] == "17:20"
    assert e["_confidence"] == "ok"


def test_parse_dm_mixed_minutes_in(tmp_storage):
    e = _parse_line("Friday 22.5. 9:30-16")
    assert e["date"].endswith("-05-22")
    assert e["time_in"]  == "09:30"
    assert e["time_out"] == "16:00"
    assert e["_confidence"] == "ok"


def test_parse_dm_holiday_no_time(tmp_storage):
    """'Ascension day' -- date recognised, no times -> uncertain, empty times."""
    e = _parse_line("Thursday 14.5. Ascension day")
    assert e["date"].endswith("-05-14")
    assert e["time_in"]  == ""
    assert e["time_out"] == ""
    assert e["_confidence"] == "uncertain"


def test_parse_dm_holiday_typo_no_time(tmp_storage):
    """'holdiay' (typo) -- still no times -> uncertain."""
    e = _parse_line("Friday 15.5. holdiay")
    assert e["date"].endswith("-05-15")
    assert e["time_in"]  == ""
    assert e["time_out"] == ""
    assert e["_confidence"] == "uncertain"


# ── _parse_line: existing-format regressions ───────────────────────────────────

def test_parse_iso_date_with_shift_unaffected(tmp_storage):
    """ISO-dated line with explicit HH:MM-HH:MM and a known shift keyword
    must still parse correctly -- this is the regression the new
    optional-minutes _TIME_PAIR could break if searched on the whole line."""
    e = _parse_line("2026-05-12 09:00-17:00 GPSR")
    assert e["date"] == "2026-05-12"
    assert e["time_in"]  == "09:00"
    assert e["time_out"] == "17:00"
    assert e["job_shift"] == "GPSR"
    assert e["_confidence"] == "ok"


def test_parse_dmy_with_year_unaffected(tmp_storage):
    e = _parse_line("12.5.2026 09:00-17:00")
    assert e["date"] == "2026-05-12"
    assert e["time_in"]  == "09:00"
    assert e["time_out"] == "17:00"
    assert e["_confidence"] == "ok"


# ── _parse_line: shift fallback uses storage.get_default_job_shift() ──────────

def test_parse_dm_no_shift_uses_configured_default(tmp_storage):
    """Lines like 'Monday 4.5. 10-16' have no shift keyword at all --
    job_shift must come from storage.get_default_job_shift(), not a
    hardcoded 'GPSR'."""
    storage.set_default_job_shift("Sales/Support")
    e = _parse_line("Monday 4.5. 10-16")
    assert e["job_shift"] == "Sales/Support"


def test_parse_dm_no_shift_default_is_gpsr_when_unconfigured(tmp_storage):
    """storage.get_default_job_shift() itself defaults to 'GPSR' when unset."""
    assert storage.get_default_job_shift() == "GPSR"
    e = _parse_line("Monday 4.5. 10-16")
    assert e["job_shift"] == "GPSR"


def test_save_confirmed_entries_uses_default_shift_when_missing(tmp_storage):
    storage.set_default_job_shift("Training")
    imported, skipped = image_ocr.save_confirmed_entries([{
        "date": "2026-05-04", "job_shift": "", "time_in": "10:00", "time_out": "16:00",
    }])
    assert imported == 1
    assert skipped == 0
    entries = storage.load_all_entries()
    assert entries[0].job_shift == "Training"


# ── extract_entries_from_image: resize + parse glue (mocked OCR) ──────────────

def test_extract_entries_from_image_uses_ocr_text(tmp_storage, tmp_path, monkeypatch):
    """Monkeypatch _ocr_image so this test exercises the resize/line-split/
    _parse_line glue without depending on real Windows OCR or any
    installed language pack."""
    canned_text = (
        "Monday 4.5. 10-16\n"
        "Thursday 7.5. 10-17:20\n"
        "Friday 22.5. 9:30-16\n"
        "Thursday 14.5. Ascension day\n"
        "Friday 15.5. holdiay\n"
        "garbage line with no date\n"
    )
    monkeypatch.setattr(image_ocr, "_ocr_image", lambda img: canned_text)

    img_path = tmp_path / "sample.png"
    Image.new("RGB", (400, 100), color="white").save(img_path)

    results = extract_entries_from_image(str(img_path))

    assert len(results) == 5   # the 5 dated lines; "garbage line" is dropped
    assert results[0]["time_in"]  == "10:00"
    assert results[0]["time_out"] == "16:00"
    assert results[3]["_confidence"] == "uncertain"   # Ascension day
    assert results[4]["_confidence"] == "uncertain"   # holdiay


def test_extract_entries_from_image_upscales_small_images(tmp_storage, tmp_path, monkeypatch):
    """Images smaller than 1200px on the long side are upscaled before OCR."""
    seen = {}

    def _fake_ocr(img):
        seen["size"] = img.size
        return ""

    monkeypatch.setattr(image_ocr, "_ocr_image", _fake_ocr)

    img_path = tmp_path / "small.png"
    Image.new("RGB", (300, 100), color="white").save(img_path)

    extract_entries_from_image(str(img_path))

    assert max(seen["size"]) >= 1200


# ── Real-OCR smoke test (skipped if no Windows OCR language pack) ─────────────

@pytest.mark.skipif(
    OcrEngine.try_create_from_user_profile_languages() is None,
    reason="No Windows OCR language pack installed on this machine",
)
def test_ocr_image_smoke():
    """End-to-end smoke test against the real winrt OCR engine.  Skipped
    automatically on machines/CI runners without any OCR language pack."""
    from PIL import ImageDraw

    img = Image.new("RGB", (400, 80), color="white")
    d = ImageDraw.Draw(img)
    d.text((10, 20), "Hello 123", fill="black")

    text = image_ocr._ocr_image(img)
    assert isinstance(text, str)
    assert len(text) > 0
