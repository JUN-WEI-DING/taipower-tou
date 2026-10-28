"""The demand side of a bill, replayed along the paths of the demand statechart.

Each test is one path of the chart: a contract, each time's highest demand,
then the 基本電費 and the 超約 that calculate_bill_breakdown bills, with Taipower
rounding. Amounts are worked from src/taipower_tou/data/詳細電價表.md
(114/10/1). 高壓: 二段式 prices lines 850-859 and 三段式 888-895, 夏月 5月16日至
10月15日 (lines 854-855), 基本電費 五(一) lines 1014-1052, 超約 七(一) lines
1093-1125 and 七(二) lines 1129-1133. 低壓 二段式: prices lines 530-546, 夏月
6月1日至9月30日 (lines 532-533), 超約 七(二) lines 742-791. 施行細則 第二十九條
cuts each item to the 角 (docs/references/營業規章施行細則第四章.txt).

The 10% of 超約 is of the contracts each time's excess is over, and the kW
earlier times already counted are the lowest of that excess (README, Demand
Penalty). A 高壓 month over 5/16 or 10/16 bills each season's part by its
share of the month's days, each part on its own highest demand (README,
Demand Penalty). Both are the package's readings where the 電價表 is silent.

Every bill has the contracts 經常 100 kW, 非夏月 (二段式) or 半尖峰 (三段式) 20
kW, 週六半尖峰 60 kW and 離峰 40 kW, so 超約 is over 經常 at 尖峰 (經常 + 非夏月
at 非夏月 尖峰), 120 kW at 半尖峰, 180 kW at 週六半尖峰 and 220 kW at 離峰. Demand
is 10 kW except at the readings a case lists.
"""

import math

import pandas as pd
import pytest

import taipower_tou as tou

CONTRACTS = {
    "high_voltage_2_tier": {"non_summer": 20},
    "low_voltage_2_tier": {"non_summer": 20},
    "high_voltage_three_stage": {"semi_peak": 20},
}
MONTH = {
    "july": pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min"),
    "may": pd.date_range("2026-05-01", "2026-05-31 23:45", freq="15min"),
    "october": pd.date_range("2026-10-01", "2026-10-31 23:45", freq="15min"),
}
# Weekdays and Saturdays that are not 離峰日 (lines 313-325).
PEAK = "2026-07-15 17:00"
SEMI_PEAK = "2026-07-15 10:00"
SATURDAY = "2026-07-18 17:00"
OFF_PEAK = "2026-07-15 03:00"
MAY_NON_SUMMER = "2026-05-12 17:00"
MAY_SUMMER = "2026-05-20 17:00"


def _jiao(amount):
    """第二十九條: 應計電費各項均計至角位，分位以下捨棄."""
    return pytest.approx(math.floor(round(amount * 10, 6)) / 10, abs=1e-6)


def _demand(index, readings):
    demand = pd.Series(10.0, index=index)
    for when, kw in readings.items():
        demand[pd.Timestamp(when)] = kw
    return demand


def _breakdown(plan, month, readings):
    index = MONTH[month]
    contracts = {
        "regular": 100,
        **CONTRACTS[plan],
        "saturday_semi_peak": 60,
        "off_peak": 40,
    }
    inputs = tou.BillingInputs(
        contract_capacities=contracts, demand_kw=_demand(index, readings)
    )
    return tou.calculate_bill_breakdown(pd.Series(0.1, index=index), plan, inputs)


# plan, readings, each billed time as (its contract's price, kW at 2x, kW at
# 3x), and the 基本電費.
LAYERED = {
    "peak-within-then-saturday-beyond": (
        "high_voltage_2_tier",
        {PEAK: 105, SATURDAY: 210},
        [(223.60, 5, 0), (44.70, 13, 12)],
        223.60 * 100 + 44.70 * 40,
    ),
    "low-voltage-peak-within-then-saturday-beyond": (
        "low_voltage_2_tier",
        {PEAK: 105, SATURDAY: 210},
        [(236.20, 5, 0), (47.20, 13, 12)],
        262.50 + 236.20 * 100 + 47.20 * 40,
    ),
    "peak-beyond-counts-the-later-excess": (
        "high_voltage_2_tier",
        {PEAK: 130, SATURDAY: 200, OFF_PEAK: 240},
        [(223.60, 10, 20)],
        223.60 * 100 + 44.70 * 40,
    ),
    "off-peak-leaves-out-the-larger-earlier-excess": (
        "high_voltage_2_tier",
        {PEAK: 105, SATURDAY: 190, OFF_PEAK: 250},
        [(223.60, 5, 0), (44.70, 5, 0), (44.70, 12, 8)],
        223.60 * 100 + 44.70 * 40,
    ),
    "three-stage-every-time": (
        "high_voltage_three_stage",
        {PEAK: 105, SEMI_PEAK: 150, SATURDAY: 200, OFF_PEAK: 260},
        [(223.60, 5, 0), (166.90, 7, 18), (44.70, 0, 10)],
        223.60 * 100 + 166.90 * 20 + 44.70 * 40,
    ),
}


