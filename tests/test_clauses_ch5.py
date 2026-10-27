"""第五章 高壓及特高壓電力電價 rules, with amounts worked from its text.

Prices are from src/taipower_tou/data/詳細電價表.md (114/10/1): 二段式 lines
856-880, 三段式 892-955, 批次 964-980, and 電動車 line 983 as 95% of the
第四章 table at lines 627-637.
"""

from datetime import date, datetime

import pandas as pd
import pytest

import taipower_tou as tou

JULY = pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min")
JANUARY = pd.date_range("2026-01-01", "2026-01-31 23:45", freq="15min")
MONTHS = {"july": (JULY, 0), "january": (JANUARY, 1)}

# Per kW a month: 經常契約 (夏月, 非夏月), 非夏月 or 半尖峰契約, and
# 週六半尖峰 or 離峰契約 (夏月, 非夏月). Lines 856-859, 892-895, 964-967.
HV = {"regular": (223.60, 166.90), "second": 166.90, "weekend": (44.70, 33.30)}
EHV = {"regular": (217.30, 160.60), "second": 160.60, "weekend": (43.40, 32.10)}
TWO_STAGE = {
    "high_voltage_2_tier": HV,
    "high_voltage_power": HV,
    "high_voltage_batch": HV,
    "extra_high_voltage_2_tier": EHV,
    "extra_high_voltage_power": EHV,
    "extra_high_voltage_batch": EHV,
}
THREE_STAGE = {"high_voltage_three_stage": HV, "extra_high_voltage_three_stage": EHV}

EV_SHARE = 0.95
EV_HOUSEHOLD = EV_SHARE * 262.50
EV_REGULAR = (EV_SHARE * 47.20, EV_SHARE * 34.60)


def _july_energy(weekday, saturday, sunday):
    """Cost of 1 kWh every hour of July 2026, from each day's (hours, price).

    July 2026 has 23 weekdays, 4 Saturdays, 4 Sundays and no 離峰日.
    """
    return sum(
        days * sum(hours * price for hours, price in rows)
        for days, rows in ((23, weekday), (4, saturday), (4, sunday))
    )


HV_2_TIER_JULY = _july_energy(
    [(15, 6.75), (9, 2.71)], [(15, 2.77), (9, 2.71)], [(24, 2.71)]
)
EHV_2_TIER_JULY = _july_energy(
    [(15, 6.17), (9, 2.55)], [(15, 2.73), (9, 2.55)], [(24, 2.55)]
)
JULY_ENERGY = {
    "high_voltage_2_tier": HV_2_TIER_JULY,
    "high_voltage_power": HV_2_TIER_JULY,
    "extra_high_voltage_2_tier": EHV_2_TIER_JULY,
    "extra_high_voltage_power": EHV_2_TIER_JULY,
    "high_voltage_three_stage": _july_energy(
        [(6, 9.39), (9, 5.85), (9, 2.53)], [(15, 2.60), (9, 2.53)], [(24, 2.53)]
    ),
    "extra_high_voltage_three_stage": _july_energy(
        [(6, 8.69), (9, 5.38), (9, 2.40)], [(15, 2.50), (9, 2.40)], [(24, 2.40)]
    ),
    "high_voltage_batch": _july_energy(
        [(6, 12.47), (18, 3.18)], [(6, 3.26), (18, 3.18)], [(24, 3.18)]
    ),
    "extra_high_voltage_batch": _july_energy(
        [(6, 11.44), (18, 2.99)], [(6, 3.20), (18, 2.99)], [(24, 2.99)]
    ),
    "high_voltage_ev": EV_SHARE
    * _july_energy([(6, 12.47), (18, 3.05)], [(24, 3.05)], [(24, 3.05)]),
}
JULY_REGULAR = {
    **{plan: fees["regular"][0] for plan, fees in {**TWO_STAGE, **THREE_STAGE}.items()},
    "high_voltage_ev": EV_REGULAR[0],
}
HOUSEHOLD = {"high_voltage_ev": EV_HOUSEHOLD}


def _bill(plan, index, kwh=0.25, demand=None, **inputs):
    usage = pd.Series(kwh, index=index)
    if demand is not None:
        inputs["demand_kw"] = demand
    return tou.calculate_bill(usage, plan, tou.BillingInputs(**inputs)).iloc[0]


