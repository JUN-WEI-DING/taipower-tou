"""Properties every plan's bill keeps, on seeded random usage, demand and
inputs.

Each property comes from a rule, not from a bill worked by hand: the 電價表
(src/taipower_tou/data/詳細電價表.md, 114/10/1), 營業規章施行細則 第四章
(docs/references/營業規章施行細則第四章.txt), the README and the 0.2.0
CHANGELOG. The sample is hourly from 12 May to 4 June 2026. It crosses the
5/16 高壓 and 6/1 低壓 夏月 starts and bills parts of two months.
"""

from __future__ import annotations

import warnings
import zlib
from datetime import timedelta, timezone
from functools import cache
from typing import NamedTuple

import numpy as np
import pandas as pd
import pytest

import taipower_tou as tou

SEED = 20261028
HOURS = pd.date_range("2026-05-12", "2026-06-04 23:00", freq="h")
JULY = pd.date_range("2026-07-01", "2026-07-31 23:00", freq="h")
# A week of quarter hours with a Saturday, a Sunday and 端午 on Friday 6/19.
WEEK = pd.date_range("2026-06-15", "2026-06-21 23:45", freq="15min")
# Wednesday 2026-06-17 17:15 is 夏月 尖峰 on every time-of-use plan: 09:00-24:00
# (二段式), 16:00-22:00 (三段式, 電動車), 15:30-21:30 (批次, line 968).
PEAK_QUARTER = pd.Timestamp("2026-06-17 17:15")
TAIWAN = timezone(timedelta(hours=8))
TWO = ("regular", "non_summer", "saturday_semi_peak", "off_peak")
THREE = ("regular", "semi_peak", "saturday_semi_peak", "off_peak")


class Plan(NamedTuple):
    size_kw: float
    contracts: tuple = ()
    # 按戶計收 per month, which 功率因數 leaves out (電價表 line 357).
    household: float = 0.0
    # 夏月經常契約 per kW, the rate of 超約. None for a plan with no 超約.
    regular_summer: float | None = None
    # 高壓 電動車 is 95% of the 低壓 電動車 bill (line 983).
    ratio: float = 1.0
    tiered: bool = False
    # 批次 periods change at 15:30 and 21:30 (line 968).
    whole_hours: bool = True


# 電價表 lines: 簡易型 189 and 210, 標準型 236-237 and 276-277, 低壓電力 523,
# 538-540, 578-579 and 627-628, 高壓 and 特高壓 856, 892 and 964.
PLANS = {
    "residential_non_tou": Plan(6, tiered=True),
    "lighting_non_business_tiered": Plan(6, tiered=True),
    "lighting_business_tiered": Plan(6, tiered=True),
    "residential_simple_2_tier": Plan(6, household=75.0),
    "residential_simple_3_tier": Plan(6, household=75.0),
    "lighting_standard_2_tier": Plan(40, TWO, 262.5, 236.2),
    "lighting_standard_3_tier": Plan(40, THREE, 262.5, 236.2),
    "low_voltage_power": Plan(40, ("regular", "non_summer"), 0.0, 236.2),
    "low_voltage_2_tier": Plan(40, TWO, 262.5, 236.2),
    "low_voltage_three_stage": Plan(40, THREE, 262.5, 236.2),
    "low_voltage_ev": Plan(40, ("regular",), 262.5, 47.2),
    "high_voltage_2_tier": Plan(300, TWO, 0.0, 223.6),
    "high_voltage_three_stage": Plan(300, THREE, 0.0, 223.6),
    "high_voltage_batch": Plan(300, TWO, 0.0, 223.6, whole_hours=False),
    "high_voltage_ev": Plan(300, ("regular",), 262.5, 47.2, ratio=0.95),
    "extra_high_voltage_2_tier": Plan(300, TWO, 0.0, 217.3),
    "extra_high_voltage_three_stage": Plan(300, THREE, 0.0, 217.3),
    "extra_high_voltage_batch": Plan(300, TWO, 0.0, 217.3, whole_hours=False),
}
CONTRACT_SHARES = {
    "regular": (0.8, 1.2),
    "non_summer": (0.0, 0.3),
    "semi_peak": (0.0, 0.3),
    "saturday_semi_peak": (0.0, 0.8),
    "off_peak": (0.0, 0.8),
}
ITEMS = ["energy_cost", "basic_cost", "surcharge", "adjustment"]
OVER_CONTRACT = [name for name, plan in PLANS.items() if plan.regular_summer]
TIME_OF_USE = [name for name, plan in PLANS.items() if not plan.tiered]
TIERED = [name for name, plan in PLANS.items() if plan.tiered]
CONTRACTS = [(name, key) for name, plan in PLANS.items() for key in plan.contracts]
VARIANTS = pytest.mark.parametrize(
    ("variant", "rounding"),
    [("busy", True), ("busy", False), ("idle_june", True)],
    ids=["rounded", "unrounded", "idle_june"],
)
ROUNDING = pytest.mark.parametrize(
    "rounding", [True, False], ids=["rounded", "unrounded"]
)