@pytest.mark.parametrize("case", LAYERED)
def test_each_time_pays_its_excess_beyond_the_times_before_it(case):
    """七(一)1(5), 2(5): 各時間之超約用電，其超出部分不重複計算, so a time leaves
    out the largest excess before it. 七(二): each time's kW at 2x its own
    契約電價 up to 10% of the contracts it is over, less the kW earlier times
    counted, and 3x above. 105 kW at 尖峰 is 5 kW over 100, and 210 kW on a
    Saturday is 30 over 180, 25 after the 5, of which 18 - 5 = 13 are within
    10%. 五(一): the 夏月 基本電費 leaves out 非夏月契約 but its 週六半尖峰 term is
    (60 + 40) - (100 + 20) x 0.5 = 40 kW. A 低壓 需量 bill adds 按戶計收 262.50."""
    plan, readings, times, basic = LAYERED[case]
    bill = _breakdown(plan, "july", readings)["summary"].iloc[0]
    over = sum(price * (2 * low + 3 * high) for price, low, high in times)
    assert bill["basic_cost"] == _jiao(basic)
    assert bill["adjustment"] == _jiao(over)


# Each season's part: its season, days, 基本電費 and 超約 for a whole month.
NON_SUMMER_2_TIER = 166.90 * 100 + 166.90 * 20 + 33.30 * 40
SUMMER_2_TIER = 223.60 * 100 + 44.70 * 40
SPLIT = {
    "two-stage-may": (
        "high_voltage_2_tier",
        "may",
        {MAY_NON_SUMMER: 150, MAY_SUMMER: 105},
        [
            ("non_summer", 15, NON_SUMMER_2_TIER, 166.90 * (2 * 12 + 3 * 18)),
            ("summer", 16, SUMMER_2_TIER, 223.60 * 2 * 5),
        ],
    ),
    "three-stage-may": (
        "high_voltage_three_stage",
        "may",
        {MAY_NON_SUMMER: 150, MAY_SUMMER: 130},
        [
            (
                "non_summer",
                15,
                166.90 * 100 + 166.90 * 20 + 33.30 * 40,
                166.90 * (2 * 12 + 3 * 18),
            ),
            (
                "summer",
                16,
                223.60 * 100 + 166.90 * 20 + 44.70 * 40,
                223.60 * (2 * 10 + 3 * 20),
            ),
        ],
    ),
    "two-stage-october": (
        "high_voltage_2_tier",
        "october",
        {"2026-10-14 17:00": 130, "2026-10-21 17:00": 125},
        [
            ("summer", 15, SUMMER_2_TIER, 223.60 * (2 * 10 + 3 * 20)),
            ("non_summer", 16, NON_SUMMER_2_TIER, 166.90 * 2 * 5),
        ],
    ),
}


@pytest.mark.parametrize("case", SPLIT)
def test_a_high_voltage_month_over_the_season_edge_bills_each_part(case):
    """夏月 runs 5月16日至10月15日, so May has 15 days of 非夏月 and 16 of 夏月 and
    October 15 of 夏月 and 16 of 非夏月. Each part pays its season's 基本電費 and
    its own 超約 at its season's contracts and prices, by its share of the
    31 days, as the README reads it. 150 kW at 尖峰 on 5/12 is 30 over 經常 +
    非夏月 at 166.90, 12 within 10% of 120 at 2x and 18 at 3x. 三段式 has no
    非夏月 尖峰, so 5/12 17:00 is 半尖峰, over 經常 + 半尖峰. 125 kW on 10/21 is 5
    over 120."""
    plan, month, readings, parts = SPLIT[case]
    breakdown = _breakdown(plan, month, readings)
    bill = breakdown["summary"].iloc[0]
    basic = sum(days * fee for _, days, fee, _ in parts) / 31
    over = sum(days * fee for _, days, _, fee in parts) / 31
    shares = breakdown["basic_details"].groupby("season")["share"].first()
    assert shares.to_dict() == pytest.approx(
        {season: days / 31 for season, days, _, _ in parts}
    )
    assert bill["basic_cost"] == _jiao(basic)
    assert bill["adjustment"] == _jiao(over)