def _demand(index, peaks, kw=100.0):
    """kw all month, with the kW in peaks at (day, hour) on that hour."""
    demand = pd.Series(kw, index=index)
    for (day, hour), value in peaks.items():
        demand[(index.day == day) & (index.hour == hour)] = value
    return demand


def _night_load(index, events):
    """100 kW from 00:00 to 06:00 each day, 0 kW otherwise, plus events."""
    return _demand(index, events, kw=100.0 * (index.hour < 6))


@pytest.mark.parametrize("plan", JULY_ENERGY)
def test_month_bill_is_basic_fee_plus_energy_by_period(plan):
    """五(一): 每月電費為基本電費與流動電費之總和, with 流動電費 by each
    time's 實用電度 (五(一)1-4)."""
    bill = _bill(plan, JULY, contract_capacities={"regular": 200})
    basic = HOUSEHOLD.get(plan, 0.0) + JULY_REGULAR[plan] * 200
    assert [bill["basic_cost"], bill["energy_cost"], bill["total"]] == pytest.approx(
        [basic, JULY_ENERGY[plan], basic + JULY_ENERGY[plan]]
    )


CAPACITIES = {"regular": 200, "saturday_semi_peak": 100, "off_peak": 300}
WEEKEND_KW = (100 + 300) - (200 + 50) * 0.5


@pytest.mark.parametrize("month", MONTHS)
@pytest.mark.parametrize("plan", TWO_STAGE)
def test_two_stage_and_batch_basic_fee_formula(plan, month):
    """五(一)1 lines 1023-1041, and 五(一)3 批次 比照二段式: 非夏月契約 is
    billed only in 非夏月, but is taken off the 週六半尖峰或離峰 kW all year."""
    index, season = MONTHS[month]
    fees = TWO_STAGE[plan]
    expected = fees["regular"][season] * 200 + fees["weekend"][season] * WEEKEND_KW
    if season == 1:
        expected += fees["second"] * 50
    bill = _bill(plan, index, contract_capacities={**CAPACITIES, "non_summer": 50})
    assert bill["basic_cost"] == pytest.approx(expected)


@pytest.mark.parametrize("month", MONTHS)
@pytest.mark.parametrize("plan", THREE_STAGE)
def test_three_stage_basic_fee_formula(plan, month):
    """五(一)2 lines 1049-1054: 當月 prices for 經常, 半尖峰 and
    〔(週六半尖峰 + 離峰) - (經常 + 半尖峰) x 0.5〕."""
    index, season = MONTHS[month]
    fees = THREE_STAGE[plan]
    expected = (
        fees["regular"][season] * 200
        + fees["second"] * 50
        + fees["weekend"][season] * WEEKEND_KW
    )
    bill = _bill(plan, index, contract_capacities={**CAPACITIES, "semi_peak": 50})
    assert bill["basic_cost"] == pytest.approx(expected)


@pytest.mark.parametrize("month", MONTHS)
@pytest.mark.parametrize("plan", {**TWO_STAGE, **THREE_STAGE})
def test_weekend_only_contracts_pay_the_weekend_price_on_both(plan, month):
    """五(一)1 and 2 但書: 僅在週六半尖峰時間或離峰時間用電 → 基本電費按
    週六半尖峰契約容量與離峰契約容量計算."""
    index, season = MONTHS[month]
    usage = _night_load(index, {}) / 4
    inputs = tou.BillingInputs(
        contract_capacities={"saturday_semi_peak": 100, "off_peak": 300},
        demand_kw=_night_load(index, {}),
    )
    bill = tou.calculate_bill(usage, plan, inputs).iloc[0]
    fees = {**TWO_STAGE, **THREE_STAGE}[plan]
    assert bill["basic_cost"] == pytest.approx(fees["weekend"][season] * 400)


@pytest.mark.parametrize(("month", "regular"), [("july", 0), ("january", 1)])
def test_ev_basic_fee_is_per_household_and_per_regular_contract(month, regular):
    """五(一)4a lines 1057-1062: 按戶 and 夏月(非夏月)經常契約電價 x 經常契約容量."""
    index, _ = MONTHS[month]
    bill = _bill("high_voltage_ev", index, contract_capacities={"regular": 200})
    assert bill["basic_cost"] == pytest.approx(EV_HOUSEHOLD + EV_REGULAR[regular] * 200)


