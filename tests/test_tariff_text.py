"""Bills at the edges of the 電價表's rules, with amounts worked from its text.

The amounts come from src/taipower_tou/data/詳細電價表.md (114/10/1), not from
plans.json, so a wrong price or limit in plans.json fails here.
"""

from datetime import datetime

import pandas as pd
import pytest

import taipower_tou as tou


def _month(start, end, kwh):
    days = pd.date_range(start, end, freq="D")
    return pd.Series(kwh / len(days), index=days)


def _meter(months=1, phase="single", ampere=10):
    return tou.BillingInputs(
        meter_phase=phase,
        meter_voltage_v=220 if phase == "three" else 110,
        meter_ampere=ampere,
        billing_cycle_months=months,
    )


@pytest.mark.parametrize(
    ("kwh", "expected"),
    [
        (120, 120 * 1.78),
        (121, 120 * 1.78 + 1 * 2.55),
        (330, 120 * 1.78 + 210 * 2.55),
        (331, 120 * 1.78 + 210 * 2.55 + 1 * 3.80),
        (1001, 120 * 1.78 + 210 * 2.55 + 170 * 3.80 + 200 * 5.14 + 300 * 6.44 + 8.86),
    ],
)
def test_residential_tier_limits_in_summer(kwh, expected):
    bill = tou.calculate_bill(
        _month("2026-07-01", "2026-07-31", kwh), "residential_non_tou", _meter()
    )
    assert bill["energy_cost"].iloc[0] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("kwh", "expected"),
    [(240, 240 * 1.78), (241, 240 * 1.78 + 2.26), (660, 240 * 1.78 + 420 * 2.26)],
)
def test_two_month_tier_limits_are_doubled(kwh, expected):
    bill = tou.calculate_bill(
        _month("2026-01-01", "2026-02-28", kwh), "residential_non_tou", _meter(months=2)
    )
    assert bill["energy_cost"].iloc[0] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("start", "end", "second_tier"),
    [("2026-05-01", "2026-05-31", 2.26), ("2026-06-01", "2026-06-30", 2.55)],
    ids=["may-non-summer", "june-summer"],
)
def test_residential_summer_starts_june_1(start, end, second_tier):
    bill = tou.calculate_bill(_month(start, end, 200), "residential_non_tou", _meter())
    assert bill["energy_cost"].iloc[0] == pytest.approx(120 * 1.78 + 80 * second_tier)


@pytest.mark.parametrize(
    ("phase", "ampere", "expected"),
    [
        ("single", 10, 100.0),
        ("single", 11, 100.0),
        ("three", 5, 100.0),
        ("three", 10, 60 * 1.78),
        ("three", 11, 60 * 1.78),
    ],
)
def test_minimum_usage_and_fee_for_an_empty_house(phase, ampere, expected):
    bill = tou.calculate_bill(
        _month("2026-01-01", "2026-01-31", 0),
        "residential_non_tou",
        _meter(phase=phase, ampere=ampere),
    )
    assert bill["total"].iloc[0] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("kwh", "expected"), [(2000, 0.0), (2001, 1.04), (2500, 500 * 1.04)]
)
def test_simple_two_tier_surcharge_above_2000_kwh(kwh, expected):
    hours = pd.date_range("2026-07-01", "2026-07-31 23:00", freq="h")
    usage = pd.Series(kwh / len(hours), index=hours)
    bill = tou.calculate_bill(usage, "residential_simple_2_tier", _meter())
    assert bill["surcharge"].iloc[0] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("when", "period", "rate"),
    [
        (datetime(2026, 7, 15, 8, 0), "off_peak", 2.06),
        (datetime(2026, 7, 15, 9, 0), "peak", 5.16),
        (datetime(2026, 7, 12, 12, 0), "off_peak", 2.06),
        (datetime(2026, 1, 14, 5, 0), "off_peak", 1.99),
        (datetime(2026, 1, 14, 6, 0), "peak", 4.93),
        (datetime(2026, 1, 14, 11, 0), "off_peak", 1.99),
        (datetime(2026, 1, 14, 14, 0), "peak", 4.93),
    ],
    ids=str,
)
def test_simple_two_tier_period_edges(when, period, rate):
    context = tou.plan("residential_simple_2_tier").pricing_context(when)
    assert (context["period"], context["rate"]) == (period, pytest.approx(rate))


@pytest.mark.parametrize(
    ("when", "season", "period", "rate"),
    [
        (datetime(2026, 5, 15, 17, 0), "non_summer", "semi_peak", 5.47),
        (datetime(2026, 5, 18, 17, 0), "summer", "peak", 9.39),
        (datetime(2026, 10, 15, 17, 0), "summer", "peak", 9.39),
        (datetime(2026, 10, 16, 17, 0), "non_summer", "semi_peak", 5.47),
    ],
    ids=str,
)
def test_high_voltage_summer_runs_may_16_to_october_15(when, season, period, rate):
    context = tou.plan("high_voltage_three_stage").pricing_context(when)
    assert (context["season"], context["period"], context["rate"]) == (
        season,
        period,
        pytest.approx(rate),
    )


THREE_STAGE_SEMI_PEAK = {
    "lighting_standard_3_tier": (5.02, 4.86, 2.50, 2.40),
    "low_voltage_three_stage": (5.02, 4.86, 2.50, 2.40),
    "high_voltage_three_stage": (5.85, 5.47, 2.60, 2.41),
    "extra_high_voltage_three_stage": (5.38, 5.03, 2.50, 2.31),
}


@pytest.mark.parametrize("plan", THREE_STAGE_SEMI_PEAK)
def test_three_stage_weekday_and_saturday_semi_peak_prices_differ(plan):
    summer_weekday, non_summer_weekday, summer_saturday, non_summer_saturday = (
        THREE_STAGE_SEMI_PEAK[plan]
    )
    cases = [
        (datetime(2026, 7, 15, 10, 0), summer_weekday),
        (datetime(2026, 1, 14, 7, 0), non_summer_weekday),
        (datetime(2026, 7, 18, 10, 0), summer_saturday),
        (datetime(2026, 1, 17, 7, 0), non_summer_saturday),
    ]
    tariff = tou.plan(plan)
    got = [tariff.pricing_context(when) for when, _ in cases]
    assert [(c["period"], c["rate"]) for c in got] == [
        ("semi_peak", pytest.approx(rate)) for _, rate in cases
    ]
    index = pd.DatetimeIndex(sorted(when for when, _ in cases))
    costs = tariff.calculate_costs(pd.Series(1.0, index=index))
    assert costs.sum() == pytest.approx(sum(rate for _, rate in cases))
