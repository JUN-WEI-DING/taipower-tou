"""Bills from an independent calculator, compared with calculate_bill.

The calculator in this file reads nothing from taipower_tou. Its prices, hours,
tiers and basic fees are transcribed from src/taipower_tou/data/詳細電價表.md
(114/10/1), each table with its lines. Its 離峰日 are the 電價表's list (lines
313-325) for 2025-10-01 to 2026-12-31, the days the bundled prices cover, with
the lunar and 清明 dates worked by hand. It is checked against Taipower's
時間電價日曆表 (tests/data/taipower_calendar/) and against the printed totals
of Taipower's worked examples (tests/test_worked_examples.py) before it bills
seeded random months.

Where the 電價表 leaves a reading open, the calculator takes the README's.
The 10% of 超約 is of the contracts each time's excess is over, and the kW
that earlier times already counted are the lowest of that excess (README,
Demand Penalty). 流動電費 is cut to the 角 once (docs/references/README.md,
Open questions). 功率因數 is worked from the cut items, with 按戶計收 left out
(README, Power Factor Adjustment). A 表燈 非時間 or 簡易型 bill with a
three-phase meter is adjusted, since 用電設備容量 is not an input (README,
Rules the package does not apply). A 時間電價 meter reads each 時段 on its own
register, each to the whole kWh (施行細則 第二十八條; README, Complete Bill
Example).

A random bill keeps clear of what the README does not say. A 高壓 month that
straddles 5/16 or 10/15 compares energy alone. A contract below a 功率因數
threshold while the contracts together reach it is raised to the threshold.
The 2,000 kWh 加計流動電費 of 簡易型 may be cut alone or with the rest of
流動電費, so either bill passes. A bill with a 週六半尖峰 or 離峰 contract alone
is compared unrounded, since no one says how its 4.8x and 1.6x amounts are cut.
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_worked_examples import CASES as WORKED
from test_worked_examples import _usage as worked_usage

import taipower_tou as tou

SEASONS = ("summer", "non_summer")
DAYS = ("weekday", "saturday", "offpeak")
FIRST_DAY, LAST_DAY = date(2025, 10, 1), date(2026, 12, 31)

# Lines 313-325: 1/1, 春節 (除夕前1日 to 1月5日), 2/28, 4/4, 清明 (4/4 or 4/5),
# 5/1, 端午, 中秋, 9/28, 10/10, 10/25 and 12/25. 115年 除夕 is 2026-02-16,
# 端午 2026-06-19, 中秋 2025-10-06 and 2026-09-25, 清明 2026-04-05.
OFFPEAK_DAYS = {
    date(2025, 10, 6),
    date(2025, 10, 10),
    date(2025, 10, 25),
    date(2025, 12, 25),
    date(2026, 1, 1),
    *(date(2026, 2, day) for day in range(15, 22)),
    date(2026, 2, 28),
    date(2026, 4, 4),
    date(2026, 4, 5),
    date(2026, 5, 1),
    date(2026, 6, 19),
    date(2026, 9, 25),
    date(2026, 9, 28),
    date(2026, 10, 10),
    date(2026, 10, 25),
    date(2026, 12, 25),
}

ALL_DAY = ("00:00-24:00", "00:00-24:00")
# Rows of (day, period, 夏月 hours, 非夏月 hours). "offpeak" is 週日及離峰日.
SIMPLE_2_HOURS = [  # lines 191-203
    ("weekday", "peak", "09:00-24:00", "06:00-11:00 14:00-24:00"),
    ("weekday", "off_peak", "00:00-09:00", "00:00-06:00 11:00-14:00"),
    ("saturday", "off_peak", *ALL_DAY),
    ("offpeak", "off_peak", *ALL_DAY),
]
SIMPLE_3_HOURS = [  # lines 212-225
    ("weekday", "peak", "16:00-22:00", ""),
    ("weekday", "semi_peak", "09:00-16:00 22:00-24:00", "06:00-11:00 14:00-24:00"),
    ("weekday", "off_peak", "00:00-09:00", "00:00-06:00 11:00-14:00"),
    ("saturday", "off_peak", *ALL_DAY),
    ("offpeak", "off_peak", *ALL_DAY),
]
TWO_STAGE_HOURS = [  # lines 242-264, 546-568, 860-881
    ("weekday", "peak", "09:00-24:00", "06:00-11:00 14:00-24:00"),
    ("weekday", "off_peak", "00:00-09:00", "00:00-06:00 11:00-14:00"),
    ("saturday", "semi_peak", "09:00-24:00", "06:00-11:00 14:00-24:00"),
    ("saturday", "off_peak", "00:00-09:00", "00:00-06:00 11:00-14:00"),
    ("offpeak", "off_peak", *ALL_DAY),
]
THREE_STAGE_HOURS = [  # lines 282-307, 585-614, 896-923
    ("weekday", "peak", "16:00-22:00", ""),
    ("weekday", "semi_peak", "09:00-16:00 22:00-24:00", "06:00-11:00 14:00-24:00"),
    ("weekday", "off_peak", "00:00-09:00", "00:00-06:00 11:00-14:00"),
    ("saturday", "semi_peak", "09:00-24:00", "06:00-11:00 14:00-24:00"),
    ("saturday", "off_peak", "00:00-09:00", "00:00-06:00 11:00-14:00"),
    ("offpeak", "off_peak", *ALL_DAY),
]
EV_HOURS = [  # lines 629-638
    ("weekday", "peak", "16:00-22:00", "15:00-21:00"),
    ("weekday", "off_peak", "00:00-16:00 22:00-24:00", "00:00-15:00 21:00-24:00"),
    ("saturday", "off_peak", *ALL_DAY),
    ("offpeak", "off_peak", *ALL_DAY),
]
BATCH_HOURS = [  # lines 968-981
    ("weekday", "peak", "15:30-21:30", "15:30-21:30"),
    ("weekday", "off_peak", "00:00-15:30 21:30-24:00", "00:00-15:30 21:30-24:00"),
    ("saturday", "semi_peak", "15:30-21:30", "15:30-21:30"),
    ("saturday", "off_peak", "00:00-15:30 21:30-24:00", "00:00-15:30 21:30-24:00"),
    ("offpeak", "off_peak", *ALL_DAY),
]
FLAT_HOURS = [(day, "flat", *ALL_DAY) for day in DAYS]  # line 526

RESIDENTIAL_TIERS = [  # lines 138-144 and 156-162
    (120, "1.78", "1.78"),
    (330, "2.55", "2.26"),
    (500, "3.80", "3.13"),
    (700, "5.14", "4.24"),
    (1000, "6.44", "5.27"),
    (None, "8.86", "7.03"),
]
BUSINESS_TIERS = [  # lines 170-174
    (330, "2.71", "2.28"),
    (700, "3.76", "3.10"),
    (1500, "4.46", "3.61"),
    (3000, "7.08", "5.56"),
    (None, "7.43", "5.83"),
]

# 每瓩每月 (夏月, 非夏月). "weekend" is 週六半尖峰或離峰契約, one price for both.
LOW_CONTRACTS = {  # lines 237-241, 277-281, 523-525, 540-545, 579-584
    "regular": ("236.20", "173.20"),
    "non_summer": ("—", "173.20"),
    "semi_peak": ("173.20", "173.20"),
    "weekend": ("47.20", "34.60"),
}
HIGH_CONTRACTS = {  # lines 856-859, 892-895, 964-967, 高壓供電
    "regular": ("223.60", "166.90"),
    "non_summer": ("—", "166.90"),
    "semi_peak": ("166.90", "166.90"),
    "weekend": ("44.70", "33.30"),
}
EXTRA_HIGH_CONTRACTS = {  # the same lines, 特高壓供電
    "regular": ("217.30", "160.60"),
    "non_summer": ("—", "160.60"),
    "semi_peak": ("160.60", "160.60"),
    "weekend": ("43.40", "32.10"),
}
EV_CONTRACTS = {"regular": ("47.20", "34.60")}  # line 628


@dataclass(frozen=True)
class Plan:
    """One table of the 電價表 and the rules that bill it.

    basic and over_contract name the formula: "two_stage" (經常 and 非夏月
    契約), "three_stage" (經常 and 半尖峰契約), or for over_contract "month",
    the month's highest demand at any time. power_factor names who is adjusted.
    """

    summer: tuple[tuple[int, int], tuple[int, int]]
    power_factor: str
    hours: list = field(default_factory=list)
    prices: str = ""
    tiers: list = field(default_factory=list)
    household: dict = field(default_factory=dict)
    contracts: dict = field(default_factory=dict)
    installed: str | None = None
    basic: str | None = None
    over_contract: str | None = None
    over_2000: str | None = None
    share: str | None = None


LOW_SUMMER = ((6, 1), (9, 30))  # line 137 and each 第三、四章 table
HIGH_SUMMER = ((5, 16), (10, 15))  # lines 854, 890 and 962

# power_factor: "three_phase" lines 461-464 (用電設備容量 not checked),
# "standard" lines 464-465, "low_voltage" lines 729-731, "high_voltage" line 1085.
PLANS = {
    "residential_non_tou": Plan(LOW_SUMMER, "three_phase", tiers=RESIDENTIAL_TIERS),
    "lighting_non_business_tiered": Plan(
        LOW_SUMMER, "three_phase", tiers=RESIDENTIAL_TIERS
    ),
    "lighting_business_tiered": Plan(LOW_SUMMER, "three_phase", tiers=BUSINESS_TIERS),
    "residential_simple_2_tier": Plan(
        LOW_SUMMER,
        "three_phase",
        SIMPLE_2_HOURS,
        "5.16 4.93  2.06 1.99  2.06 1.99  2.06 1.99",
        household={"": "75.00"},
        over_2000="1.04",
    ),
    "residential_simple_3_tier": Plan(
        LOW_SUMMER,
        "three_phase",
        SIMPLE_3_HOURS,
        "7.13 —  4.69 4.48  2.06 1.99  2.06 1.99  2.06 1.99",
        household={"": "75.00"},
        over_2000="1.04",
    ),
    "lighting_standard_2_tier": Plan(
        LOW_SUMMER,
        "standard",
        TWO_STAGE_HOURS,
        "5.54 5.39  2.27 2.15  2.76 2.65  2.27 2.15  2.27 2.15",
        household={"single": "129.10", "three": "262.50"},
        contracts=LOW_CONTRACTS,
        basic="two_stage",
        over_contract="two_stage",
    ),
    "lighting_standard_3_tier": Plan(
        LOW_SUMMER,
        "standard",
        THREE_STAGE_HOURS,
        "8.12 —  5.02 4.86  2.23 2.12  2.50 2.40  2.23 2.12  2.23 2.12",
        household={"single": "129.10", "three": "262.50"},
        contracts=LOW_CONTRACTS,
        basic="three_stage",
        over_contract="three_stage",
    ),
    "low_voltage_power": Plan(
        LOW_SUMMER,
        "low_voltage",
        FLAT_HOURS,
        "4.08 3.87  4.08 3.87  4.08 3.87",
        contracts=LOW_CONTRACTS,
        installed="137.50",
        basic="two_stage",
        over_contract="month",
    ),
    "low_voltage_2_tier": Plan(
        LOW_SUMMER,
        "low_voltage",
        TWO_STAGE_HOURS,
        "5.54 5.39  2.27 2.15  2.76 2.65  2.27 2.15  2.27 2.15",
        household={"installed": "105.00", "demand": "262.50"},
        contracts=LOW_CONTRACTS,
        installed="137.50",
        basic="two_stage",
        over_contract="two_stage",
    ),
    "low_voltage_three_stage": Plan(
        LOW_SUMMER,
        "low_voltage",
        THREE_STAGE_HOURS,
        "8.12 —  5.02 4.86  2.23 2.12  2.50 2.40  2.23 2.12  2.23 2.12",
        household={"demand": "262.50"},
        contracts=LOW_CONTRACTS,
        basic="three_stage",
        over_contract="three_stage",
    ),
    "low_voltage_ev": Plan(
        LOW_SUMMER,
        "low_voltage",
        EV_HOURS,
        "12.47 12.14  3.05 2.90  3.05 2.90  3.05 2.90",
        household={"demand": "262.50"},
        contracts=EV_CONTRACTS,
        basic="two_stage",
        over_contract="month",
    ),
    "high_voltage_2_tier": Plan(
        HIGH_SUMMER,
        "high_voltage",
        TWO_STAGE_HOURS,
        "6.75 6.37  2.71 2.46  2.77 2.54  2.71 2.46  2.71 2.46",
        contracts=HIGH_CONTRACTS,
        basic="two_stage",
        over_contract="two_stage",
    ),
    "high_voltage_three_stage": Plan(
        HIGH_SUMMER,
        "high_voltage",
        THREE_STAGE_HOURS,
        "9.39 —  5.85 5.47  2.53 2.32  2.60 2.41  2.53 2.32  2.53 2.32",
        contracts=HIGH_CONTRACTS,
        basic="three_stage",
        over_contract="three_stage",
    ),
    "high_voltage_batch": Plan(  # lines 1055 and 1126: 比照二段式
        HIGH_SUMMER,
        "high_voltage",
        BATCH_HOURS,
        "12.47 11.79  3.18 2.88  3.26 3.00  3.18 2.88  3.18 2.88",
        contracts=HIGH_CONTRACTS,
        basic="two_stage",
        over_contract="two_stage",
    ),
    "high_voltage_ev": Plan(  # line 983: 第四章 電動車充換電設施電價 95%
        LOW_SUMMER,
        "high_voltage",
        EV_HOURS,
        "12.47 12.14  3.05 2.90  3.05 2.90  3.05 2.90",
        household={"demand": "262.50"},
        contracts=EV_CONTRACTS,
        basic="two_stage",
        over_contract="month",
        share="0.95",
    ),
    "extra_high_voltage_2_tier": Plan(
        HIGH_SUMMER,
        "high_voltage",
        TWO_STAGE_HOURS,
        "6.17 5.79  2.55 2.28  2.73 2.48  2.55 2.28  2.55 2.28",
        contracts=EXTRA_HIGH_CONTRACTS,
        basic="two_stage",
        over_contract="two_stage",
    ),
    "extra_high_voltage_three_stage": Plan(
        HIGH_SUMMER,
        "high_voltage",
        THREE_STAGE_HOURS,
        "8.69 —  5.38 5.03  2.40 2.18  2.50 2.31  2.40 2.18  2.40 2.18",
        contracts=EXTRA_HIGH_CONTRACTS,
        basic="three_stage",
        over_contract="three_stage",
    ),
    "extra_high_voltage_batch": Plan(
        HIGH_SUMMER,
        "high_voltage",
        BATCH_HOURS,
        "11.44 10.80  2.99 2.67  3.20 2.89  2.99 2.67  2.99 2.67",
        contracts=EXTRA_HIGH_CONTRACTS,
        basic="two_stage",
        over_contract="two_stage",
    ),
}


@dataclass(eq=False)
class Case:
    """One bill's usage and the customer's inputs."""

    plan: str
    usage: pd.Series
    contracts: dict = field(default_factory=dict)
    installed_kw: int = 0
    demand: pd.Series | None = None
    power_factor: int | None = None
    meter_phase: str | None = None
    meter: tuple[int, int] | None = None
    months: int = 1

    def inputs(self, rounding):
        voltage, ampere = self.meter or (None, None)
        installed = {"裝置契約": self.installed_kw} if self.installed_kw else {}
        return tou.BillingInputs(
            contract_capacities=dict(self.contracts),
            basic_fee_inputs=installed,
            demand_kw=self.demand,
            power_factor=self.power_factor,
            meter_phase=self.meter_phase,
            meter_voltage_v=voltage,
            meter_ampere=ampere,
            billing_cycle_months=self.months,
            taipower_rounding=rounding,
        )


def _day(day):
    if day.weekday() == 6 or day in OFFPEAK_DAYS:
        return "offpeak"
    return "saturday" if day.weekday() == 5 else "weekday"


def _season(plan, day):
    start, end = plan.summer
    return "summer" if start <= (day.month, day.day) <= end else "non_summer"


def _quarters(spans):
    for span in spans.split():
        start, end = (int(t[:2]) * 4 + int(t[3:]) // 15 for t in span.split("-"))
        yield from range(start, end)


def _table(plan):
    """(season, day, quarter hour) -> (period, price) from a plan's rows."""
    prices = iter(plan.prices.split())
    table = {}
    for day, period, *spans in plan.hours:
        for season, span in zip(SEASONS, spans):
            price = next(prices)
            for quarter in _quarters(span):
                table[season, day, quarter] = (period, price)
    return table


