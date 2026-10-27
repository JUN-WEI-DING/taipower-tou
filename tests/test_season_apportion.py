"""Tiered bills that span 夏月 and 非夏月, per Taipower's 請問電費如何計算 FAQ.

The FAQ prices all of a period's kWh at the summer and the non-summer rates,
with tiers doubled for a two-month bill, and weights each total by its share
of the days.
"""

import pandas as pd
import pytest

import taipower_tou as tou
from taipower_tou import BillingCycleType
from taipower_tou.tariff import tiered_energy_cost

SUMMER_350 = 1.78 * 240 + 2.55 * 110
NON_SUMMER_350 = 1.78 * 240 + 2.26 * 110
SEP_OCT_350 = SUMMER_350 * 30 / 61 + NON_SUMMER_350 * 31 / 61
INPUTS = dict(meter_phase="single", meter_voltage_v=110, meter_ampere=10)


def _sep_oct_usage():
    return pd.Series(175.0, index=pd.to_datetime(["2026-09-15", "2026-10-15"]))


def test_faq_example():
    tiers = tou.plan("residential_non_tou").rates.tiered_rates
    shares = {"summer": 18 / 60, "non_summer": 42 / 60}
    expected = SUMMER_350 * 18 / 60 + NON_SUMMER_350 * 42 / 60
    assert tiered_energy_cost(350, tiers, shares, 2) == pytest.approx(expected)


def test_tariff_plan_weights_seasons_by_days():
    plan = tou.plan(
        "residential_non_tou", billing_cycle_type=BillingCycleType.EVEN_MONTH
    )
    assert plan.calculate_costs(_sep_oct_usage()).tolist() == pytest.approx(
        [SEP_OCT_350]
    )


def test_calculate_bill_weights_seasons_by_days():
    bill = tou.calculate_bill(
        _sep_oct_usage(),
        "residential_non_tou",
        inputs=tou.BillingInputs(taipower_rounding=False, **INPUTS),
    )
    assert bill["energy_cost"].tolist() == pytest.approx([SEP_OCT_350])


def test_breakdown_lists_each_season():
    breakdown = tou.calculate_bill_breakdown(
        _sep_oct_usage(),
        "residential_non_tou",
        inputs=tou.BillingInputs(taipower_rounding=False, **INPUTS),
    )
    details = breakdown["details"]
    assert sorted(details["season"]) == ["non_summer", "summer"]
    assert details["energy_cost"].sum() == pytest.approx(SEP_OCT_350)


def test_breakdown_of_tou_usage_across_seasons():
    usage = pd.Series(1.0, index=pd.date_range("2026-05-31", periods=48, freq="h"))
    breakdown = tou.calculate_bill_breakdown(
        usage,
        "residential_simple_2_tier",
        inputs=tou.BillingInputs(taipower_rounding=False, **INPUTS),
    )
    assert set(breakdown["details"]["season"]) == {"non_summer", "summer"}
    assert breakdown["details"]["energy_cost"].sum() == pytest.approx(
        breakdown["summary"]["energy_cost"].sum()
    )