def test_month_with_demand_but_no_kwh_pays_the_full_basic_fee():
    """五(二) halves the basic fee only when 抄見度數與最高需量均為0."""
    bill = _bill(
        "high_voltage_2_tier",
        JULY,
        kwh=0.0,
        demand=_demand(JULY, {(15, 17): 50}, kw=0.0),
        contract_capacities={"regular": 200},
    )
    assert bill["total"] == pytest.approx(HV["regular"][0] * 200)


@pytest.mark.parametrize(
    ("power_factor", "share"), [(90, -0.01), (70, 0.01), (98, -0.015)]
)
@pytest.mark.parametrize("plan", JULY_ENERGY)
def test_power_factor_adjusts_basic_and_energy(plan, power_factor, share):
    """六 lines 1086-1088: 0.1% per 1% from 80%, no 扣減 above 95%.
    五(一)4b: 按戶計收之基本電費，不列計功率因數調整費."""
    bill = _bill(
        plan, JULY, contract_capacities={"regular": 200}, power_factor=power_factor
    )
    month = JULY_REGULAR[plan] * 200 + JULY_ENERGY[plan]
    assert bill["adjustment"] == pytest.approx(share * month)


def _over_cost(fees, season, over):
    """2x the 契約電價 of each time for 超約 kW within 10% (七(二)1)."""
    prices = {
        "regular": fees["regular"][season],
        "semi_peak": fees["second"],
        "weekend": fees["weekend"][season],
    }
    return sum(2 * kw * prices[key] for key, kw in over.items())


TWO_STAGE_CONTRACT = {"regular": 200, "saturday_semi_peak": 30, "off_peak": 50}
TWO_STAGE_CASES = {
    "saturday-only": ("july", TWO_STAGE_CONTRACT, {(18, 17): 236}, {"weekend": 6}),
    "saturday-less-peak": (
        "july",
        TWO_STAGE_CONTRACT,
        {(15, 17): 205, (18, 17): 238},
        {"regular": 5, "weekend": 3},
    ),
    "off-peak-only": ("july", TWO_STAGE_CONTRACT, {(15, 3): 290}, {"weekend": 10}),
    "off-peak-less-larger": (
        "july",
        TWO_STAGE_CONTRACT,
        {(15, 17): 205, (18, 17): 238, (15, 3): 292},
        {"regular": 5, "weekend": 3 + 4},
    ),
    "off-peak-less-peak-above-saturday": (
        "july",
        TWO_STAGE_CONTRACT,
        {(15, 17): 210, (18, 17): 236, (15, 3): 292},
        {"regular": 10, "weekend": 2},
    ),
    "off-peak-below-saturday": (
        "july",
        TWO_STAGE_CONTRACT,
        {(18, 17): 240, (15, 3): 285},
        {"weekend": 10},
    ),
    "non-summer-all-times": (
        "january",
        {"regular": 200, "non_summer": 50, "saturday_semi_peak": 30, "off_peak": 20},
        {(14, 17): 254, (17, 17): 287, (14, 3): 310},
        {"regular": 4, "weekend": 3 + 3},
    ),
}


@pytest.mark.parametrize("case", TWO_STAGE_CASES)
@pytest.mark.parametrize("plan", TWO_STAGE)
def test_two_stage_over_contract_by_time(plan, case):
    """七(一)1 lines 1094-1107, and 七(一)3 批次 比照二段式: 週六半尖峰超約 is
    over 經常 + 非夏月 + 週六半尖峰, 離峰超約 also over 離峰契約. Each leaves
    out the larger excess of the times before it, and is billed 2x its own
    契約電價 (七(二)1); every case stays within 10% of every contract."""
    month, capacities, peaks, over = TWO_STAGE_CASES[case]
    index, season = MONTHS[month]
    bill = _bill(
        plan, index, demand=_demand(index, peaks), contract_capacities=capacities
    )
    assert bill["adjustment"] == pytest.approx(
        _over_cost(TWO_STAGE[plan], season, over)
    )