def test_a_low_voltage_may_is_one_non_summer_month():
    """低壓 夏月 runs 6月1日至9月30日 (lines 532-533), so all of May is 非夏月. 150
    kW at 尖峰 on 5/12 is 30 kW over 經常 + 非夏月 (第四章 七(二)1(2)b), 12
    within 10% at 2x and 18 at 3x of 173.20. 105 kW on 5/20, which a 高壓 bill
    reads in 夏月, is under 120 kW here."""
    breakdown = _breakdown(
        "low_voltage_2_tier", "may", {MAY_NON_SUMMER: 150, MAY_SUMMER: 105}
    )
    bill = breakdown["summary"].iloc[0]
    basic = 262.50 + 173.20 * 100 + 173.20 * 20 + 34.60 * 40
    assert set(breakdown["basic_details"]["season"]) == {"non_summer"}
    assert bill["basic_cost"] == _jiao(basic)
    assert bill["adjustment"] == _jiao(173.20 * (2 * 12 + 3 * 18))


JUNE = pd.date_range("2026-06-01", "2026-06-30 23:45", freq="15min")


@pytest.mark.xfail(
    strict=True,
    reason="not supported: BillingInputs takes one contract_capacities for all "
    "the usage, and a bill of part of a month is not one Taipower bill",
)
@pytest.mark.parametrize(
    ("before_kw", "after_kw", "over"),
    [
        (105, 155, 15 / 30 * 223.60 * 2 * 5 + 15 / 30 * 223.60 * 2 * 5),
        (130, 140, 15 / 30 * 223.60 * (2 * 10 + 3 * 30)),
    ],
    ids=["both-within-10-percent", "10-percent-or-more-takes-the-larger-demand"],
)
def test_a_contract_raised_mid_month_is_billed_by_days(before_kw, after_kw, over):
    """營業規章 第二十七條: 用戶於月中變更用電時，基本電費...依變更前後按實際使用
    日數照核定電價每日以三十分之一計算, and 超約 依變更前、後超約用電量. 但...其前或
    後用電之超約容量在契約容量百分之十以上者...應依增設或減少契約容量前、後用電最高
    需量較大者為準，分別計算變更前後超約用電容量. 施行細則 第四十六條三 sends a
    月中增設 to this article, and 第三十七條 counts the days before the change
    first. 經常契約 100 kW to 6/15 and 150 kW from 6/16 is 15/30 of a month at
    each, in 夏月. 30 kW over 100 on 6/10 is 10% or more, so both parts take
    140 kW, 40 over 100 before and none over 150 after.

    The README names no input for a contract that changes, so a caller can
    only bill each part on its own. Each part bill warns and is billed as a
    whole month (README, Billing Periods Are Calendar Months)."""
    before = {
        "regular": 100,
        "non_summer": 20,
        "saturday_semi_peak": 60,
        "off_peak": 40,
    }
    readings = {"2026-06-10 17:00": before_kw, "2026-06-24 17:00": after_kw}
    demand = _demand(JUNE, readings)
    total = {"basic_cost": 0.0, "adjustment": 0.0}
    for contracts, days in (
        (before, JUNE.day <= 15),
        ({**before, "regular": 150}, JUNE.day > 15),
    ):
        inputs = tou.BillingInputs(
            contract_capacities=contracts, demand_kw=demand[days]
        )
        with pytest.warns(tou.PartialPeriodWarning):
            bill = tou.calculate_bill(
                pd.Series(0.1, index=JUNE[days]), "high_voltage_2_tier", inputs
            ).iloc[0]
        total = {key: total[key] + bill[key] for key in total}
    basic = 15 / 30 * (223.60 * 100 + 44.70 * 40) + 15 / 30 * (
        223.60 * 150 + 44.70 * 15
    )
    assert total == {"basic_cost": _jiao(basic), "adjustment": _jiao(over)}