TABLES = {plan_id: _table(plan) for plan_id, plan in PLANS.items() if plan.hours}


def _exact(values):
    """kWh or kW read to the Wh, so float noise does not move a 角."""
    return Fraction(f"{math.fsum(values):.6f}")


def _whole(kwh):
    """施行細則 第二十八條: 有效電度以瓩小時（kWH）...為計量單位，小數點以下四捨五入
    進整."""
    return Fraction(math.floor(kwh + Fraction(1, 2)))


def _cut(amount):
    """施行細則 第二十九條: 應計電費各項均計至角位，分位以下捨棄."""
    return Fraction(math.trunc(amount * 10), 10)


def _yuan(amount):
    """施行細則 第二十九條: 電費總金額...以元為單位，角位四捨五入進整."""
    return Fraction(math.floor(amount + Fraction(1, 2)))


def _bill_days(case):
    first = case.usage.index[0]
    start = date(first.year, first.month, 1)
    end = (pd.Timestamp(start) + pd.DateOffset(months=case.months)).date()
    return [start + timedelta(days=n) for n in range((end - start).days)]


def _tiered(kwh, tiers, column, months):
    """Lines 138-176: each 分段, 加倍 for a two-month bill (lines 145, 347)."""
    cost, low = Fraction(0), 0
    for upper, *prices in tiers:
        high = math.inf if upper is None else upper * months
        if kwh > low:
            cost += (min(kwh, high) - low) * Fraction(prices[column])
        low = high
    return cost


