"""Day types must match Taipower's official 時間電價日曆表 day by day.

tests/data/taipower_calendar/<year>.csv is read from Taipower's calendar PDF by
scripts/read_tou_calendar_pdf.py; its README names the source files.
"""

import csv
import socket
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import taipower_tou as tou
from taipower_tou.calendar import LAST_CHECKED_YEAR

OFFICIAL_CALENDARS = sorted(
    (Path(__file__).parent / "data" / "taipower_calendar").glob("*.csv")
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("network access is not allowed in this test")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


def _official_day_types(path):
    with open(path, encoding="utf-8") as f:
        return {
            date.fromisoformat(row["date"]): row["day_type"]
            for row in csv.DictReader(f)
        }


def _mismatches(expected, actual):
    return [
        f"{day} {actual[day]} (official {expected[day]})"
        for day in sorted(expected)
        if actual[day] != expected[day]
    ]


@pytest.mark.parametrize("path", OFFICIAL_CALENDARS, ids=lambda p: p.stem)
def test_period_context_day_types_match_official_calendar(path):
    expected = _official_day_types(path)
    noon = pd.DatetimeIndex([f"{day} 12:00" for day in sorted(expected)])
    context = tou.period_context(noon, "high_voltage_three_stage")
    actual = dict(zip(noon.date, context["day_type"]))
    assert not _mismatches(expected, actual)


@pytest.mark.parametrize("path", OFFICIAL_CALENDARS, ids=lambda p: p.stem)
def test_is_holiday_matches_official_calendar(path):
    expected = _official_day_types(path)
    calendar = tou.taiwan_calendar()
    wrong = [
        str(day)
        for day, day_type in sorted(expected.items())
        if calendar.is_holiday(day) != (day_type == "sunday_holiday")
    ]
    assert not wrong


def test_last_checked_year_is_the_newest_official_calendar():
    assert LAST_CHECKED_YEAR == int(OFFICIAL_CALENDARS[-1].stem)
