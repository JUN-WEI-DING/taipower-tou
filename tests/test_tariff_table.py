"""Prices and hours match the 114/10/1 電價表, cell by cell.

tests/data/tariff_114_10_01.json is a transcription of 詳細電價表.md made
without looking at plans.json, with the source line of every number. A
second transcription from 簡要電價表.pdf agreed with it on every cell.
"""

import json
import warnings
from datetime import datetime, timedelta
from importlib.resources import files
from pathlib import Path

import pandas as pd
import pytest

import taipower_tou as tou

TABLE = json.loads(
    (Path(__file__).parent / "data" / "tariff_114_10_01.json").read_text("utf-8")
)

# A weekday, a Saturday and a Sunday in each season, none an off-peak day.
DAYS = {
    ("summer", "weekday"): datetime(2026, 7, 15),
    ("summer", "saturday"): datetime(2026, 7, 18),
    ("summer", "sunday_holiday"): datetime(2026, 7, 19),
    ("non_summer", "weekday"): datetime(2026, 1, 14),
    ("non_summer", "saturday"): datetime(2026, 1, 17),
    ("non_summer", "sunday_holiday"): datetime(2026, 1, 18),
}


def _energy(plan_id):
    entry = TABLE[plan_id]
    derived = entry.get("derived")
    if derived:
        return [
            {**row, "price": row["price"] * derived["share"]}
            for row in _energy(derived["from"])
        ]
    return entry["energy"]


def _expected(plan_id):
    """(season, day_type, minute of day) -> (period, price), every half hour."""
    cells = {}
    for row in _energy(plan_id):
        start = int(row["start"][:2]) * 60 + int(row["start"][3:])
        end = int(row["end"][:2]) * 60 + int(row["end"][3:])
        for minute in range(start, end, 30):
            key = (row["season"], row["day_type"], minute)
            cells[key] = (row["period"], round(row["price"], 4))
    return cells


def _actual(plan_id):
    plan = tou.plan(plan_id)
    cells = {}
    for (season, day_type), day in DAYS.items():
        for minute in range(0, 24 * 60, 30):
            context = plan.pricing_context(day + timedelta(minutes=minute))
            cells[(season, day_type, minute)] = (
                context["period"],
                round(context["rate"], 4),
            )
    return cells


TOU_PLANS = [
    plan for plan in TABLE if TABLE[plan]["energy"] or "derived" in TABLE[plan]
]


@pytest.mark.parametrize("plan_id", TOU_PLANS)
def test_every_half_hour_has_the_tariff_period_and_price(plan_id):
    expected = _expected(plan_id)
    actual = _actual(plan_id)
    wrong = {
        key: (actual[key], cell)
        for key, cell in expected.items()
        if actual[key] != cell
    }
    assert wrong == {}


TIERED_PLANS = [plan for plan in TABLE if TABLE[plan]["tiers"]]
MONTHS = {
    "summer": ("2026-07-01", "2026-07-31"),
    "non_summer": ("2026-01-01", "2026-01-31"),
}


def _tier_cost(tiers, kwh):
    cost = 0.0
    for tier in tiers:
        top = tier["to_kwh"] if tier["to_kwh"] is not None else float("inf")
        cost += max(0.0, min(kwh, top) - (tier["from_kwh"] - 1)) * tier["price"]
    return cost


@pytest.mark.parametrize("season", MONTHS)
@pytest.mark.parametrize("plan_id", TIERED_PLANS)
def test_tier_limits_and_prices(plan_id, season):
    tiers = [tier for tier in TABLE[plan_id]["tiers"] if tier["season"] == season]
    start, end = MONTHS[season]
    days = pd.date_range(start, end, freq="D")
    inputs = tou.BillingInputs(
        meter_phase="single",
        meter_voltage_v=110,
        meter_ampere=10,
        billing_cycle_months=1,
    )
    for tier in tiers:
        for kwh in {tier["from_kwh"] + 199, tier["to_kwh"] or tier["from_kwh"] + 500}:
            usage = pd.Series(kwh / len(days), index=days)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                bill = tou.calculate_bill(usage, plan_id, inputs).iloc[0]
            assert bill["energy_cost"] == pytest.approx(_tier_cost(tiers, kwh)), kwh


def _plan_data(plan_id):
    plans = json.loads(
        files("taipower_tou.data").joinpath("plans.json").read_text("utf-8")
    )["plans"]
    return next(plan for plan in plans if plan["id"] == plan_id)


def _fee_prices(fees, share=1.0):
    prices = set()
    for fee in fees:
        for season in ("summer", "non_summer"):
            if fee.get("season", season) in (season, "all"):
                prices.add((season, round(fee["price"] * share, 4)))
    return prices


def _plans_json_fee_prices(plan_id):
    prices = set()
    data = _plan_data(plan_id)
    for fee in data.get("basic_fees", []):
        for season in ("summer", "non_summer"):
            value = fee.get(season, fee.get("cost"))
            if value is not None:
                prices.add((season, round(value, 4)))
    if data.get("basic_fee") is not None:
        prices |= {(season, round(data["basic_fee"], 4)) for season in MONTHS}
    return prices


FEE_PLANS = [
    plan for plan in TABLE if TABLE[plan]["basic_fees"] or "derived" in TABLE[plan]
]


@pytest.mark.parametrize("plan_id", FEE_PLANS)
def test_basic_fee_prices(plan_id):
    entry = TABLE[plan_id]
    derived = entry.get("derived")
    expected = (
        _fee_prices(TABLE[derived["from"]]["basic_fees"], derived["share"])
        if derived
        else _fee_prices(entry["basic_fees"])
    )
    assert sorted(_plans_json_fee_prices(plan_id)) == sorted(expected)


# The 電價表 has no 高壓 or 特高壓 非時間電價 (第五章 四), and 高壓 users have
# all been on 時間電價 since 1989. 0.1.0 had these ids as copies of 二段式.
REMOVED = {
    "high_voltage_power": "high_voltage_2_tier",
    "extra_high_voltage_power": "extra_high_voltage_2_tier",
    "高壓電力": "high_voltage_2_tier",
    "特高壓電力": "extra_high_voltage_2_tier",
}


@pytest.mark.parametrize(("plan_id", "replacement"), REMOVED.items())
def test_removed_non_tou_high_voltage_plans_name_their_replacement(
    plan_id, replacement
):
    assert plan_id not in tou.available_plans()
    with pytest.raises(KeyError, match=replacement):
        tou.plan(plan_id)