def _minimum_kwh(case):
    """Lines 333-339: 單相低壓電表每安培2度、三相6度, an electricity meter over
    10 A counted as 10 A, per month."""
    if case.meter is None or case.meter_phase is None:
        return 0
    per_ampere = {"single": 2, "three": 6}[case.meter_phase]
    return per_ampere * min(case.meter[1], 10) * case.months


def _layers(plan, contracts, summer):
    """(demand category, contracts it is over, contract price) in the order
    each time leaves out the excess before it (lines 411-445, 744-786,
    1093-1128)."""
    regular, non_summer, semi_peak, saturday, off_peak = (
        contracts.get(name, 0)
        for name in (
            "regular",
            "non_summer",
            "semi_peak",
            "saturday_semi_peak",
            "off_peak",
        )
    )
    if plan.over_contract == "month":
        return [("month", regular + (0 if summer else non_summer), "regular")]
    if plan.over_contract == "three_stage":
        second, second_name = semi_peak, "semi_peak"
        peak = regular
    else:
        second, second_name = non_summer, None
        peak = regular if summer else regular + non_summer
    layers = [("peak", peak, "regular")]
    if second_name:
        layers.append((second_name, regular + second, second_name))
    layers += [
        ("saturday_semi_peak", regular + second + saturday, "weekend"),
        ("off_peak", regular + second + saturday + off_peak, "weekend"),
    ]
    return layers


