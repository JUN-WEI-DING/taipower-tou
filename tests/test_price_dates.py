"""Usage outside the bundled price table's dates raises UncheckedPriceWarning."""

import warnings

import pandas as pd
import pytest

import taipower_tou as tou
from taipower_tou.rates import TariffJSONLoader
from taipower_tou.tariff import _warn_outside_price_dates

INPUTS = tou.BillingInputs(meter_phase="single", meter_voltage_v=110, meter_ampere=10)


def _usage(start, periods=48, tz=None):
    index = pd.date_range(start, periods=periods, freq="h", tz=tz)
    return pd.Series(1.0, index=index)


def _price_uses():
    yield lambda usage: tou.calculate_bill(usage, "residential_simple_2_tier", INPUTS)
    yield lambda usage: tou.calculate_bill_breakdown(
        usage, "residential_simple_2_tier", INPUTS
    )
    yield lambda usage: tou.plan("residential_simple_2_tier").calculate_costs(usage)
    yield lambda usage: tou.plan("high_voltage_2_tier").calculate_costs(usage)
    yield lambda usage: tou.plan("high_voltage_2_tier").monthly_breakdown(usage)
    yield lambda usage: tou.plan("high_voltage_2_tier").pricing_context(usage.index)


@pytest.mark.parametrize(
    ("start", "match"),
    [("2025-09-30", "earlier prices"), ("2026-12-31", "after that day")],
    ids=["before", "after"],
)
def test_usage_outside_price_dates_warns_once(start, match):
    _warn_outside_price_dates.cache_clear()
    with pytest.warns(tou.UncheckedPriceWarning, match=match) as record:
        for use in _price_uses():
            use(_usage(start))
    assert len(record) == 1


def test_usage_inside_price_dates_does_not_warn():
    _warn_outside_price_dates.cache_clear()
    with warnings.catch_warnings():
        warnings.simplefilter("error", tou.UncheckedPriceWarning)
        for use in _price_uses():
            use(_usage("2025-10-01", periods=24 * 7))
            use(_usage("2026-12-25", periods=24 * 7))


def test_price_dates_use_taiwan_local_time():
    _warn_outside_price_dates.cache_clear()
    with warnings.catch_warnings():
        warnings.simplefilter("error", tou.UncheckedPriceWarning)
        tou.calculate_bill(
            _usage("2025-09-30 16:00", tz="UTC"), "residential_simple_2_tier", INPUTS
        )
    with pytest.warns(tou.UncheckedPriceWarning):
        tou.calculate_bill(
            _usage("2025-09-30 15:00", tz="UTC"), "residential_simple_2_tier", INPUTS
        )


def test_price_dates_start_on_the_table_version():
    data = TariffJSONLoader().load()
    assert data["price_dates"]["effective_from"].replace("-", "") == data["version"]


def test_caller_supplied_prices_do_not_warn():
    season = tou.TaiwanSeasonStrategy((6, 1), (9, 30))
    profile = tou.build_tariff_profile(
        name="flat",
        season_strategy=season,
        day_type_strategy=tou.WeekdayDayTypeStrategy(tou.custom_calendar()),
        schedules=[],
        default_period="off_peak",
    )
    rates = tou.build_tariff_rate(
        period_costs=[{"season": "non_summer", "period": "off_peak", "cost": 1.0}],
        season_strategy=season,
    )
    plan = tou.build_tariff_plan(profile, rates)
    _warn_outside_price_dates.cache_clear()
    with warnings.catch_warnings():
        warnings.simplefilter("error", tou.UncheckedPriceWarning)
        plan.calculate_costs(_usage("2020-01-01"))
