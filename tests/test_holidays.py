"""Finnish public holidays (holidays.py)."""
import json
import os
from datetime import date, timedelta

import pytest

import holidays

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "fi_holidays.json")

# Checked by hand against the Finnish calendar, independent of the code.
KNOWN = {
    2024: {
        "2024-01-01": "Uudenvuodenpäivä", "2024-01-06": "Loppiainen",
        "2024-03-29": "Pitkäperjantai", "2024-03-31": "Pääsiäispäivä",
        "2024-04-01": "2. pääsiäispäivä", "2024-05-01": "Vappu",
        "2024-05-09": "Helatorstai", "2024-06-21": "Juhannusaatto",
        "2024-06-22": "Juhannuspäivä", "2024-11-02": "Pyhäinpäivä",
        "2024-12-06": "Itsenäisyyspäivä", "2024-12-24": "Jouluaatto",
        "2024-12-25": "Joulupäivä", "2024-12-26": "Tapaninpäivä",
    },
    2025: {
        "2025-01-01": "Uudenvuodenpäivä", "2025-01-06": "Loppiainen",
        "2025-04-18": "Pitkäperjantai", "2025-04-20": "Pääsiäispäivä",
        "2025-04-21": "2. pääsiäispäivä", "2025-05-01": "Vappu",
        "2025-05-29": "Helatorstai", "2025-06-20": "Juhannusaatto",
        "2025-06-21": "Juhannuspäivä", "2025-11-01": "Pyhäinpäivä",
        "2025-12-06": "Itsenäisyyspäivä", "2025-12-24": "Jouluaatto",
        "2025-12-25": "Joulupäivä", "2025-12-26": "Tapaninpäivä",
    },
    2026: {
        "2026-01-01": "Uudenvuodenpäivä", "2026-01-06": "Loppiainen",
        "2026-04-03": "Pitkäperjantai", "2026-04-05": "Pääsiäispäivä",
        "2026-04-06": "2. pääsiäispäivä", "2026-05-01": "Vappu",
        "2026-05-14": "Helatorstai", "2026-06-19": "Juhannusaatto",
        "2026-06-20": "Juhannuspäivä", "2026-10-31": "Pyhäinpäivä",
        "2026-12-06": "Itsenäisyyspäivä", "2026-12-24": "Jouluaatto",
        "2026-12-25": "Joulupäivä", "2026-12-26": "Tapaninpäivä",
    },
    2027: {
        "2027-01-01": "Uudenvuodenpäivä", "2027-01-06": "Loppiainen",
        "2027-03-26": "Pitkäperjantai", "2027-03-28": "Pääsiäispäivä",
        "2027-03-29": "2. pääsiäispäivä", "2027-05-01": "Vappu",
        "2027-05-06": "Helatorstai", "2027-06-25": "Juhannusaatto",
        "2027-06-26": "Juhannuspäivä", "2027-11-06": "Pyhäinpäivä",
        "2027-12-06": "Itsenäisyyspäivä", "2027-12-24": "Jouluaatto",
        "2027-12-25": "Joulupäivä", "2027-12-26": "Tapaninpäivä",
    },
}


@pytest.mark.parametrize("year", sorted(KNOWN))
def test_known_years(year):
    got = {d.isoformat(): n for d, n in holidays.holidays_in_year(year).items()}
    assert got == KNOWN[year]


@pytest.mark.parametrize("year,easter", [
    (2008, date(2008, 3, 23)), (2011, date(2011, 4, 24)), (2019, date(2019, 4, 21)),
    (2028, date(2028, 4, 16)), (2029, date(2029, 4, 1)), (2030, date(2030, 4, 21)),
    (2038, date(2038, 4, 25)), (2285, date(2285, 3, 22)), (2000, date(2000, 4, 23)),
])
def test_easter_including_earliest_and_latest(year, easter):
    assert holidays.easter_sunday(year) == easter


@pytest.mark.parametrize("year", range(1990, 2100))
def test_rules_hold_every_year(year):
    days = holidays.holidays_in_year(year)
    by_name = {part: d for d, n in days.items() for part in n.split(" / ")}
    assert len(by_name) == 14
    easter = by_name["Pääsiäispäivä"]
    assert easter.weekday() == 6 and (3, 22) <= (easter.month, easter.day) <= (4, 25)
    assert by_name["Pitkäperjantai"].weekday() == 4
    assert by_name["2. pääsiäispäivä"].weekday() == 0
    assert by_name["Helatorstai"].weekday() == 3
    mid = by_name["Juhannuspäivä"]
    assert mid.weekday() == 5 and mid.month == 6 and 20 <= mid.day <= 26
    eve = by_name["Juhannusaatto"]
    assert eve.weekday() == 4 and eve == mid - timedelta(days=1) and 19 <= eve.day <= 25
    saints = by_name["Pyhäinpäivä"]
    assert saints.weekday() == 5
    assert date(year, 10, 31) <= saints <= date(year, 11, 6)
    assert list(days) == sorted(days)


def test_fixture_matches_the_code():
    """The fixture is what the TypeScript twin is tested against too."""
    with open(FIXTURE, encoding="utf-8") as f:
        fixture = json.load(f)
    assert len(fixture) >= 10
    for year, expected in fixture.items():
        got = {d.isoformat(): n for d, n in holidays.holidays_in_year(int(year)).items()}
        assert got == expected, year


def test_shared_date_names_both():
    # Helatorstai fell on Vappu in 2008
    assert holidays.holiday_name(date(2008, 5, 1)) == "Vappu / Helatorstai"
    assert len(holidays.holidays_in_year(2008)) == 13


def test_month_and_lookup():
    assert holidays.holidays_in_month(2026, 12) == {
        "2026-12-06": "Itsenäisyyspäivä", "2026-12-24": "Jouluaatto",
        "2026-12-25": "Joulupäivä", "2026-12-26": "Tapaninpäivä"}
    assert holidays.holidays_in_month(2026, 2) == {}
    # Pyhäinpäivä can fall in October or November
    assert holidays.holidays_in_month(2026, 10) == {"2026-10-31": "Pyhäinpäivä"}
    assert holidays.holidays_in_month(2026, 11) == {}
    assert holidays.holidays_in_month(2027, 11) == {"2027-11-06": "Pyhäinpäivä"}
    assert holidays.holiday_name(date(2026, 5, 1)) == "Vappu"
    assert holidays.holiday_name(date(2026, 5, 2)) is None
    assert holidays.is_holiday(date(2026, 4, 3))
    assert not holidays.is_holiday(date(2026, 4, 7))
