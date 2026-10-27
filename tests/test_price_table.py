"""plans.json agrees with the 電價表 text it was transcribed from."""

import json
import re
from importlib.resources import files

import pytest

PLANS = json.loads(
    files("taipower_tou.data").joinpath("plans.json").read_text("utf-8")
)["plans"]
TEXT = files("taipower_tou.data").joinpath("詳細電價表.md").read_text("utf-8")
TEXT_NUMBERS = set(re.findall(r"\d+\.\d\d", re.sub(r"(\d),(\d{3})", r"\1\2", TEXT)))
PRICE_KEYS = {
    "cost",
    "summer_cost",
    "non_summer_cost",
    "summer",
    "non_summer",
    "cost_per_kwh",
}

# 電價表 第五章 四(四): 高壓電動車充換電設施電價按第四章第四條第(三)款 95% 計算.
SHARE_OF_LISTED_PRICE = {"high_voltage_ev": 0.95}


def _prices(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in PRICE_KEYS and isinstance(value, (int, float)):
                yield f"{path}.{key}", value
            else:
                yield from _prices(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _prices(value, f"{path}[{i}]")


def _day_types(schedule):
    return (
        [schedule["day_type"]]
        if "day_type" in schedule
        else ["weekday", "saturday", "sunday_holiday"]
    )


def _scheduled_periods(plan):
    periods = set()
    for schedule in plan.get("schedules", []):
        slots = schedule.get("slots", [schedule])
        for day_type in _day_types(schedule):
            periods.update(
                (schedule["season"], day_type, slot["period"]) for slot in slots
            )
    return periods


def _priced(rate):
    """A rate without a day_type prices its period on every day type."""
    return (rate["season"], rate.get("day_type"), rate["period"])


def _has_price(prices, season, day_type, period):
    return {(season, day_type, period), (season, None, period)} & prices != set()


@pytest.mark.parametrize("plan", PLANS, ids=lambda plan: plan["id"])
def test_every_price_is_in_the_tariff_text(plan):
    share = SHARE_OF_LISTED_PRICE.get(plan["id"], 1.0)
    missing = [
        (path, value)
        for path, value in _prices(plan)
        if f"{value / share:.2f}" not in TEXT_NUMBERS
    ]
    assert missing == []


TOU_PLANS = [plan for plan in PLANS if plan.get("schedules")]


@pytest.mark.parametrize("plan", TOU_PLANS, ids=lambda plan: plan["id"])
def test_every_scheduled_period_has_a_price(plan):
    prices = {_priced(rate) for rate in plan["rates"]}
    unpriced = [p for p in _scheduled_periods(plan) if not _has_price(prices, *p)]
    assert sorted(unpriced) == []


@pytest.mark.parametrize("plan", TOU_PLANS, ids=lambda plan: plan["id"])
def test_every_price_is_for_a_scheduled_period(plan):
    scheduled = _scheduled_periods(plan)
    unused = [
        _priced(rate)
        for rate in plan["rates"]
        if not any(
            (season, period) == (rate["season"], rate["period"])
            and rate.get("day_type") in (None, day_type)
            for season, day_type, period in scheduled
        )
    ]
    assert unused == []
