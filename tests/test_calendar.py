import json
from datetime import date
from unittest.mock import Mock, patch

from tou_calculator.calendar import TaiwanCalendar


def test_taiwan_calendar_weekend_rules() -> None:
    # Mock read_file to return empty list (no holidays)
    with patch("tou_calculator.calendar._HolidayCache.read_file", return_value=[]):
        cal = TaiwanCalendar(cache_dir=None)
        # Saturday is not a holiday by default if not in list
        assert cal.is_holiday(date(2025, 7, 12)) is False
        # Sunday is always a holiday
        assert cal.is_holiday(date(2025, 7, 13)) is True


def test_taiwan_calendar_cached_holiday() -> None:
    data = [
        {
            "date": "20251010",
            "description": "National Day",
            "isHoliday": True,
        }
    ]
    
    # Mock read_file to return our specific holiday data
    with patch("tou_calculator.calendar._HolidayCache.read_file", return_value=data):
        cal = TaiwanCalendar(cache_dir=None)
        assert cal.is_holiday(date(2025, 10, 10)) is True