def _category(plan, day, period):
    if plan.over_contract == "month":
        return "month"
    return (
        "saturday_semi_peak" if (day, period) == ("saturday", "semi_peak") else period
    )


def _price(plan, name, summer):
    return Fraction(plan.contracts[name][0 if summer else 1])


def _basic_fee(plan, case, summer):
    """按戶計收 and the contract part (lines 374-403, 645-711, 1016-1063)."""
    phase = case.meter_phase or "single"
    if case.installed_kw and not case.contracts:
        household = Fraction(plan.household.get("installed", 0))
        return household + Fraction(plan.installed) * case.installed_kw, household
    household = Fraction(
        plan.household.get("demand")
        or plan.household.get(phase)
        or plan.household.get("", 0)
    )
    if plan.basic is None:
        return household, household
    get = case.contracts.get
    second = (
        get("semi_peak", 0) if plan.basic == "three_stage" else get("non_summer", 0)
    )
    fee = _price(plan, "regular", summer) * get("regular", 0)
    if plan.basic == "three_stage":
        fee += _price(plan, "semi_peak", summer) * second
    elif not summer and second:
        fee += _price(plan, "non_summer", summer) * second
    weekend = (
        get("saturday_semi_peak", 0)
        + get("off_peak", 0)
        - Fraction(get("regular", 0) + second, 2)
    )
    if weekend > 0:
        fee += _price(plan, "weekend", summer) * weekend
    return household + fee, household


def _outside(contracts):
    """Times a 週六半尖峰 or 離峰 contract alone does not cover (第八章 二(一)8,
    lines 1575-1578)."""
    if any(contracts.get(name, 0) for name in ("regular", "non_summer", "semi_peak")):
        return set()
    if contracts.get("saturday_semi_peak", 0):
        return {"peak", "semi_peak"}
    if contracts.get("off_peak", 0):
        return {"peak", "semi_peak", "saturday_semi_peak"}
    return set()