def _rng(*salt):
    return np.random.default_rng([SEED, *(zlib.crc32(str(s).encode()) for s in salt)])


@cache
def _sample(name, variant="busy", quarter_hours=False):
    """Usage, demand and BillingInputs keywords for one plan.

    Every bill is three-phase with contracts of 32 kW or more, one the 電價表
    adjusts for 功率因數 (lines 461, 729 and 1085). idle_june has no kWh and
    no demand in June.
    """
    plan = PLANS[name]
    index = WEEK if quarter_hours else HOURS
    rng = _rng(name, len(index))
    hours = (index[1] - index[0]) / pd.Timedelta("1h")
    kw = plan.size_kw * rng.uniform(0.0, 1.1, len(index))
    kw[rng.random(len(index)) < 0.05] = 0.0
    if variant == "idle_june":
        kw[index.month == 6] = 0.0
    usage = pd.Series(kw * hours, index=index)
    demand = pd.Series(kw * rng.uniform(1.0, 1.15, len(index)), index=index)
    inputs = {
        "meter_phase": "three",
        "meter_voltage_v": 220,
        "meter_ampere": 30,
        "power_factor": float(rng.integers(60, 101)),
    }
    if plan.contracts:
        inputs["contract_capacities"] = {
            key: float(round(plan.size_kw * rng.uniform(*CONTRACT_SHARES[key])))
            for key in plan.contracts
        }
    return usage, demand, inputs


def _bill(name, usage, rounding=True, breakdown=False, **inputs):
    """A bill on fresh BillingInputs, since calculate_bill fills in
    billing_cycle_months on the one it is given. The UserWarnings for
    partial months, hourly demand and missing contract keys are ignored."""
    inputs = {k: dict(v) if isinstance(v, dict) else v for k, v in inputs.items()}
    calculate = tou.calculate_bill_breakdown if breakdown else tou.calculate_bill
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return calculate(
            usage, name, tou.BillingInputs(taipower_rounding=rounding, **inputs)
        )


def _base(name, rounding=True, variant="busy", breakdown=False):
    """The sample's bill, computed once per plan and options."""
    return _sample_bill(name, rounding, variant, breakdown)


@cache
def _sample_bill(name, rounding, variant, breakdown):
    usage, demand, inputs = _sample(name, variant)
    return _bill(name, usage, rounding, breakdown, demand_kw=demand, **inputs)


def test_every_plan_is_sampled():
    """README API Quickstart: 18 plans total. A new plan needs a row in PLANS."""
    assert sorted(PLANS) == sorted(tou.available_plans())


@pytest.mark.parametrize("name", PLANS)
def test_total_is_the_sum_of_the_items(name):
    """README Quick Formula: 總電費 = 電能費 + 基本費 + 違約金 ± 功率因數調整 +
    其他調整, with 違約金 and 功率因數 in adjustment. Unrounded, nothing else
    enters the total."""
    bill = _base(name, rounding=False)
    items = bill[ITEMS].sum(axis=1).to_numpy()
    assert bill["total"].to_numpy() == pytest.approx(items, rel=1e-12)