THREE_STAGE_CONTRACT = {
    "regular": 200,
    "semi_peak": 50,
    "saturday_semi_peak": 30,
    "off_peak": 20,
}
THREE_STAGE_CASES = {
    "peak": ("july", {(15, 17): 204}, {"regular": 4}),
    "semi-peak-less-peak": (
        "july",
        {(15, 17): 204, (15, 10): 256},
        {"regular": 4, "semi_peak": 2},
    ),
    "semi-peak-below-peak": ("july", {(15, 17): 210, (15, 10): 255}, {"regular": 10}),
    "saturday-less-peak-above-semi-peak": (
        "july",
        {(15, 17): 210, (15, 10): 255, (18, 17): 292},
        {"regular": 10, "weekend": 2},
    ),
    "saturday-less-larger": (
        "july",
        {(15, 17): 204, (15, 10): 256, (18, 17): 289},
        {"regular": 4, "semi_peak": 2, "weekend": 3},
    ),
    "off-peak-less-largest": (
        "july",
        {(15, 17): 204, (15, 10): 256, (18, 17): 289, (15, 3): 311},
        {"regular": 4, "semi_peak": 2, "weekend": 3 + 2},
    ),
    "non-summer-semi-peak-and-saturday": (
        "january",
        {(14, 17): 256, (17, 17): 287},
        {"semi_peak": 6, "weekend": 1},
    ),
}


@pytest.mark.parametrize("case", THREE_STAGE_CASES)
@pytest.mark.parametrize("plan", THREE_STAGE)
def test_three_stage_over_contract_by_time(plan, case):
    """七(一)2 lines 1109-1125: 尖峰超約 over 經常, 半尖峰 over 經常 + 半尖峰,
    週六半尖峰 and 離峰 over the next contracts too, each leaving out the
    largest excess before it, billed 2x its own 契約電價 (七(二)1)."""
    month, peaks, over = THREE_STAGE_CASES[case]
    index, season = MONTHS[month]
    bill = _bill(
        plan,
        index,
        demand=_demand(index, peaks),
        contract_capacities=THREE_STAGE_CONTRACT,
    )
    assert bill["adjustment"] == pytest.approx(
        _over_cost(THREE_STAGE[plan], season, over)
    )


@pytest.mark.parametrize(
    ("month", "peaks", "over_kw"),
    [
        ("july", {(15, 3): 210}, 10),
        ("july", {(18, 17): 212}, 12),
        ("july", {(15, 17): 205, (19, 3): 212}, 12),
        ("january", {(14, 17): 210}, 10),
    ],
    ids=["weekday-off-peak", "saturday", "highest-of-the-month", "non-summer"],
)
def test_ev_over_contract_is_the_months_highest_demand(month, peaks, over_kw):
    """七(一)4 line 1128: 超約瓩數＝當月用電最高需量－經常契約容量, at any hour."""
    index, season = MONTHS[month]
    bill = _bill(
        "high_voltage_ev",
        index,
        demand=_demand(index, peaks),
        contract_capacities={"regular": 200},
    )
    assert bill["adjustment"] == pytest.approx(2 * over_kw * EV_REGULAR[season])


@pytest.mark.parametrize("plan", JULY_REGULAR)
def test_over_contract_above_10_percent_pays_3x(plan):
    """七(二) lines 1132-1133: 30 kW over 200 kW is 20 kW at 2x and 10 kW at 3x."""
    bill = _bill(
        plan,
        JULY,
        demand=_demand(JULY, {(15, 17): 230}),
        contract_capacities={"regular": 200},
    )
    assert bill["adjustment"] == pytest.approx((20 * 2 + 10 * 3) * JULY_REGULAR[plan])


@pytest.mark.parametrize("plan", ["high_voltage_2_tier", "high_voltage_three_stage"])
def test_over_contract_gets_no_power_factor_discount(plan):
    """七(二) line 1131: 超約 基本電費 不給予功率因數扣減."""
    bill = _bill(
        plan,
        JULY,
        demand=_demand(JULY, {(15, 17): 205}),
        contract_capacities={"regular": 200},
        power_factor=90,
    )
    month = HV["regular"][0] * 200 + JULY_ENERGY[plan]
    assert bill["adjustment"] == pytest.approx(-0.01 * month + 2 * 5 * HV["regular"][0])