def _over_contract_fee(plan, case, summer, highest):
    """Each time's excess, less the largest before it, at its own contract
    price; 2x within 10% of the contracts it is over, 3x above (lines 446-450,
    787-791, 1129-1133). 最高需量 drops its fraction (施行細則 第二十八條). A time
    outside a 週六半尖峰 or 離峰 contract pays 4.8x its price on its highest
    demand instead (lines 487-491, 811-815, 1160-1164)."""
    if plan.over_contract is None or case.demand is None or not case.contracts:
        return Fraction(0)
    fee, largest = Fraction(0), Fraction(0)
    outside = _outside(case.contracts)
    for category, base, name in _layers(plan, case.contracts, summer):
        if category in outside:
            highest_kw = math.floor(highest.get(category, 0))
            fee += Fraction(48, 10) * _price(plan, name, summer) * highest_kw
            continue
        excess = max(Fraction(0), math.floor(highest.get(category, 0)) - base)
        counted = max(Fraction(0), excess - largest)
        within = max(Fraction(0), min(excess, Fraction(base, 10)) - largest)
        fee += _price(plan, name, summer) * (2 * within + 3 * (counted - within))
        largest = max(largest, excess)
    return fee


def _power_factor_applies(plan, case):
    """Who the 電價表 adjusts, as the PLANS comment cites. A month with no kWh
    is not adjusted (施行細則 第三十八條)."""
    three = case.meter_phase == "three"
    if plan.power_factor == "high_voltage":
        return True
    if plan.power_factor == "three_phase":
        return three
    regular = case.contracts.get("regular", 0)
    if plan.power_factor == "standard":
        return three and regular >= 20
    return three and (case.installed_kw >= 20 or regular >= 30)


def _quarter_hours(plan_id, index):
    """Each quarter hour's demand category, price, and register: its 時段,
    with 週六半尖峰 apart from 半尖峰."""
    plan, table = PLANS[plan_id], TABLES[plan_id]
    days = {d: (_season(plan, d), _day(d)) for d in set(index.date)}
    quarters = index.hour * 4 + index.minute // 15
    cells = [(days[d][1], *table[(*days[d], q)]) for d, q in zip(index.date, quarters)]
    categories = np.array([_category(plan, day, period) for day, period, _ in cells])
    registers = np.array(
        [
            "saturday_semi_peak"
            if (day, period) == ("saturday", "semi_peak")
            else period
            for day, period, _ in cells
        ]
    )
    return categories, np.array([price for _, _, price in cells]), registers


@functools.lru_cache(maxsize=8)
def _energy(case, rounding=True):
    """Each demand category's 流動電費, the kWh billed and metered, and each
    category's highest kW. Rounded, each 時段 register of the meter is read to
    the whole kWh, spread over its prices by their kWh (README, Complete Bill
    Example)."""
    plan, kwh = PLANS[case.plan], _exact(case.usage.to_numpy())
    if plan.tiers:
        metered = _whole(kwh) if rounding else kwh
        kwh = max(metered, _minimum_kwh(case))
        days = _bill_days(case)
        cost = Fraction(0)
        for column, season in enumerate(SEASONS):
            share = Fraction(sum(_season(plan, d) == season for d in days), len(days))
            if share:
                cost += share * _tiered(kwh, plan.tiers, column, case.months)
        return {"month": cost}, kwh, metered, {}
    categories, prices, registers = _quarter_hours(case.plan, case.usage.index)
    usage = case.usage.to_numpy()
    scale = dict.fromkeys(set(registers), Fraction(1))
    if rounding:
        kwh = Fraction(0)
        for register in scale:
            read = _exact(usage[registers == register])
            scale[register] = _whole(read) / read if read else Fraction(0)
            kwh += _whole(read)
    costs = dict.fromkeys(set(categories), Fraction(0))
    for category, price, register in set(zip(categories, prices, registers)):
        cell = (categories == category) & (prices == price) & (registers == register)
        costs[category] += Fraction(price) * _exact(usage[cell]) * scale[register]
    if case.demand is None:
        return costs, kwh, kwh, {}
    demand = case.demand.to_numpy()
    highest = {c: _exact([demand[categories == c].max()]) for c in costs}
    return costs, kwh, kwh, highest


def oracle_bill(case, rounding=True, cut_flow_once=False):
    """The bill's items: 流動電費 (energy and 2,000 kWh 加計), 基本電費, the
    adjustments (超約, use outside a 週六半尖峰 or 離峰 contract, 功率因數,
    高壓 電動車 5%) and the total."""
    plan = PLANS[case.plan]
    cut = _cut if rounding else (lambda amount: amount)
    days = _bill_days(case)
    summer = _season(plan, days[0]) == "summer"
    costs, kwh, metered, highest = _energy(case, rounding)
    energy = sum(costs.values())
    over_2000 = (
        max(Fraction(0), kwh - 2000) * Fraction(plan.over_2000)
        if plan.over_2000
        else Fraction(0)
    )
    flow = cut(energy + over_2000) if cut_flow_once else cut(energy) + cut(over_2000)
    basic, household = (Fraction(0), Fraction(0))
    if not plan.tiers:
        basic, household = _basic_fee(plan, case, summer)
    basic = cut(basic)
    over = cut(_over_contract_fee(plan, case, summer, highest))
    outside = sum(costs.get(c, 0) for c in _outside(case.contracts))
    adjustment = over + cut(outside * Fraction(6, 10))
    used = metered > 0
    if case.power_factor is not None and used and _power_factor_applies(plan, case):
        factor = min(case.power_factor, 95)
        base = basic - household + flow + (over if factor < 80 else 0)
        adjustment += cut(base * (80 - factor) / 1000)
    total = flow + basic + adjustment
    if rounding:
        total = _yuan(total)
    if plan.tiers:
        total = max(total, 100 * case.months)
    if plan.share:
        shared = total * Fraction(plan.share)
        shared = _yuan(shared) if rounding else shared
        adjustment += shared - total
        total = shared
    return {
        "流動電費": flow,
        "basic_cost": basic,
        "adjustment": adjustment,
        "total": total,
    }