@pytest.mark.parametrize("name", PLANS)
def test_items_are_cut_to_the_jiao_and_the_total_rounded_to_the_yuan(name):
    """施行細則 第二十九條: 應計電費各項均計至角位，分位以下捨棄；電費總金額...均以元
    為單位，角位四捨五入進整. The total is the items' sum rounded half up.
    high_voltage_ev rounds its 低壓 bill, then 95% of it (CHANGELOG 0.2.0), and
    stays within half a 元 of its items."""
    bill = _base(name)
    jiao = bill[ITEMS].to_numpy() * 10
    assert jiao == pytest.approx(np.round(jiao), abs=1e-6)
    items = bill[ITEMS].sum(axis=1).to_numpy()
    total = bill["total"].to_numpy()
    assert total == pytest.approx(np.round(total), abs=1e-9)
    assert np.abs(total - items).max() <= 0.5 + 1e-9
    if PLANS[name].ratio == 1.0:
        assert total == pytest.approx(np.floor(np.round(items, 6) + 0.5))


@pytest.mark.parametrize("name", PLANS)
def test_rounding_moves_the_total_less_than_its_cuts(name):
    """施行細則 第二十八條 reads each 時段 register, four at most, to the whole
    kWh, half a kWh from the kWh given at up to the highest 電價表 price, 12.47
    (line 629), and 簡易型's 1.04 加計 (line 204). 第二十九條 cuts five items
    (流動電費, 基本電費, 2000度 加計, 超約, 1.6倍 流動電費) by under a 角 each,
    works 功率因數 from the cut items and cuts it too, then moves the total by
    half a 元 at most. high_voltage_ev then takes 95% and rounds again."""
    _, _, inputs = _sample(name)
    share = abs(80 - min(inputs["power_factor"], 95)) / 1000
    reading = 4 * 0.5 * (12.47 + 1.04)
    cuts = (0.1 * 5 + reading) * (1 + share) + 0.1
    plan = PLANS[name]
    bound = 0.5 + cuts if plan.ratio == 1.0 else 0.5 + plan.ratio * (0.5 + cuts)
    moved = _base(name)["total"] - _base(name, rounding=False)["total"]
    assert moved.abs().max() < bound


def _june_and_any(usage, rng, count):
    june = np.flatnonzero(usage.index.month == 6)
    return np.concatenate([rng.choice(june, 1), rng.choice(len(usage), count)])


@VARIANTS
@pytest.mark.parametrize("name", PLANS)
def test_more_kwh_never_lowers_the_bill(name, variant, rounding):
    """Every 電價表 price per kWh is positive, 2000度 加計 adds per kWh, and
    功率因數 takes 1.5% off at most (line 469). A month's first kWh ends its
    half basic fee (抄見度數與最高需量均為0, lines 407, 712-715 and 1064) and its
    80% 功率因數 (施行細則 第三十八條)."""
    usage, demand, inputs = _sample(name, variant)
    rng = _rng(name, variant, "kwh")
    at = _june_and_any(usage, rng, 12)
    more = usage.copy()
    more.iloc[at] += PLANS[name].size_kw * rng.uniform(0.1, 2.0, len(at))
    before = _base(name, rounding, variant)
    after = _bill(name, more, rounding, demand_kw=demand, **inputs)
    for column in ("energy_cost", "total"):
        assert (after[column] >= before[column] - 1e-9).all(), column


@VARIANTS
@pytest.mark.parametrize("name", PLANS)
def test_more_demand_never_lowers_the_bill(name, variant, rounding):
    """第五章 七(一) (lines 1090-1131): each time's 超約瓩數 grows with its
    highest demand and leaves out the excess of the times before it, which is
    billed at a higher or equal rate. A month's first demand ends its half
    basic fee (lines 407, 712-715 and 1064)."""
    usage, demand, inputs = _sample(name, variant)
    rng = _rng(name, variant, "demand")
    at = _june_and_any(usage, rng, 12)
    more = demand.copy()
    more.iloc[at] += PLANS[name].size_kw * rng.uniform(0.0, 0.5, len(at))
    before = _base(name, rounding, variant)
    after = _bill(name, usage, rounding, demand_kw=more, **inputs)
    assert (after["total"] >= before["total"] - 1e-9).all()


