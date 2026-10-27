"""Relations between bills that hold without knowing the right amount.

Each test computes one bill two ways that must agree, so it catches a wrong
rule on either side without a hand-computed answer.
"""

import numpy as np
import pandas as pd
import pytest

import taipower_tou as tou
from taipower_tou import BillingCycleType

TIERED = [
    "residential_non_tou",
    "lighting_non_business_tiered",
    "lighting_business_tiered",
]
TOU = [plan for plan in tou.available_plans() if plan not in TIERED]


def _daily(start, end, kwh_per_month):
    """Daily usage that adds up to kwh_per_month in every calendar month."""
    days = pd.date_range(start, end, freq="D")
    month_days = days.to_series().groupby(days.to_period("M")).transform("size")
    return pd.Series(kwh_per_month / month_days.to_numpy(), index=days)


def _hourly(start, end, seed=0):
    hours = pd.date_range(start, end, freq="h")
    rng = np.random.default_rng(seed)
    return pd.Series(rng.uniform(1.0, 5.0, len(hours)), index=hours)


def _meter(months=None, ampere=30):
    return tou.BillingInputs(
        taipower_rounding=False,
        meter_phase="single",
        meter_voltage_v=110,
        meter_ampere=ampere,
        billing_cycle_months=months,
        contract_capacity_kw=500,
    )


@pytest.mark.parametrize("kwh_per_month", [0, 15, 300, 800])
@pytest.mark.parametrize(
    ("start", "end"),
    [("2026-01-01", "2026-02-28"), ("2026-07-01", "2026-08-31")],
    ids=["non-summer", "summer"],
)
@pytest.mark.parametrize("plan", TIERED)
def test_two_month_bill_equals_two_one_month_bills(plan, start, end, kwh_per_month):
    """Doubled tiers, 底度 and the minimum fee all scale with the months."""
    usage = _daily(start, end, kwh_per_month)
    two = tou.calculate_bill(usage, plan, _meter(2))["total"].sum()
    one = tou.calculate_bill(usage, plan, _meter(1))["total"].sum()
    assert two == pytest.approx(one)


@pytest.mark.parametrize(
    ("start", "end", "cycle"),
    [
        ("2026-02-01", "2026-03-31", BillingCycleType.ODD_MONTH),
        ("2026-05-01", "2026-06-30", BillingCycleType.EVEN_MONTH),
        ("2026-09-01", "2026-10-31", BillingCycleType.EVEN_MONTH),
    ],
    ids=["non-summer", "into-summer", "out-of-summer"],
)
@pytest.mark.parametrize("plan", TIERED)
def test_bill_energy_matches_plan_costs_for_tiered_plans(plan, start, end, cycle):
    usage = _daily(start, end, 400)
    bill = tou.calculate_bill(usage, plan, _meter(2))["energy_cost"].sum()
    costs = tou.plan(plan, billing_cycle_type=cycle).calculate_costs(usage).sum()
    assert bill == pytest.approx(costs)


@pytest.mark.parametrize("plan", TOU)
def test_bill_energy_matches_plan_costs_for_tou_plans(plan):
    usage = _hourly("2026-05-01", "2026-06-30 23:00")
    bill = tou.calculate_bill(usage, plan, _meter())["energy_cost"]
    costs = tou.plan(plan).calculate_costs(usage)
    assert bill.to_numpy() == pytest.approx(costs.to_numpy())


@pytest.mark.parametrize("plan", TIERED + TOU)
def test_breakdown_details_add_up_to_summary(plan):
    usage = _hourly("2026-05-01", "2026-06-30 23:00")
    breakdown = tou.calculate_bill_breakdown(usage, plan, _meter())
    details = breakdown["details"]["energy_cost"].sum()
    assert details == pytest.approx(breakdown["summary"]["energy_cost"].sum())
    assert breakdown["details"]["usage_kwh"].sum() == pytest.approx(usage.sum())


@pytest.mark.parametrize("plan", TOU)
def test_quarter_hour_and_half_hour_usage_cost_the_same(plan):
    """Every period boundary in plans.json is on the hour or the half hour."""
    quarters = pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min")
    rng = np.random.default_rng(0)
    quarter = pd.Series(rng.uniform(0.0, 2.0, len(quarters)), index=quarters)
    half = quarter.resample("30min").sum()
    pd.testing.assert_series_equal(
        tou.plan(plan).calculate_costs(quarter), tou.plan(plan).calculate_costs(half)
    )


@pytest.mark.parametrize("plan", TOU)
def test_moving_usage_to_night_never_costs_more(plan):
    usage = _hourly("2026-07-06", "2026-07-06 23:00")
    night = usage.copy()
    for hour in range(8, 22):
        night.iloc[hour] -= 1.0
        night.iloc[hour % 6] += 1.0
    plan_ = tou.plan(plan)
    assert (
        plan_.calculate_costs(night).sum() <= plan_.calculate_costs(usage).sum() + 1e-9
    )


@pytest.mark.parametrize("plan", TIERED)
def test_more_usage_never_costs_less(plan):
    totals = [
        tou.calculate_bill(_daily("2026-01-01", "2026-02-28", kwh), plan, _meter(2))[
            "total"
        ].sum()
        for kwh in range(0, 1201, 25)
    ]
    assert all(later >= earlier for earlier, later in zip(totals, totals[1:]))
    assert totals[-1] > totals[len(totals) // 2] > totals[0]