def _package_items(case, rounding):
    bill = tou.calculate_bill(case.usage, case.plan, case.inputs(rounding)).iloc[0]
    return {
        "流動電費": bill["energy_cost"] + bill["surcharge"],
        "basic_cost": bill["basic_cost"],
        "adjustment": bill["adjustment"],
        "total": bill["total"],
    }


def _differences(expected, actual, rounding):
    tolerance = 1e-6 if rounding else 1e-9
    return {
        item: (float(value), actual[item])
        for item, value in expected.items()
        if actual[item] != pytest.approx(float(value), rel=tolerance, abs=1e-6)
    }


def _readings(case, rounding):
    if rounding and PLANS[case.plan].over_2000:
        return [oracle_bill(case), oracle_bill(case, cut_flow_once=True)]
    return [oracle_bill(case, rounding)]


def test_offpeak_days_are_taipowers():
    """The 電價表's 離峰日 list (lines 313-325), with this file's lunar and
    清明 dates, gives each day of 2025-10 to 2026-12 the day type of Taipower's
    時間電價日曆表."""
    folder = Path(__file__).parent / "data" / "taipower_calendar"
    calendar = pd.concat(
        pd.read_csv(folder / f"{year}.csv", index_col="date")["day_type"]
        for year in (2025, 2026)
    )
    days = pd.date_range(FIRST_DAY, LAST_DAY).date
    ours = {d.isoformat(): _day(d).replace("offpeak", "sunday_holiday") for d in days}
    assert ours == calendar[list(ours)].to_dict()


@pytest.mark.parametrize("plan", sorted(TABLES))
def test_each_table_prices_every_quarter_hour_once(plan):
    """A plan's rows, as transcribed, cover each day of each season once."""
    quarters = sorted(
        quarter
        for day, _, *spans in PLANS[plan].hours
        for span in spans
        for quarter in _quarters(span)
    )
    assert quarters == sorted(list(range(96)) * len(DAYS) * len(SEASONS))


@pytest.mark.parametrize(
    ("plan", "hours", "kwh", "inputs", "total", "equation"),
    [pytest.param(*case.values, id=case.id) for case in WORKED if not case.marks],
)
def test_oracle_bills_the_worked_examples(plan, hours, kwh, inputs, total, equation):
    """This file's calculator gives each printed total of Taipower's
    各類電價表及計算範例 (114/10/1) that tests/test_worked_examples.py bills."""
    usage = worked_usage(hours, kwh)
    contracts = inputs.get("contract_capacities", {})
    case = Case(
        plan,
        usage,
        contracts=contracts,
        installed_kw=inputs.get("basic_fee_inputs", {}).get("裝置契約", 0),
        demand=usage * 4 if contracts else None,
        meter_phase=inputs.get("meter_phase"),
    )
    assert oracle_bill(case)["total"] == total, equation


SEED = 20261028
MONTHS = list(pd.period_range("2025-10", "2026-12", freq="M"))
STRADDLING = {5, 10}
TWO_SEASONS = ["2026-05", "2026-09"]
PF_CHOICES = [None, 60, 72, 79, 80, 81, 88, 95, 96, 100]
CONTRACT_NAMES = (
    "regular",
    "non_summer",
    "semi_peak",
    "saturday_semi_peak",
    "off_peak",
)
LAYER_CONTRACT = {"peak": "regular", "month": "regular", "semi_peak": "semi_peak"}
# Mean kW of a month's load, and whether a 裝置契約 is drawn half the time.
LOADS = {
    "residential_simple_2_tier": (0.2, 4.5, False),
    "residential_simple_3_tier": (0.2, 4.5, False),
    "lighting_standard_2_tier": (2.0, 30.0, False),
    "lighting_standard_3_tier": (2.0, 30.0, False),
    "low_voltage_power": (3.0, 40.0, True),
    "low_voltage_2_tier": (3.0, 40.0, True),
    "low_voltage_three_stage": (3.0, 40.0, False),
    "low_voltage_ev": (3.0, 40.0, False),
    "high_voltage_2_tier": (150.0, 3000.0, False),
    "high_voltage_three_stage": (150.0, 3000.0, False),
    "high_voltage_batch": (150.0, 3000.0, False),
    "high_voltage_ev": (150.0, 3000.0, False),
    "extra_high_voltage_2_tier": (4000.0, 20000.0, False),
    "extra_high_voltage_three_stage": (4000.0, 20000.0, False),
    "extra_high_voltage_batch": (4000.0, 20000.0, False),
}
# Monthly kWh of a tiered bill, drawn log-uniform.
TIERED_KWH = {
    "residential_non_tou": (5, 1600),
    "lighting_non_business_tiered": (5, 1600),
    "lighting_business_tiered": (20, 4200),
}
BILLS_PER_PLAN = 12


def _specs():
    rng = np.random.default_rng(SEED)
    specs = []
    for plan in [*TIERED_KWH, *LOADS]:
        months = [str(m) for m in MONTHS]
        if PLANS[plan].summer == HIGH_SUMMER:
            months = [str(m) for m in MONTHS if m.month not in STRADDLING]
        for _ in range(BILLS_PER_PLAN):
            cycle = int(rng.choice([1, 2])) if plan in TIERED_KWH else 1
            start = months[rng.integers(len(months) - cycle + 1)]
            if cycle == 2 and rng.random() < 0.5:
                start = TWO_SEASONS[rng.integers(len(TWO_SEASONS))]
            seed = len(specs)
            specs.append(
                pytest.param(plan, start, cycle, seed, id=f"{plan}-{start}-{seed}")
            )
    return specs


