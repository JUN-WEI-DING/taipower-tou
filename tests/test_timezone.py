"""Timezone-aware input gives the same results as naive Taiwan local time."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

import taipower_tou as tou

TAIWAN_JULY = pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min")


def _weekday_daytime_load(index):
    """A factory that runs 08:00-18:00 on weekdays, where day types matter."""
    local = index.tz_convert("Asia/Taipei") if index.tz is not None else index
    running = (local.day_of_week < 5) & (local.hour >= 8) & (local.hour < 18)
    return pd.Series(running.astype(float) * 100.0, index=index)


AWARE = {
    "taipei": TAIWAN_JULY.tz_localize("Asia/Taipei"),
    "utc": TAIWAN_JULY.tz_localize("Asia/Taipei").tz_convert("UTC"),
}


@pytest.mark.parametrize("zone", AWARE)
def test_period_context_uses_taiwan_local_time(zone):
    naive = tou.period_context(TAIWAN_JULY, "high_voltage_three_stage")
    aware = tou.period_context(AWARE[zone], "high_voltage_three_stage")
    assert aware.index.equals(AWARE[zone])
    for column in ("season", "day_type", "period"):
        assert aware[column].tolist() == naive[column].tolist()


@pytest.mark.parametrize(
    "plan_name", ["high_voltage_three_stage", "high_voltage_2_tier"]
)
@pytest.mark.parametrize("zone", AWARE)
def test_costs_use_taiwan_local_time(plan_name, zone):
    plan = tou.plan(plan_name)
    naive = plan.calculate_costs(_weekday_daytime_load(TAIWAN_JULY))
    aware = plan.calculate_costs(_weekday_daytime_load(AWARE[zone]))
    pd.testing.assert_series_equal(aware, naive)


@pytest.mark.parametrize("zone", AWARE)
def test_bill_uses_taiwan_local_time(zone):
    inputs = tou.BillingInputs(
        taipower_rounding=False,
        meter_phase="single",
        meter_voltage_v=110,
        meter_ampere=10,
    )
    naive = tou.calculate_bill(
        _weekday_daytime_load(TAIWAN_JULY) / 100,
        "residential_simple_2_tier",
        inputs=inputs,
    )
    aware = tou.calculate_bill(
        _weekday_daytime_load(AWARE[zone]) / 100,
        "residential_simple_2_tier",
        inputs=inputs,
    )
    pd.testing.assert_frame_equal(aware, naive)


def test_aware_datetime_uses_taiwan_date():
    sunday_evening_utc = datetime(2026, 7, 12, 20, 0, tzinfo=timezone.utc)
    monday_morning_taiwan = sunday_evening_utc.astimezone(timezone(timedelta(hours=8)))
    assert tou.is_holiday(sunday_evening_utc) is False
    assert tou.is_holiday(monday_morning_taiwan) is False
    assert tou.is_holiday(sunday_evening_utc.replace(tzinfo=None)) is True