@pytest.mark.parametrize(
    ("capacities", "event", "basic_price", "energy_price"),
    [
        ({"saturday_semi_peak": 300}, (15, 17), HV["regular"][0], 6.75),
        ({"off_peak": 300}, (18, 17), HV["weekend"][0], 2.77),
    ],
    ids=["saturday-contract-at-weekday-peak", "off-peak-contract-on-saturday"],
)
def test_weekend_only_contract_used_outside_its_times(
    capacities, event, basic_price, energy_price
):
    """八(六) lines 1160-1164: 僅訂週六半尖峰 or 僅訂離峰契約容量 users pay
    4.8x the time's 基本電費 on its 最高需量 and 1.6x its 流動電費.

    100 kW from 00:00 to 06:00 every July day is 離峰 (line 865), and 50 kW
    for one hour is the use outside the contract's times."""
    demand = _night_load(JULY, {event: 50})
    inputs = tou.BillingInputs(contract_capacities=capacities, demand_kw=demand)
    bill = tou.calculate_bill(demand / 4, "high_voltage_2_tier", inputs).iloc[0]
    night = 31 * 6 * 100 * 2.71
    expected = (
        HV["weekend"][0] * 300
        + night
        + 4.8 * basic_price * 50
        + 1.6 * energy_price * 50
    )
    assert bill["total"] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("plan", "non_summer", "summer"),
    [
        ("high_voltage_2_tier", 6.37, 6.75),
        ("high_voltage_batch", 11.79, 12.47),
        ("extra_high_voltage_2_tier", 5.79, 6.17),
        ("extra_high_voltage_three_stage", 5.03, 8.69),
        ("extra_high_voltage_batch", 10.80, 11.44),
    ],
)
def test_high_voltage_summer_season_runs_may_16_to_october_15(plan, non_summer, summer):
    """夏月 (5月16日至10月15日) in each table's header, lines 854, 890, 962.
    The prices are a weekday 17:00 in each season."""
    days = {
        datetime(2026, 5, 15, 17): ("non_summer", non_summer),
        datetime(2026, 5, 18, 17): ("summer", summer),
        datetime(2026, 10, 15, 17): ("summer", summer),
        datetime(2026, 10, 16, 17): ("non_summer", non_summer),
    }
    tariff = tou.plan(plan)
    got = {when: tariff.pricing_context(when) for when in days}
    assert {when: (c["season"], c["rate"]) for when, c in got.items()} == {
        when: (season, pytest.approx(rate)) for when, (season, rate) in days.items()
    }


def test_high_voltage_ev_summer_runs_june_1_to_september_30():
    """四(四) lines 982-984: 按第四章第四條第(三)款「電動車充換電設施電價」95%
    計算, whose 夏月 is 6月1日至9月30日 (line 625), not the 5月16日至10月15日 of
    the other 高壓 tables. Taipower's 各類電價表及計算範例 (113/4/1) prints the
    高壓 table with the same 夏月. The prices are a weekday 17:00, 尖峰 in both
    seasons (lines 629-630)."""
    days = {
        datetime(2026, 5, 29, 17): ("non_summer", 12.14),
        datetime(2026, 6, 1, 17): ("summer", 12.47),
        datetime(2026, 9, 30, 17): ("summer", 12.47),
        datetime(2026, 10, 1, 17): ("non_summer", 12.14),
    }
    tariff = tou.plan("high_voltage_ev")
    got = {when: tariff.pricing_context(when) for when in days}
    assert {when: (c["season"], c["rate"]) for when, c in got.items()} == {
        when: (season, pytest.approx(EV_SHARE * rate))
        for when, (season, rate) in days.items()
    }


VARIABLE_PEAK = {
    "high_voltage_three_stage_variable_peak": (
        HV,
        [(6, 18.33), (9, 5.85), (9, 2.53)],
        [(15, 5.85), (9, 2.53)],
        [(15, 2.60), (9, 2.53)],
        [(24, 2.53)],
    ),
    "extra_high_voltage_three_stage_variable_peak": (
        EHV,
        [(6, 17.05), (9, 5.38), (9, 2.40)],
        [(15, 5.38), (9, 2.40)],
        [(15, 2.50), (9, 2.40)],
        [(24, 2.40)],
    ),
}


@pytest.mark.xfail(
    strict=True,
    reason="not supported: no 三段式尖峰時間可變動 plan and no input for its 指定 days",
)
@pytest.mark.parametrize("plan", VARIABLE_PEAK)
def test_variable_peak_bills_peak_only_on_the_designated_days(plan):
    """四(二) 尖峰時間可變動 lines 924-956 and 註2 lines 1000-1003: 夏月
    16:00-22:00 is 尖峰 only on 指定 days, 半尖峰 09:00-24:00 on the others.
    八(七): its 契約容量 follow 尖峰時間固定, so the basic fee is the same."""
    fees, designated, weekday, saturday, sunday = VARIABLE_PEAK[plan]
    energy = sum(
        days * sum(hours * price for hours, price in rows)
        for days, rows in ((1, designated), (22, weekday), (4, saturday), (4, sunday))
    )
    inputs = tou.BillingInputs(
        contract_capacities={"regular": 200}, peak_days=[date(2026, 7, 15)]
    )
    bill = tou.calculate_bill(pd.Series(0.25, index=JULY), plan, inputs).iloc[0]
    assert bill["total"] == pytest.approx(fees["regular"][0] * 200 + energy)