def _straddling_specs():
    return [
        pytest.param(plan, month, id=f"{plan}-{month}")
        for plan in LOADS
        if PLANS[plan].summer == HIGH_SUMMER
        for month in ("2025-10", "2026-05", "2026-10")
    ]


def _load(rng, index, mean_kw):
    """kW in each quarter hour: a daily shape, a weekend level, and noise."""
    shape = rng.uniform(0.2, 1.0, 24)[index.hour.to_numpy()]
    kinds = np.array([_day(d) for d in index.date])
    weekend = np.where(kinds == "weekday", 1.0, rng.uniform(0.3, 1.5))
    noise = rng.uniform(0.7, 1.3, len(index))
    return mean_kw * shape * weekend * noise / shape.mean()


def _draw_contracts(rng, plan_id, kw, categories, summer):
    """Each time's contracts near that time's highest load, so that any time
    can run over."""
    plan = PLANS[plan_id]
    contracts = dict.fromkeys(CONTRACT_NAMES, 0)
    for category, _, _ in _layers(plan, contracts, summer):
        loads = kw[categories == category]
        if not len(loads) or (category in CONTRACT_NAMES and rng.random() < 0.3):
            continue
        base = {c: b for c, b, _ in _layers(plan, contracts, summer)}[category]
        target = round(loads.max() * rng.uniform(0.8, 1.2))
        contracts[LAYER_CONTRACT.get(category, category)] += max(0, target - base)
    if contracts["regular"] == 0:
        contracts["regular"] = max(
            1, round(contracts["semi_peak"] * rng.uniform(0.4, 1))
        )
        contracts["semi_peak"] = max(0, contracts["semi_peak"] - contracts["regular"])
    if "non_summer" in plan.contracts and plan.basic == "two_stage":
        if rng.random() < 0.4:
            moved = round(contracts["regular"] * rng.uniform(0, 0.4))
            contracts["non_summer"] = moved
            contracts["regular"] -= 0 if summer else moved
            contracts["regular"] = max(1, contracts["regular"])
    low_voltage = plan.power_factor in ("standard", "low_voltage")
    if not low_voltage:
        contracts["regular"] += max(0, 100 - sum(contracts.values()))
    threshold = {"standard": 20, "low_voltage": 30}.get(plan.power_factor, 0)
    if contracts["regular"] < threshold <= sum(contracts.values()):
        contracts["regular"] = threshold
    for name in (
        "off_peak",
        "saturday_semi_peak",
        "non_summer",
        "semi_peak",
        "regular",
    ):
        over = sum(contracts.values()) - 99
        if low_voltage and over > 0:
            contracts[name] = max(int(name == "regular"), contracts[name] - over)
    return contracts


def _spike(rng, plan, kw, categories, contracts, summer):
    """Push one quarter hour of some times near or past their contracts."""
    for category, base, _ in _layers(plan, contracts, summer):
        where = np.flatnonzero(categories == category)
        if base and len(where) and rng.random() < 0.5:
            at = rng.choice(where)
            kw[at] = max(kw[at], base * rng.uniform(0.9, 1.3))
    return kw


def _draw(plan_id, start, cycle, rng):
    plan = PLANS[plan_id]
    begin = pd.Timestamp(start)
    end = begin + pd.DateOffset(months=cycle)
    phase = str(rng.choice(["single", "three"]))
    power_factor = PF_CHOICES[rng.integers(len(PF_CHOICES))]
    if plan.tiers:
        index = pd.date_range(begin, end, freq="D", inclusive="left")
        low, high = TIERED_KWH[plan_id]
        monthly = math.exp(rng.uniform(math.log(low), math.log(high)))
        daily = monthly / 30 * rng.uniform(0.5, 1.5, len(index))
        usage = pd.Series(np.round(daily, 3), index=index)
        meter = None
        if rng.random() < 0.6:
            voltage = int(rng.choice([110, 220] if phase == "single" else [220, 380]))
            meter = (voltage, int(rng.choice([5, 10, 15, 30])))
        return Case(plan_id, usage, {}, 0, None, power_factor, phase, meter, cycle)
    index = pd.date_range(begin, end, freq="15min", inclusive="left")
    low, high, installed = LOADS[plan_id]
    kw = _load(rng, index, rng.uniform(low, high))
    case = Case(plan_id, None, power_factor=power_factor, meter_phase=phase)
    if plan.power_factor == "high_voltage":
        case.meter_phase = None if rng.random() < 0.5 else "three"
    if installed and rng.random() < 0.5:
        case.installed_kw = int(math.ceil(kw.max())) + int(rng.integers(0, 20))
    elif plan.contracts:
        summer = _season(plan, begin.date()) == "summer"
        categories = _quarter_hours(plan_id, index)[0]
        case.contracts = _draw_contracts(rng, plan_id, kw, categories, summer)
        kw = _spike(rng, plan, kw, categories, case.contracts, summer)
    kwh = np.round(kw / 4, 3)
    case.usage = pd.Series(kwh, index=index)
    if (case.contracts or case.installed_kw) and rng.random() < 0.85:
        case.demand = pd.Series(kwh * 4, index=index)
    return case


