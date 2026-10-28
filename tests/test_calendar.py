import warnings
from datetime import date

import pandas as pd
import pytest

import taipower_tou as tou
from taipower_tou.calendar import TaiwanCalendar, _warn_unchecked_year
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


@pytest.mark.filterwarnings("ignore::UserWarning")
@pytest.mark.parametrize("year", [2013, 2101])
@pytest.mark.parametrize("plan", ["residential_non_tou", "residential_simple_2_tier"])
def test_every_entry_point_refuses_unsupported_years(plan, year) -> None:
    """CHANGELOG 0.2.0: years outside 2014-2100 raise CalendarError, and
    calendar_instance=custom_calendar(...) bills them. A tiered plan needs no
    day types but is refused the same way."""
    usage = pd.Series(1.0, index=pd.date_range(f"{year}-01-01", periods=48, freq="h"))
    for call in (tou.costs, tou.monthly_breakdown, tou.calculate_bill):
        with pytest.raises(CalendarError):
            call(usage, plan)
    assert len(tou.costs(usage, plan, calendar_instance=tou.custom_calendar())) == 1


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


def test_year_after_last_checked_calendar_warns_once() -> None:
    _warn_unchecked_year.cache_clear()
    with pytest.warns(tou.UncheckedYearWarning, match="2028") as record:
        for _ in range(3):
            tou.period_context(
                pd.date_range("2027-12-31", periods=2), "high_voltage_three_stage"
            )
            TaiwanCalendar().is_holiday(date(2028, 1, 4))
    assert len(record) == 1


def test_checked_years_do_not_warn() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        TaiwanCalendar().is_holiday(pd.date_range("2014-01-01", "2027-12-31"))