@pytest.mark.parametrize(("name", "key"), CONTRACTS)
def test_a_larger_contract_never_lowers_the_basic_fee(name, key):
    """基本電費 = 經常契約電價 x 經常 + 非夏月 (or 半尖峰) 契約電價 x its contract +
    週六半尖峰或離峰契約電價 x max(0, 週六半尖峰 + 離峰 − (經常 + 非夏月 or 半尖峰)
    x 0.5) (電價表 lines 374-403, 651-709 and 1025-1060). Each contract's own
    price is over half the 週六半尖峰 price, so a larger one costs more. 非夏月契約
    has no 夏月 price and enters the last term with −0.5, so in June it lowers
    the fee or leaves it."""
    usage, demand, inputs = _sample(name)
    larger = dict(inputs["contract_capacities"])
    larger[key] += float(_rng(name, key).integers(1, PLANS[name].size_kw // 2))
    inputs = {**inputs, "contract_capacities": larger, "demand_kw": demand}
    before = _base(name, rounding=False)["basic_cost"]
    after = _bill(name, usage, rounding=False, **inputs)["basic_cost"]
    if key == "non_summer":
        assert after.loc["2026-06-01"] <= before.loc["2026-06-01"] + 1e-9
    else:
        assert (after >= before - 1e-9).all()


@pytest.mark.parametrize("name", PLANS)
def test_moving_kwh_within_a_period_keeps_the_bill(name):
    """README How TOU Rates Work: Energy Cost = Σ(Period_Usage_kWh x
    Period_Rate), so a kWh's price depends on its season, day type and period
    alone. Shuffling kWh among a month's hours that share all three changes no
    item. Tiered plans price the month's total. demand_kw stays as it was.
    Unrounded, as an optimizer moves load; rounding equal amounts is equal."""
    usage, demand, inputs = _sample(name)
    context = tou.period_context(usage.index, name)
    groups = pd.DataFrame(
        {
            "month": usage.index.month,
            **{c: context[c].astype(str).to_numpy() for c in context.columns},
        }
    ).groupby(["month", *context.columns])
    values = usage.to_numpy().copy()
    rng = _rng(name, "move")
    for positions in groups.indices.values():
        values[positions] = rng.permutation(values[positions])
    moved = pd.Series(values, index=usage.index)
    assert not moved.equals(usage)
    bill = _bill(name, moved, rounding=False, demand_kw=demand, **inputs)
    pd.testing.assert_frame_equal(bill, _base(name, rounding=False), rtol=1e-12)


def _five_minutes(usage):
    index = pd.date_range(usage.index[0], periods=3 * len(usage), freq="5min")
    return pd.Series(np.repeat(usage.to_numpy() / 3, 3), index=index)


RESOLUTIONS = [(name, "5min") for name in PLANS] + [
    (name, "h") for name, plan in PLANS.items() if plan.whole_hours
]


@cache
def _quarter_hour_energy(name):
    usage, _, inputs = _sample(name, quarter_hours=True)
    return _bill(name, usage, rounding=False, **inputs)["energy_cost"].to_numpy()


@pytest.mark.parametrize(("name", "resolution"), RESOLUTIONS)
def test_energy_cost_does_not_depend_on_resolution(name, resolution):
    """README Data Resolution Requirements: Energy Cost (電能費) | Any
    resolution | Only total kWh per period matters. Each 15-minute value split
    into three 5-minute ones, or four summed into their hour, keeps every
    period's kWh. 批次 periods change on the half hour (line 968), which
    hourly data cannot show, so those plans are left out of hourly."""
    usage, _, inputs = _sample(name, quarter_hours=True)
    other = _five_minutes(usage) if resolution == "5min" else usage.resample("h").sum()
    energy = _bill(name, other, rounding=False, **inputs)["energy_cost"]
    assert energy.to_numpy() == pytest.approx(_quarter_hour_energy(name), rel=1e-12)


@cache
def _over_contract_bill(name, percent, hourly):
    """A WEEK bill on an 經常契約 of the plan's size. demand_kw is 5 kW under
    it but percent over it in PEAK_QUARTER, or absent for None. hourly sums
    the kWh into hours and leaves demand_kw at 15 minutes."""
    contract = PLANS[name].size_kw
    usage = pd.Series(0.25, index=WEEK)
    if hourly:
        usage = usage.resample("h").sum()
    inputs = {"contract_capacities": {"regular": contract}}
    if percent is not None:
        demand = pd.Series(contract - 5.0, index=WEEK)
        demand[PEAK_QUARTER] = contract + round(contract * percent / 100)
        inputs["demand_kw"] = demand
    return _bill(name, usage, rounding=False, **inputs)


@pytest.mark.parametrize("percent", [0, 5, 15])
@pytest.mark.parametrize("name", OVER_CONTRACT)
def test_over_contract_is_2x_within_10_percent_and_3x_above(name, percent):
    """電價表 第三章 五(三)5 (lines 446-450), 第四章 七(二)2 (lines 787-791) and
    第五章 七(二) (lines 1127-1131): 當月用電最高需量超出其契約容量時，超出部分...
    在契約容量10%以下部分按2倍、超過契約容量10%部分按3倍計收基本電費, at the
    夏月經常契約 price. A peak at the contract pays nothing."""
    plan = PLANS[name]
    over = round(plan.size_kw * percent / 100)
    low = min(over, 0.1 * plan.size_kw)
    fee = plan.regular_summer * (2 * low + 3 * (over - low))
    with_demand = _over_contract_bill(name, percent, False)["total"]
    added = (with_demand - _over_contract_bill(name, None, False)["total"]).iloc[0]
    assert added == pytest.approx(plan.ratio * fee)


@pytest.mark.parametrize("name", OVER_CONTRACT)
def test_over_contract_does_not_depend_on_the_usage_resolution(name):
    """營業規章 第三條: 需量 is the 十五分鐘平均瓩數, and the README's Data
    Resolution Requirements take energy at any resolution and demand_kw at 15
    minutes. Hourly kWh with the same 15-minute demand_kw pay the same 超約."""
    expected = _over_contract_bill(name, 15, False)["adjustment"].iloc[0]
    bill = _over_contract_bill(name, 15, True)
    assert bill["adjustment"].iloc[0] == pytest.approx(expected)


@pytest.mark.parametrize("zone", ["Asia/Taipei", "UTC"])
@pytest.mark.parametrize("name", PLANS)
def test_bill_does_not_depend_on_the_index_timezone(name, zone):
    """CHANGELOG 0.2.0: Timezone-aware input is evaluated in Taiwan local time
    (UTC+8), and the README reads naive timestamps as Taiwan time. The same
    instants, naive, in Asia/Taipei or in UTC, with demand_kw in the same zone,
    give the same bill."""
    usage, demand, inputs = _sample(name)

    def aware(series):
        return series.tz_localize("Asia/Taipei").tz_convert(zone)

    bill = _bill(name, aware(usage), demand_kw=aware(demand), **inputs)
    pd.testing.assert_frame_equal(bill, _base(name))


def test_an_aware_datetime_is_priced_at_taiwan_time():
    """README Time & Rate Queries: Timezone-aware timestamps are converted to
    Taiwan time (UTC+8) first. period_at and pricing_context give a UTC
    datetime the period and price of its Taiwan wall time, on every plan."""
    rng = _rng("aware datetime")
    hours = list(HOURS[rng.choice(len(HOURS), 6, replace=False)])
    hours += [pd.Timestamp("2026-05-16 03:00"), pd.Timestamp("2026-06-01 03:00")]
    wrong = []
    for name in PLANS:
        plan = tou.plan(name)
        for hour in hours:
            local = hour.to_pydatetime()
            utc = local.replace(tzinfo=TAIWAN).astimezone(timezone.utc)
            if tou.period_at(utc, name) != tou.period_at(local, name) or (
                plan.pricing_context(utc) != plan.pricing_context(local)
            ):
                wrong.append(f"{name} {local:%m-%d %H:%M}")
    assert wrong == []


@ROUNDING
@pytest.mark.parametrize("name", PLANS)
def test_breakdown_summary_is_the_bill(name, rounding):
    """README Detailed Bill Breakdown: calculate_bill_breakdown shows exactly
    how the bill was composed. Its summary repeats calculate_bill's columns."""
    bill = _base(name, rounding)
    summary = _base(name, rounding, breakdown=True)["summary"]
    pd.testing.assert_frame_equal(summary[bill.columns], bill)


@pytest.mark.parametrize("name", PLANS)
def test_breakdown_rows_add_up_to_the_summary(name):
    """README Detailed Bill Breakdown. Unrounded, the details' energy_cost,
    the basic_details' cost and the adjustment_details' amount add up to each
    bill's items. CHANGELOG 0.2.0: tiered rows have costs, one row per season."""
    result = _base(name, rounding=False, breakdown=True)
    summary = result["summary"]
    for frame, column, item in [
        ("details", "energy_cost", "energy_cost"),
        ("basic_details", "cost", "basic_cost"),
        ("adjustment_details", "amount", "adjustment"),
    ]:
        rows = result[frame]
        sums = pd.Series(0.0, index=summary.index)
        if not rows.empty:
            sums = sums.add(rows.groupby("period")[column].sum(), fill_value=0.0)
        assert sums.to_numpy() == pytest.approx(
            summary[item].to_numpy(), rel=1e-9, abs=1e-9
        ), frame
    parts = summary[[*ITEMS, "min_fee_adjustment"]].sum(axis=1)
    assert summary["total"].to_numpy() == pytest.approx(parts.to_numpy())


@pytest.mark.parametrize("name", TIME_OF_USE)
def test_interval_prices_add_up_to_the_energy_cost(name):
    """README How TOU Rates Work: Energy Cost = Σ(Period_Usage_kWh x
    Period_Rate). pricing_context's rate x kWh, calculate_costs and the bill's
    unrounded energy_cost agree. high_voltage_ev's prices are 95% of the 低壓
    ones its bill lists (CHANGELOG 0.2.0: pricing_context and calculate_costs
    are unchanged)."""
    usage, _, _ = _sample(name)
    plan = tou.plan(name)
    context = plan.pricing_context(usage.index, usage_kwh=usage)
    cost = context["cost"].astype(float)
    assert cost.to_numpy() == pytest.approx((context["rate"] * usage).to_numpy())
    monthly = cost.groupby(usage.index.to_period("M")).sum().to_numpy()
    costs = plan.calculate_costs(usage).to_numpy()
    energy = _base(name, rounding=False)["energy_cost"].to_numpy()
    assert monthly == pytest.approx(costs, rel=1e-12)
    assert costs == pytest.approx(PLANS[name].ratio * energy, rel=1e-12)


@pytest.mark.parametrize("months", [1, 2])
@pytest.mark.parametrize("name", TIERED)
def test_tiered_costs_are_the_bills_energy_cost(name, months):
    """CHANGELOG 0.2.0: a tiered period over 夏月 and 非夏月 is priced at each
    season's rates weighted by its days, where 0.1.0's calculate_bill and
    calculate_costs disagreed. With the same months per bill, May-June in one,
    they give the same energy cost."""
    usage, _, inputs = _sample(name)
    cycles = {1: tou.BillingCycleType.MONTHLY, 2: tou.BillingCycleType.EVEN_MONTH}
    plan = tou.plan(name, billing_cycle_type=cycles[months])
    costs = plan.calculate_costs(usage).to_numpy()
    bill = _bill(name, usage, rounding=False, billing_cycle_months=months, **inputs)
    assert costs == pytest.approx(bill["energy_cost"].to_numpy(), rel=1e-12)


@pytest.mark.parametrize("name", PLANS)
def test_power_factor_moves_the_bill_a_tenth_of_a_percent_per_percent(name):
    """電價表 六 (lines 461-469, 729-734 and 1085-1088): 功率因數不及80%時，每低1%，
    該月份電費應增加0.1%；超過80%時，每超過1%，該月份電費應減少0.1%，惟...超過95%
    部分不予扣減. 該月份電費 leaves out 按戶計收 (line 357). Without demand, 80%
    changes nothing and other values move the bill by (80 − pf) / 1000 of
    基本電費 − 按戶計收 + 流動電費 + 2000度 加計."""
    plan = PLANS[name]
    usage, _, inputs = _sample(name)

    def bill(power_factor):
        return _bill(name, usage, False, **{**inputs, "power_factor": power_factor})

    unadjusted = bill(None)
    pd.testing.assert_frame_equal(bill(80.0), unadjusted)
    base = (
        unadjusted["basic_cost"]
        - plan.household
        + unadjusted[["energy_cost", "surcharge"]].sum(axis=1)
    )
    for power_factor in (70.0, 99.0):
        moved = bill(power_factor)["total"] - unadjusted["total"]
        share = (80 - min(power_factor, 95)) / 1000
        assert moved.to_numpy() == pytest.approx(
            plan.ratio * share * base.to_numpy(), rel=1e-9
        ), power_factor


@pytest.mark.parametrize("name", OVER_CONTRACT)
def test_power_factor_below_80_also_moves_the_over_contract_fee(name):
    """施行細則 第三十條: 計算功率因數調整費，包括...超出契約容量之非約定基本電費；惟
    功率因數在80％（含）以上之超約用戶，不另計算. So 70% and 90% move the bill by
    opposite amounts, apart from 1% of the 超約 fee that only 70% adds. The
    經常契約 is 80% of the sample's load, so the bill has 超約."""
    usage, demand, inputs = _sample(name)
    contracts = {**inputs["contract_capacities"], "regular": 0.8 * PLANS[name].size_kw}

    def total(power_factor, demand_kw=None):
        changed = {"contract_capacities": contracts, "power_factor": power_factor}
        bill = _bill(name, usage, False, demand_kw=demand_kw, **{**inputs, **changed})
        return bill["total"]

    unadjusted = total(None, demand)
    over = unadjusted - total(None)
    assert (over > 0).all()
    moved = total(70.0, demand) + total(90.0, demand) - 2 * unadjusted
    assert moved.to_numpy() == pytest.approx(0.01 * over.to_numpy(), rel=1e-9)


@pytest.mark.parametrize("name", TIME_OF_USE)
def test_energy_cost_scales_with_kwh_off_the_tiers(name):
    """README How TOU Rates Work: Energy Cost = Σ(Period_Usage_kWh x
    Period_Rate), linear in kWh. 低壓電力非時間 has one price per season (line
    525). Tiered plans are not linear."""
    usage, _, inputs = _sample(name)
    energy = _base(name, rounding=False)["energy_cost"].to_numpy()
    scaled = _bill(name, usage * 3.7, rounding=False, **inputs)["energy_cost"]
    assert scaled.to_numpy() == pytest.approx(3.7 * energy, rel=1e-12)


@pytest.mark.parametrize("name", PLANS)
def test_bill_does_not_depend_on_the_usage_dtype(name):
    """The 電價表 bills kWh, not how a Series stores them. Whole kWh as float32
    are the same numbers as float64, so the rounded bill, with demand and
    功率因數, has the same amounts to the 分."""
    usage, demand, inputs = _sample(name)
    whole = usage.round()
    expected = _bill(name, whole, demand_kw=demand, **inputs)
    bill = _bill(name, whole.astype("float32"), demand_kw=demand, **inputs)
    pd.testing.assert_frame_equal(
        bill, expected, check_dtype=False, check_exact=False, rtol=0, atol=0.005
    )


@pytest.mark.parametrize("dtype", ["int64", "float32", "float64"])
@pytest.mark.parametrize(
    ("name", "kwh", "bill"),
    [
        (
            "residential_simple_2_tier",
            5005,
            {"energy_cost": 10310.3, "surcharge": 3125.2, "total": 13511.0},
        ),
        ("residential_non_tou", 105, {"energy_cost": 186.9, "total": 187.0}),
    ],
    ids=["simple_2000_kwh_surcharge", "non_tou_first_tier"],
)
def test_whole_kwh_bill_the_same_in_every_dtype(name, kwh, bill, dtype):
    """One July month's kWh, all at Sunday 2026-07-05 04:00. 簡易型二段式 (電價表
    lines 189-204): 5005 x 2.06 = 10310.3 off-peak, 75.00 按戶, and 3005 x 1.04 =
    3125.2 加計 over 2000 kWh, 13510.5 in all, which 第二十九條 rounds to 13511.
    表燈非時間 billed monthly (line 138): 105 x 1.78 = 186.9, rounded to 187."""
    usage = pd.Series(0, index=JULY, dtype=dtype)
    usage[pd.Timestamp("2026-07-05 04:00")] = kwh
    result = _bill(name, usage, billing_cycle_months=1, meter_phase="single")
    for column, amount in bill.items():
        assert result[column].iloc[0] == pytest.approx(amount, abs=0.005), column