@pytest.mark.filterwarnings("ignore:Plan .* has minimum usage rules")
@pytest.mark.parametrize(("plan", "start", "cycle", "seed"), _specs())
def test_bill_matches_the_oracle(plan, start, cycle, seed):
    """A seeded random bill, rounded as 施行細則 第二十九條 and unrounded, has
    the items and total this file's calculator works from the 電價表."""
    rng = np.random.default_rng([SEED, seed])
    case = _draw(plan, start, cycle, rng)
    misses = {}
    for rounding in (True, False):
        actual = _package_items(case, rounding)
        found = [_differences(e, actual, rounding) for e in _readings(case, rounding)]
        if all(found):
            misses["rounded" if rounding else "unrounded"] = found[0]
    assert not misses, (case.contracts, case.installed_kw, case.power_factor)


@pytest.mark.parametrize(("plan", "month"), _straddling_specs())
def test_energy_of_a_month_that_straddles_the_high_voltage_summer(plan, month):
    """A 高壓 夏月 runs 5/16 to 10/15 (line 854), so May and October price
    each quarter hour at its own day's season."""
    rng = np.random.default_rng([SEED, int(month.replace("-", ""))])
    case = _draw(plan, month, 1, rng)
    for rounding in (True, False):
        actual = _package_items(case, rounding)["流動電費"]
        expected = oracle_bill(case, rounding)["流動電費"]
        assert actual == pytest.approx(float(expected), abs=1e-6), rounding


LOW_VOLTAGE_METERS = [("single", 110), ("single", 220), ("three", 220), ("three", 380)]


@pytest.mark.parametrize("plan", sorted(TIERED_KWH))
@pytest.mark.parametrize(
    ("phase", "voltage"),
    LOW_VOLTAGE_METERS,
    ids=[f"{p}-{v}V" for p, v in LOW_VOLTAGE_METERS],
)
def test_minimum_usage_of_each_low_voltage_meter(plan, phase, voltage):
    """表燈 is supplied at 單相 110 or 220 V, 三相三線式 220 V or 三相四線式
    220/380 V (lines 125-128). Each low-voltage meter bills at least 2 kWh
    (單相) or 6 kWh (三相) per ampere, 10 A at most (lines 333-339), so 5 kWh
    in January on a 10 A meter bills 20 or 60 kWh."""
    usage = pd.Series(5 / 31, index=pd.date_range("2026-01-01", periods=31, freq="D"))
    case = Case(plan, usage, meter_phase=phase, meter=(voltage, 10))
    actual = _package_items(case, rounding=True)
    assert not _differences(oracle_bill(case), actual, rounding=True)


WEEKEND_ONLY = ("saturday_semi_peak", "off_peak")


def _weekend_specs():
    rng = np.random.default_rng(SEED + 1)
    plans = [
        p for p, v in PLANS.items() if v.over_contract in ("two_stage", "three_stage")
    ]
    specs = []
    for plan in plans:
        months = [str(m) for m in MONTHS]
        if PLANS[plan].summer == HIGH_SUMMER:
            months = [str(m) for m in MONTHS if m.month not in STRADDLING]
        for contract in WEEKEND_ONLY:
            start = months[rng.integers(len(months))]
            seed = len(specs)
            specs.append(
                pytest.param(
                    plan, start, contract, seed, id=f"{plan}-{contract}-{start}"
                )
            )
    return specs


def _draw_weekend_only(plan_id, start, contract, rng):
    """A customer with a 週六半尖峰 or 離峰 contract alone, who still draws a
    little at other times."""
    plan = PLANS[plan_id]
    begin = pd.Timestamp(start)
    end = begin + pd.DateOffset(months=1)
    index = pd.date_range(begin, end, freq="15min", inclusive="left")
    low, high, _ = LOADS[plan_id]
    kw = _load(rng, index, rng.uniform(low, high))
    categories = _quarter_hours(plan_id, index)[0]
    covered = np.isin(categories, WEEKEND_ONLY[WEEKEND_ONLY.index(contract) :])
    kw[~covered] *= rng.uniform(0.05, 0.4)
    contracts = dict.fromkeys(CONTRACT_NAMES, 0)
    contracts[contract] = round(kw[covered].max() * rng.uniform(0.8, 1.2))
    if plan.power_factor == "high_voltage":
        contracts[contract] = max(contracts[contract], 100)
    summer = _season(plan, begin.date()) == "summer"
    kw = _spike(rng, plan, kw, categories, contracts, summer)
    kwh = np.round(kw / 4, 3)
    phase = str(rng.choice(["single", "three"]))
    demand = pd.Series(kwh * 4, index=index)
    usage = pd.Series(kwh, index=index)
    return Case(plan_id, usage, contracts, demand=demand, meter_phase=phase)


@pytest.mark.parametrize(("plan", "start", "contract", "seed"), _weekend_specs())
def test_weekend_only_contract_matches_the_oracle(plan, start, contract, seed):
    """第八章 二(一)8 (lines 1575-1578) lets a customer contract for 週六半尖峰
    or 離峰 time alone. Use at other times pays 4.8x that time's basic fee on
    its highest demand and 1.6x its energy (lines 487-491, 811-815,
    1160-1164), and a 三段式 bill pays 按戶計收 too (README). Neither says how
    those amounts are cut to the 角, so the bill is compared unrounded."""
    case = _draw_weekend_only(
        plan, start, contract, np.random.default_rng([SEED, seed])
    )
    expected = oracle_bill(case, rounding=False)
    actual = _package_items(case, rounding=False)
    expected["流動電費"] += expected.pop("adjustment")
    actual["流動電費"] += actual.pop("adjustment")
    assert not _differences(expected, actual, rounding=False), case.contracts
