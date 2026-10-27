import warnings
from datetime import date

import pandas as pd
import pytest

import taipower_tou as tou
from taipower_tou.calendar import TaiwanCalendar
from taipower_tou.errors import CalendarError


def test_taiwan_calendar_weekend_rules() -> None:
    calendar = TaiwanCalendar()
    assert calendar.is_holiday(date(2025, 7, 12)) is False
    assert calendar.is_holiday(date(2025, 7, 13)) is True


@pytest.mark.parametrize("year", [1999, 2101])
def test_unsupported_year_raises(year) -> None:
    calendar = TaiwanCalendar()
    with pytest.raises(CalendarError):
        calendar.is_holiday(date(year, 1, 4))
    with pytest.raises(CalendarError):
        calendar.is_holiday(pd.date_range(f"{year}-01-01", periods=3, freq="D"))


@pytest.mark.parametrize(
    "kwargs", [{"cache_dir": "unused"}, {"api_timeout": 5}], ids=["cache_dir", "api"]
)
def test_removed_download_options_warn(kwargs) -> None:
    with pytest.warns(DeprecationWarning):
        tou.taiwan_calendar(**kwargs)


def test_default_calendar_does_not_warn() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        tou.period_context(
            pd.date_range("2026-01-01", periods=2), "high_voltage_2_tier"
        )


def test_timezone_aware_index_uses_local_dates() -> None:
    index = pd.date_range("2026-02-20 12:00", periods=3, freq="D", tz="Asia/Taipei")
    assert TaiwanCalendar().is_holiday(index).tolist() == [True, True, True]
