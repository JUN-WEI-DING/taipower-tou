from datetime import date, datetime

import pandas as pd
import pytest

from taipower_tou import (
    InvalidUsageInput,
    monthly_breakdown,
    period_context,
    plan,
    plan_details,
    pricing_context,
)
from taipower_tou.calendar import TaiwanCalendar
from taipower_tou.tariff import PeriodType, SeasonType

# The warnings these tests cause on purpose. Any other fails them.
pytestmark = [
    # dates outside the bundled price table
    pytest.mark.filterwarnings("ignore::taipower_tou.UncheckedPriceWarning"),
]


def test_residential_simple_2_tier_periods() -> None:
    calendar = TaiwanCalendar()
    tariff_plan = plan("residential_simple_2_tier", calendar_instance=calendar)

    dt_peak = datetime(2025, 7, 15, 10, 0)
    dt_off_peak = datetime(2025, 7, 13, 10, 0)

    peak_result = tariff_plan.period_at(dt_peak)
    off_peak_result = tariff_plan.period_at(dt_off_peak)
    # Result can be either the enum or its value
    assert peak_result in (PeriodType.PEAK, PeriodType.PEAK.value)
    assert off_peak_result in (PeriodType.OFF_PEAK, PeriodType.OFF_PEAK.value)


def test_high_voltage_2_tier_plan_costs() -> None:
    calendar = TaiwanCalendar()
    tariff_plan = plan("high_voltage_2_tier", calendar_instance=calendar)

    usage = pd.Series(
        [1.0, 2.0],
        index=pd.DatetimeIndex([date(2025, 7, 15), date(2025, 7, 16)]),
    )
    costs = tariff_plan.calculate_costs(usage)
    assert len(costs) == 1
    assert (costs >= 0).all()


def test_monthly_breakdown_tou() -> None:
    calendar = TaiwanCalendar()
    index = pd.DatetimeIndex(
        [
            datetime(2025, 7, 15, 10, 0),
            datetime(2025, 7, 15, 23, 0),
        ]
    )
    usage = pd.Series([1.0, 2.0], index=index)
    result = monthly_breakdown(
        usage,
        "residential_simple_2_tier",
        calendar_instance=calendar,
    )

    assert list(result.columns) == ["month", "season", "period", "usage_kwh", "cost"]
    assert result["usage_kwh"].sum() == usage.sum()
    result_with_shares = monthly_breakdown(
        usage,
        "residential_simple_2_tier",
        include_shares=True,
        calendar_instance=calendar,
    )
    assert list(result_with_shares.columns) == [
        "month",
        "season",
        "period",
        "usage_kwh",
        "cost",
        "usage_share",
        "cost_share",
    ]


def test_monthly_breakdown_tiered() -> None:
    calendar = TaiwanCalendar()
    index = pd.DatetimeIndex(
        [
            datetime(2025, 7, 1, 10, 0),
            datetime(2025, 7, 2, 10, 0),
        ]
    )
    usage = pd.Series([3.0, 5.0], index=index)
    result = monthly_breakdown(
        usage,
        "residential_non_tou",
        calendar_instance=calendar,
    )

    assert list(result.columns) == ["month", "season", "period", "usage_kwh", "cost"]
    assert set(result["period"]) == {"tiered"}


def test_period_context_details() -> None:
    calendar = TaiwanCalendar()
    dt = datetime(2025, 7, 15, 10, 0)
    context = period_context(
        dt,
        "residential_simple_2_tier",
        calendar_instance=calendar,
    )

    assert context["season"] == SeasonType.SUMMER
    assert context["day_type"] == "weekday"
    assert context["period"] == PeriodType.PEAK


def test_plan_details_schema() -> None:
    calendar = TaiwanCalendar()
    details = plan_details(
        "residential_simple_2_tier",
        calendar_instance=calendar,
    )

    assert "profile" in details
    assert "rates" in details
    assert details["profile"]["schedules"]
    assert details["rates"]["period_costs"]


def test_pricing_context_single_basic() -> None:
    calendar = TaiwanCalendar()
    dt = datetime(2025, 7, 15, 10, 0)
    result = pricing_context(
        dt,
        "residential_simple_2_tier",
        usage=1.0,
        calendar_instance=calendar,
    )

    assert result["season"] == SeasonType.SUMMER.value
    assert result["period"] == PeriodType.PEAK.value
    assert result["rate"] is not None
    assert result["cost"] == result["rate"]


def test_pricing_context_holiday_full_day_slot_has_rate() -> None:
    calendar = TaiwanCalendar()
    dt = datetime(2025, 7, 13, 14, 0)  # Sunday
    result = pricing_context(
        dt,
        "residential_simple_2_tier",
        usage=1.0,
        calendar_instance=calendar,
    )

    assert result["period"] == PeriodType.OFF_PEAK.value
    assert result["rate"] is not None
    assert result["rate"] > 0
    assert result["cost"] == result["rate"]


def test_pricing_context_details() -> None:
    calendar = TaiwanCalendar()
    dt = datetime(2025, 7, 15, 10, 0)
    result = pricing_context(
        dt,
        "residential_simple_2_tier",
        include_details=True,
        calendar_instance=calendar,
    )

    assert "context" in result
    assert "rate_details" in result
    assert "profile_details" in result


def test_pricing_context_index_basic() -> None:
    calendar = TaiwanCalendar()
    index = pd.DatetimeIndex(
        [
            datetime(2025, 7, 15, 10, 0),
            datetime(2025, 7, 15, 23, 0),
        ]
    )
    usage = pd.Series([1.0, 2.0], index=index)
    result = pricing_context(
        index,
        "residential_simple_2_tier",
        usage=usage,
        calendar_instance=calendar,
    )

    assert list(result.columns) == ["season", "period", "rate", "cost"]
    assert (result["cost"] >= 0).all()


def test_pricing_context_tiered_no_usage() -> None:
    calendar = TaiwanCalendar()
    dt = datetime(2025, 7, 1, 10, 0)
    result = pricing_context(
        dt,
        "residential_non_tou",
        calendar_instance=calendar,
    )

    assert result["rate"] is None
    assert result["cost"] is None


def test_pricing_context_tiered_with_usage_error() -> None:
    calendar = TaiwanCalendar()
    dt = datetime(2025, 7, 1, 10, 0)
    with pytest.raises(InvalidUsageInput):
        pricing_context(
            dt,
            "residential_non_tou",
            usage=1.0,
            calendar_instance=calendar,
        )


def test_period_context_refuses_what_is_not_a_datetime():
    with pytest.raises(NotImplementedError, match="Unsupported type"):
        plan("high_voltage_2_tier").profile.period_context("2026-07-01 10:00")


def test_period_context_outside_the_calendar_years_raises():
    from taipower_tou.errors import CalendarError

    old = datetime(2010, 1, 4, 10)
    with pytest.raises(CalendarError, match="2014-2100"):
        plan("high_voltage_2_tier").profile.period_context(old)
    with pytest.raises(CalendarError, match="2014-2100"):
        plan("high_voltage_2_tier").pricing_context(old)


def test_tiered_plan_refuses_a_price_for_usage():
    """A tiered price depends on the month's total, not one reading."""
    from taipower_tou import InvalidUsageInput

    with pytest.raises(InvalidUsageInput, match="tiered"):
        plan("residential_non_tou").pricing_context(
            datetime(2026, 7, 1, 10), usage_kwh=1.0
        )