@pytest.mark.xfail(
    strict=True, reason="not supported: no input for 儲冷式空調系統 usage"
)
def test_cold_storage_air_conditioning_pays_60_percent_off_peak():
    """五(五) lines 1072-1073: 儲冷式空調 離峰時間用電之流動電費按適用電價60%.

    10 kWh at 03:00 every July day is 離峰 at 2.71, and 10 kWh at 17:00 on
    15 July is 尖峰 at 6.75, which keeps its full price."""
    usage = pd.Series(0.0, index=JULY)
    usage[JULY.hour == 3] = 2.5
    usage[(JULY.day == 15) & (JULY.hour == 17)] = 2.5
    inputs = tou.BillingInputs(
        contract_capacities={"regular": 200}, cold_storage_kwh=usage
    )
    bill = tou.calculate_bill(usage, "high_voltage_2_tier", inputs).iloc[0]
    assert bill["energy_cost"] == pytest.approx(0.6 * 2.71 * 310 + 6.75 * 10)


@pytest.mark.xfail(
    strict=True,
    reason="not supported: no input for a 自備161,000 or 345,000伏特變電設備",
)
@pytest.mark.parametrize(("volts", "discount"), [(161_000, 0.02), (345_000, 0.042)])
def test_own_substation_discounts_the_extra_high_voltage_basic_fee(volts, discount):
    """五(六) lines 1074-1076: 基本電費按特高壓供電電價給予2% or 4.2%折扣.
    七(二) line 1131: 超約 基本電費 gets no 基本電費折扣."""
    bill = _bill(
        "extra_high_voltage_2_tier",
        JULY,
        demand=_demand(JULY, {(15, 17): 1010}),
        contract_capacities={"regular": 1000},
        own_substation_v=volts,
    )
    basic = EHV["regular"][0] * 1000 * (1 - discount)
    over = 2 * 10 * EHV["regular"][0]
    assert bill["total"] == pytest.approx(
        basic + JULY_ENERGY["extra_high_voltage_2_tier"] + over
    )


@pytest.mark.xfail(
    strict=True, reason="not supported: no input for a 常閉環路 or 備用 second line"
)
def test_backup_line_adds_the_backup_basic_fee():
    """五(七) lines 1077-1080 → 第七章第一節三(一)1(1) lines 1220-1222: from
    another feeder of the same 變電所, 經常用電適用電價10% on the 經常 kW."""
    bill = _bill(
        "high_voltage_2_tier",
        JULY,
        contract_capacities={"regular": 200},
        backup_supply="same_substation",
    )
    assert bill["basic_cost"] == pytest.approx(1.10 * HV["regular"][0] * 200)


@pytest.mark.xfail(
    strict=True, reason="not supported: no input for a 依法免計營業稅 customer"
)
def test_tax_exempt_customer_pays_the_total_divided_by_1_05():
    """八(一) lines 1135-1136: 每月應繳總金額為電費總金額除以1.05."""
    bill = _bill(
        "high_voltage_2_tier",
        JULY,
        contract_capacities={"regular": 200},
        tax_exempt=True,
    )
    assert bill["total"] == pytest.approx(
        (HV["regular"][0] * 200 + HV_2_TIER_JULY) / 1.05
    )


@pytest.mark.xfail(
    strict=True,
    reason="not supported: no input for 高壓供電以低壓電表計度 and its 變壓器容量",
)
def test_low_voltage_meter_adds_transformer_losses():
    """八(二) lines 1137-1140: 低壓電表抄見度數 / 0.98 + 變壓器容量 x 720 x 0.01.

    0.25 kWh every quarter hour of July is 744 kWh read; a 500 kVA
    transformer adds 3,600 kWh."""
    inputs = tou.BillingInputs(
        contract_capacities={"regular": 200}, low_voltage_meter_transformer_kva=500
    )
    breakdown = tou.calculate_bill_breakdown(
        pd.Series(0.25, index=JULY), "high_voltage_2_tier", inputs
    )
    assert breakdown["details"]["usage_kwh"].sum() == pytest.approx(
        744 / 0.98 + 500 * 720 * 0.01
    )
