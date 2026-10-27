"""第四章 低壓電力電價, with amounts worked from its text.

Prices are from src/taipower_tou/data/詳細電價表.md (114/10/1): 非時間電價
lines 521-526, 二段式 lines 535-567, 三段式 lines 578-613, 電動車充換電設施電價
lines 627-637. tests/data/clauses/ch4.json names the clause each test checks.
"""

from datetime import datetime

import pandas as pd
import pytest

import taipower_tou as tou

JULY = pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min")
JANUARY = pd.date_range("2026-01-01", "2026-01-31 23:45", freq="15min")
# Wednesdays, neither an off-peak day. July 18 is a Saturday, July 19 a Sunday.
EVENING = {"summer": "2026-07-15 17:00", "non_summer": "2026-01-14 17:00"}

INSTALLED_PER_KW = 137.50  # lines 521, 537
INSTALLED_HOUSEHOLD = 105.00  # line 535
HOUSEHOLD = 262.50  # lines 538, 578, 627
REGULAR = {"summer": 236.20, "non_summer": 173.20}  # lines 523, 540, 579
NON_SUMMER = 173.20  # lines 525, 542
SEMI_PEAK_CONTRACT = 173.20  # line 581
WEEKEND = {"summer": 47.20, "non_summer": 34.60}  # lines 544-545, 583-584
EV_REGULAR = {"summer": 47.20, "non_summer": 34.60}  # line 628
EVENING_PRICE = {
    "low_voltage_power": 4.08,  # line 526
    "low_voltage_2_tier": 5.54,  # line 547, 尖峰 09:00~24:00
    "low_voltage_three_stage": 8.12,  # line 586, 尖峰 16:00~22:00
    "low_voltage_ev": 12.47,  # line 629, 尖峰 16:00~22:00
}


def _at(index, values):
    """0 all month except the values at their times."""
    series = pd.Series(0.0, index=index)
    for when, value in values.items():
        series.loc[pd.Timestamp(when)] = value
    return series


def _evening(season="summer", kwh=1.0):
    index = JULY if season == "summer" else JANUARY
    return _at(index, {EVENING[season]: kwh})


def _bill(plan, usage, **inputs):
    inputs = tou.BillingInputs(
        taipower_rounding=False, billing_cycle_months=1, **inputs
    )
    return tou.calculate_bill(usage, plan, inputs).iloc[0]


OFF_PEAK = {
    "low_voltage_2_tier": {"summer": 2.27, "non_summer": 2.15},  # lines 552-567
    "low_voltage_three_stage": {"summer": 2.23, "non_summer": 2.12},  # 598-613
    "low_voltage_ev": {"summer": 3.05, "non_summer": 2.90},  # lines 632-637
}


@pytest.mark.parametrize("plan", OFF_PEAK)
@pytest.mark.parametrize(
    ("day", "season"),
    [
        ("2026-01-01", "non_summer"),
        ("2026-02-16", "non_summer"),
        ("2026-04-04", "non_summer"),
        ("2026-06-19", "summer"),
        ("2026-09-28", "summer"),
    ],
    ids=["開國紀念日-thu", "春節-mon", "兒童節-sat", "端午節-fri", "教師節-mon"],
)
def test_lighting_off_peak_days_are_off_peak_all_day(plan, day, season):
    """四(二) 註1 line 616 and 四(三) 註 line 640: 離峰日參照表燈(住商)時間電價
    規定, the dates at lines 313-325. 週日及離峰日 are 離峰 all day."""
    context = tou.plan(plan).pricing_context(datetime.fromisoformat(f"{day} 17:00"))
    assert (context["period"], context["rate"]) == (
        "off_peak",
        pytest.approx(OFF_PEAK[plan][season]),
    )


@pytest.mark.parametrize(
    ("plan", "period", "rate"),
    [
        ("low_voltage_2_tier", "peak", 5.39),  # line 548
        ("low_voltage_three_stage", "semi_peak", 4.86),  # line 595
        ("low_voltage_ev", "peak", 12.14),  # line 630
    ],
)
def test_a_day_the_lighting_list_leaves_out_is_a_weekday(plan, period, rate):
    """2026-04-03 is the Friday before 兒童節 (4月4日, a Saturday). Lines 313-325
    do not list it, so it is priced as 週一至週五."""
    context = tou.plan(plan).pricing_context(datetime(2026, 4, 3, 17, 0))
    assert (context["period"], context["rate"]) == (period, pytest.approx(rate))


@pytest.mark.parametrize(
    ("plan", "inputs", "basic"),
    [
        (
            "low_voltage_power",
            {"basic_fee_inputs": {"裝置契約": 10}},
            INSTALLED_PER_KW * 10,
        ),
        (
            "low_voltage_2_tier",
            {"basic_fee_inputs": {"裝置契約": 10}},
            INSTALLED_HOUSEHOLD + INSTALLED_PER_KW * 10,
        ),
        (
            "low_voltage_2_tier",
            {"contract_capacities": {"regular": 10}},
            HOUSEHOLD + REGULAR["summer"] * 10,
        ),
        (
            "low_voltage_three_stage",
            {"contract_capacities": {"regular": 10}},
            HOUSEHOLD + REGULAR["summer"] * 10,
        ),
        (
            "low_voltage_ev",
            {"contract_capacities": {"regular": 20}},
            HOUSEHOLD + EV_REGULAR["summer"] * 20,
        ),
    ],
    ids=["power-installed", "two-stage-installed", "two-stage", "three-stage", "ev"],
)
def test_month_bill_is_basic_fee_plus_energy(plan, inputs, basic):
    """五(一) line 643: 每月電費為基本電費與流動電費之總和. 五(二)1, 五(三)1 and
    五(四)1: 流動電費 is the kWh at its time's price, here 2 kWh at 17:00 on a
    summer Wednesday."""
    bill = _bill(plan, _evening(kwh=2.0), **inputs)
    energy = 2.0 * EVENING_PRICE[plan]
    assert (bill["basic_cost"], bill["energy_cost"], bill["total"]) == pytest.approx(
        (basic, energy, basic + energy)
    )


@pytest.mark.parametrize(
    ("season", "expected"),
    [
        ("summer", REGULAR["summer"] * 20),
        ("non_summer", REGULAR["non_summer"] * 20 + NON_SUMMER * 5),
    ],
)
def test_low_voltage_power_demand_contract_basic_fee(season, expected):
    """五(二)2 lines 647-654: 夏月 基本電費＝夏月經常契約電價×經常契約容量; 非夏月
    adds 非夏月契約電價×非夏月契約容量."""
    bill = _bill(
        "low_voltage_power",
        _evening(season),
        contract_capacities={"regular": 20, "non_summer": 5},
    )
    assert bill["basic_cost"] == pytest.approx(expected)


TWO_STAGE_CONTRACTS = {
    "regular": 40,
    "non_summer": 10,
    "saturday_semi_peak": 20,
    "off_peak": 60,
}
TWO_STAGE_WEEKEND = (20 + 60) - (40 + 10) * 0.5


@pytest.mark.parametrize(
    ("index", "capacities", "expected"),
    [
        (
            JULY,
            TWO_STAGE_CONTRACTS,
            HOUSEHOLD + REGULAR["summer"] * 40 + WEEKEND["summer"] * TWO_STAGE_WEEKEND,
        ),
        (
            JANUARY,
            TWO_STAGE_CONTRACTS,
            HOUSEHOLD
            + REGULAR["non_summer"] * 40
            + NON_SUMMER * 10
            + WEEKEND["non_summer"] * TWO_STAGE_WEEKEND,
        ),
        (
            JULY,
            {"regular": 40, "saturday_semi_peak": 10},
            HOUSEHOLD + REGULAR["summer"] * 40,
        ),
        (JULY, {"off_peak": 50}, HOUSEHOLD + WEEKEND["summer"] * 50),
    ],
    ids=["summer", "non-summer", "negative-weekend-term-is-0", "weekend-only"],
)
def test_two_stage_demand_contract_basic_fee(index, capacities, expected):
    """五(三)2(1) lines 663-689: 基本電費按戶及按契約容量計算, 週六半尖峰或離峰
    契約 on (週六半尖峰 + 離峰) - (經常 + 非夏月) x 0.5 and 0 when negative.
    A customer with only a 離峰契約 pays 按戶 and that contract (lines 666-669)."""
    bill = _bill(
        "low_voltage_2_tier",
        pd.Series(0.25, index=index),
        contract_capacities=capacities,
    )
    assert bill["basic_cost"] == pytest.approx(expected)


THREE_STAGE_CONTRACTS = {
    "regular": 40,
    "semi_peak": 10,
    "saturday_semi_peak": 10,
    "off_peak": 50,
}
THREE_STAGE_WEEKEND = (10 + 50) - (40 + 10) * 0.5


@pytest.mark.parametrize(
    ("index", "capacities", "expected"),
    [
        (
            JULY,
            THREE_STAGE_CONTRACTS,
            HOUSEHOLD
            + REGULAR["summer"] * 40
            + SEMI_PEAK_CONTRACT * 10
            + WEEKEND["summer"] * THREE_STAGE_WEEKEND,
        ),
        (
            JANUARY,
            THREE_STAGE_CONTRACTS,
            HOUSEHOLD
            + REGULAR["non_summer"] * 40
            + SEMI_PEAK_CONTRACT * 10
            + WEEKEND["non_summer"] * THREE_STAGE_WEEKEND,
        ),
        (
            JULY,
            {"regular": 40, "semi_peak": 10, "off_peak": 20},
            HOUSEHOLD + REGULAR["summer"] * 40 + SEMI_PEAK_CONTRACT * 10,
        ),
    ],
    ids=["summer", "non-summer", "negative-weekend-term-is-0"],
)
def test_three_stage_demand_contract_basic_fee(index, capacities, expected):
    """五(三)2(2) lines 690-703: 按戶 plus 當月經常契約電價×經常契約容量＋當月
    半尖峰契約電價×半尖峰契約容量＋週六半尖峰或離峰契約電價×〔(週六半尖峰＋離峰)
    －(經常＋半尖峰)×0.5〕, the last term 0 when negative."""
    bill = _bill(
        "low_voltage_three_stage",
        pd.Series(0.25, index=index),
        contract_capacities=capacities,
    )
    assert bill["basic_cost"] == pytest.approx(expected)


def test_three_stage_weekend_only_contract_pays_no_household_fee():
    """五(三)2(2) lines 693-697: 用戶僅在週六半尖峰時間或離峰時間用電而申請...
    者，基本電費按週六半尖峰契約容量與離峰契約容量計算. 二段式 says 按戶及按
    週六半尖峰契約容量與離峰契約容量 (lines 668-669); 三段式 leaves 按戶 out."""
    bill = _bill(
        "low_voltage_three_stage",
        pd.Series(0.25, index=JULY),
        contract_capacities={"off_peak": 50},
    )
    assert bill["basic_cost"] == pytest.approx(WEEKEND["summer"] * 50)


@pytest.mark.parametrize("season", ["summer", "non_summer"])
def test_ev_basic_fee_is_per_household_and_regular_contract(season):
    """五(四)1 lines 706-710: 基本電費按戶及按契約容量計算, 基本電費＝夏月
    (非夏月)經常契約電價×經常契約容量."""
    bill = _bill(
        "low_voltage_ev", _evening(season), contract_capacities={"regular": 20}
    )
    assert bill["basic_cost"] == pytest.approx(HOUSEHOLD + EV_REGULAR[season] * 20)


@pytest.mark.parametrize(
    ("plan", "basic"),
    [
        ("low_voltage_power", REGULAR["summer"] * 20),
        ("low_voltage_2_tier", HOUSEHOLD + REGULAR["summer"] * 20),
        ("low_voltage_three_stage", HOUSEHOLD + REGULAR["summer"] * 20),
        ("low_voltage_ev", HOUSEHOLD + EV_REGULAR["summer"] * 20),
    ],
)
def test_demand_contract_month_without_use_pays_half(plan, basic):
    """五(五) lines 712-715: 按需量契約容量計費之用戶當月份未用電者（抄見度數與
    最高需量均為0），則基本電費按核定電價50%計算."""
    idle = pd.Series(0.0, index=JULY)
    bill = _bill(plan, idle, contract_capacities={"regular": 20}, demand_kw=idle)
    assert bill["total"] == pytest.approx(0.5 * basic)


@pytest.mark.parametrize(
    ("plan", "inputs", "basic"),
    [
        (
            "low_voltage_power",
            {"basic_fee_inputs": {"裝置契約": 20}},
            INSTALLED_PER_KW * 20,
        ),
        (
            "low_voltage_2_tier",
            {"basic_fee_inputs": {"裝置契約": 20}},
            INSTALLED_PER_KW * 20,
        ),
        (
            "low_voltage_2_tier",
            {"contract_capacities": {"regular": 30}},
            REGULAR["summer"] * 30,
        ),
        (
            "low_voltage_three_stage",
            {"contract_capacities": {"regular": 30}},
            REGULAR["summer"] * 30,
        ),
        (
            "low_voltage_ev",
            {"contract_capacities": {"regular": 30}},
            EV_REGULAR["summer"] * 30,
        ),
    ],
    ids=[
        "power-installed-20",
        "two-stage-installed-20",
        "two-stage-30",
        "three-30",
        "ev-30",
    ],
)
@pytest.mark.parametrize(
    ("power_factor", "share"),
    [(70, 0.01), (90, -0.01), (95, -0.015), (99, -0.015)],
)
def test_power_factor_adjusts_three_phase_bills_from_80_percent(
    plan, inputs, basic, power_factor, share
):
    """六 lines 729-734: 以三相供應, 裝置契約 20 瓩以上 or 需量契約 30 瓩以上:
    該月份電費 changes 0.1% per 1% from 80%, no discount above 95%. 五(三)3
    line 704 and 五(四)2 line 711: 按戶計收之基本電費，不列計功率因數調整費,
    so basic leaves 按戶 out."""
    bill = _bill(
        plan, _evening(), meter_phase="three", power_factor=power_factor, **inputs
    )
    assert bill["adjustment"] == pytest.approx(share * (basic + EVENING_PRICE[plan]))


@pytest.mark.parametrize(
    ("plan", "inputs", "phase"),
    [
        ("low_voltage_power", {"basic_fee_inputs": {"裝置契約": 19}}, "three"),
        ("low_voltage_power", {"basic_fee_inputs": {"裝置契約": 20}}, "single"),
        ("low_voltage_2_tier", {"basic_fee_inputs": {"裝置契約": 19}}, "three"),
        ("low_voltage_2_tier", {"contract_capacities": {"regular": 29}}, "three"),
        ("low_voltage_2_tier", {"contract_capacities": {"regular": 30}}, "single"),
        ("low_voltage_ev", {"contract_capacities": {"regular": 29}}, "three"),
    ],
    ids=[
        "power-installed-19",
        "power-installed-single-phase",
        "two-stage-installed-19",
        "two-stage-29",
        "two-stage-single-phase",
        "ev-29",
    ],
)
def test_power_factor_leaves_small_and_single_phase_bills_alone(plan, inputs, phase):
    """六 lines 730-731: only 以三相供應之用戶，裝置契約容量在20瓩以上或需量契約
    容量在30瓩以上者 have 功率因數 adjusted."""
    bill = _bill(plan, _evening(), meter_phase=phase, power_factor=70, **inputs)
    assert bill["adjustment"] == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("plan", "household"),
    [("low_voltage_power", 0.0), ("low_voltage_2_tier", INSTALLED_HOUSEHOLD)],
)
def test_installed_contract_metered_under_its_capacity_keeps_the_installed_price(
    plan, household
):
    """七(一)2 line 739-740: 用戶用電發生異常時，得裝表計量其負載情形，但仍按
    裝置契約電價計費. A 9 kW demand on a 10 kW 裝置契約 adds nothing."""
    bill = _bill(
        plan,
        _evening(kwh=2.0),
        basic_fee_inputs={"裝置契約": 10},
        demand_kw=_at(JULY, {EVENING["summer"]: 9.0}),
    )
    expected = household + INSTALLED_PER_KW * 10 + 2.0 * EVENING_PRICE[plan]
    assert bill["total"] == pytest.approx(expected)


@pytest.mark.parametrize("plan", ["low_voltage_power", "low_voltage_2_tier"])
def test_installed_contract_demand_over_capacity_needs_a_demand_contract(plan):
    """七(一)2 lines 740-741: 如用電最高需量超出原裝置契約容量時，自超約月份起改按
    需量契約電價計費. The text does not give the new 需量契約容量, so the bill
    warns and asks for it instead of guessing one."""
    with pytest.warns(UserWarning, match="需量契約電價"):
        _bill(
            plan,
            _evening(kwh=2.0),
            basic_fee_inputs={"裝置契約": 10},
            demand_kw=_at(JULY, {EVENING["summer"]: 11.0}),
        )


def _demand(index, peaks):
    """10 kW all month, with the kW in peaks at (day, hour) for that hour."""
    demand = pd.Series(10.0, index=index)
    for (day, hour), kw in peaks.items():
        demand[(index.day == day) & (index.hour == hour)] = kw
    return demand


def _over_contract(plan, index, capacities, peaks):
    bill = _bill(
        plan,
        pd.Series(0.25, index=index),
        contract_capacities=capacities,
        demand_kw=_demand(index, peaks),
    )
    return bill["adjustment"]


@pytest.mark.parametrize(
    ("index", "capacities", "peaks", "expected"),
    [
        (
            JULY,
            {"regular": 20, "non_summer": 5},
            {(15, 17): 21},
            1 * 2 * REGULAR["summer"],
        ),
        (
            JANUARY,
            {"regular": 20, "non_summer": 5},
            {(14, 17): 26},
            1 * 2 * REGULAR["non_summer"],
        ),
        (JULY, {"regular": 20}, {(19, 3): 25}, (2 * 2 + 3 * 3) * REGULAR["summer"]),
    ],
    ids=["summer-ignores-non-summer", "non-summer-counts-it", "any-hour-over-10pct"],
)
def test_low_voltage_power_over_contract_fee(index, capacities, peaks, expected):
    """七(二)1(1) lines 745-750: 夏月超約瓩數＝當月用電最高需量－經常契約容量;
    非夏月 takes off (經常 + 非夏月). 七(二)2 lines 787-791: 2x up to 10% of the
    contract, 3x above, at the 經常契約 price."""
    assert _over_contract(
        "low_voltage_power", index, capacities, peaks
    ) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("index", "capacities", "peaks", "expected"),
    [
        (JULY, {"regular": 50}, {(15, 17): 53}, 3 * 2 * REGULAR["summer"]),
        (JULY, {"regular": 50}, {(15, 17): 60}, (5 * 2 + 5 * 3) * REGULAR["summer"]),
        (
            JULY,
            {"regular": 50, "non_summer": 10},
            {(15, 17): 53},
            3 * 2 * REGULAR["summer"],
        ),
        (
            JANUARY,
            {"regular": 50, "non_summer": 10},
            {(14, 17): 62},
            2 * 2 * REGULAR["non_summer"],
        ),
        (
            JULY,
            {"regular": 50, "saturday_semi_peak": 10},
            {(18, 10): 63},
            3 * 2 * WEEKEND["summer"],
        ),
        (
            JULY,
            {"regular": 50, "saturday_semi_peak": 5, "off_peak": 10},
            {(19, 12): 67},
            2 * 2 * WEEKEND["summer"],
        ),
        (
            JULY,
            {"regular": 50},
            {(15, 17): 51, (18, 10): 53, (15, 3): 54},
            (1 * REGULAR["summer"] + 2 * WEEKEND["summer"] + 1 * WEEKEND["summer"]) * 2,
        ),
    ],
    ids=[
        "a-peak-within-10pct",
        "a-peak-over-10pct",
        "a-summer-ignores-non-summer",
        "b-non-summer-counts-it",
        "c-saturday",
        "d-off-peak",
        "e-no-double-count",
    ],
)
def test_two_stage_over_contract_fee(index, capacities, peaks, expected):
    """七(二)1(2) lines 751-765, a-e. The 1, 3 and 4 kW excesses at 尖峰, 週六半尖峰
    and 離峰 in the last case are counted 1, 3-1 and 4-3. 七(二)2 lines 787-791:
    each at its own 契約電價 (the package's reading of 依適用電價), 2x up to 10%
    of the contract and 3x above."""
    assert _over_contract(
        "low_voltage_2_tier", index, capacities, peaks
    ) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("capacities", "peaks", "expected"),
    [
        ({"regular": 50}, {(15, 17): 53}, 3 * 2 * REGULAR["summer"]),
        ({"regular": 50, "semi_peak": 10}, {(15, 10): 63}, 3 * 2 * SEMI_PEAK_CONTRACT),
        (
            {"regular": 50, "semi_peak": 10, "saturday_semi_peak": 5},
            {(18, 10): 68},
            3 * 2 * WEEKEND["summer"],
        ),
        ({"regular": 50, "off_peak": 10}, {(19, 12): 62}, 2 * 2 * WEEKEND["summer"]),
        (
            {"regular": 50},
            {(15, 17): 51, (15, 10): 53, (18, 10): 54, (15, 3): 55},
            (
                1 * REGULAR["summer"]
                + 2 * SEMI_PEAK_CONTRACT
                + 1 * WEEKEND["summer"]
                + 1 * WEEKEND["summer"]
            )
            * 2,
        ),
    ],
    ids=["a-peak", "b-semi-peak", "c-saturday", "d-off-peak", "e-no-double-count"],
)
def test_three_stage_over_contract_fee(capacities, peaks, expected):
    """七(二)1(3) lines 766-784, a-e. In the last case the excesses 1, 3, 4, 5 kW
    are counted 1, 3-1, 4-3 and 5-4. 七(二)2: each at its own 契約電價, 2x."""
    assert _over_contract(
        "low_voltage_three_stage", JULY, capacities, peaks
    ) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("index", "peaks", "expected"),
    [
        (JULY, {(15, 17): 21}, 1 * 2 * EV_REGULAR["summer"]),
        (JULY, {(15, 3): 22}, 2 * 2 * EV_REGULAR["summer"]),
        (JULY, {(15, 17): 21, (15, 3): 22}, 2 * 2 * EV_REGULAR["summer"]),
        (JULY, {(15, 17): 25}, (2 * 2 + 3 * 3) * EV_REGULAR["summer"]),
        (JANUARY, {(14, 17): 21}, 1 * 2 * EV_REGULAR["non_summer"]),
    ],
    ids=["peak", "off-peak", "month-maximum", "over-10pct", "non-summer"],
)
def test_ev_over_contract_fee(index, peaks, expected):
    """七(二)1(4) lines 785-786: 超約瓩數＝當月用電最高需量－經常契約容量, the
    month's highest demand at any time, so 21 kW at 尖峰 and 22 kW at 離峰 are
    2 kW over, not 1 + 2. 七(二)2: 2x up to 10%, 3x above."""
    assert _over_contract(
        "low_voltage_ev", index, {"regular": 20}, peaks
    ) == pytest.approx(expected)


def test_power_factor_discount_leaves_the_over_contract_fee_out():
    """七(二)2 lines 787-789: 超出部分...計收基本電費，不給予功率因數扣減. 90%
    takes 1% off 經常契約 and energy (六), not off the 3 kW 超約 fee."""
    bill = _bill(
        "low_voltage_2_tier",
        _evening(),
        contract_capacities={"regular": 50},
        demand_kw=_at(JULY, {EVENING["summer"]: 53.0}),
        meter_phase="three",
        power_factor=90,
    )
    over = 3 * 2 * REGULAR["summer"]
    discount = 0.01 * (REGULAR["summer"] * 50 + EVENING_PRICE["low_voltage_2_tier"])
    assert bill["adjustment"] == pytest.approx(over - discount)


@pytest.mark.parametrize(
    ("capacities", "own_time", "own_price"),
    [
        ({"off_peak": 50}, "2026-07-19 12:00", 2.27),  # Sunday 離峰, line 567
        ({"saturday_semi_peak": 50}, "2026-07-18 10:00", 2.76),  # line 555
    ],
    ids=["off-peak-only", "saturday-only"],
)
def test_weekend_only_contract_pays_more_for_use_outside_its_times(
    capacities, own_time, own_price
):
    """八(六) lines 811-815: 僅訂週六半尖峰或離峰契約容量之用戶 using power at
    other times pays 4.8x the time's 基本電費單價 on that 最高需量 and 1.6x its
    流動電費單價. 2 kWh at 8 kW on a Wednesday at 17:00 (尖峰) is 4.8 x 經常契約
    (line 540) x 8 kW and 1.6 x 5.54 (line 547) x 2 kWh. The 50 kW contract pays
    按戶 and its 契約電價 as in 五(三)2(1)."""
    usage = _at(JULY, {own_time: 10.0, EVENING["summer"]: 2.0})
    demand = _at(JULY, {own_time: 40.0, EVENING["summer"]: 8.0})
    bill = _bill(
        "low_voltage_2_tier", usage, contract_capacities=capacities, demand_kw=demand
    )
    expected = (
        HOUSEHOLD
        + WEEKEND["summer"] * 50
        + 4.8 * REGULAR["summer"] * 8
        + 10.0 * own_price
        + 1.6 * EVENING_PRICE["low_voltage_2_tier"] * 2.0
    )
    assert bill["total"] == pytest.approx(expected)


@pytest.mark.xfail(strict=True, reason="not supported: no input for 儲冷式空調 usage")
def test_thermal_storage_off_peak_energy_is_billed_at_60_percent():
    """五(八) lines 723-724: 儲冷式空調系統冷凍機...其離峰時間用電之流動電費按適用
    電價60%計收. 10 kWh of it at 03:00 (離峰 2.27, line 552), 1 kWh else at 17:00."""
    storage = _at(JULY, {"2026-07-15 03:00": 10.0})
    usage = storage + _evening()
    inputs = tou.BillingInputs(
        taipower_rounding=False,
        contract_capacities={"regular": 20},
        thermal_storage_kwh=storage,
        billing_cycle_months=1,
    )
    bill = tou.calculate_bill(usage, "low_voltage_2_tier", inputs).iloc[0]
    assert bill["energy_cost"] == pytest.approx(
        0.6 * 2.27 * 10 + EVENING_PRICE["low_voltage_2_tier"]
    )


@pytest.mark.xfail(
    strict=True, reason="not supported: no input for a customer exempt from 營業稅"
)
def test_tax_exempt_customer_pays_the_total_over_1_05():
    """八(一) lines 793-794: 依法免計營業稅用戶每月應繳總金額為電費總金額除以1.05."""
    inputs = tou.BillingInputs(
        taipower_rounding=False,
        basic_fee_inputs={"裝置契約": 10},
        tax_exempt=True,
        billing_cycle_months=1,
    )
    bill = tou.calculate_bill(_evening(), "low_voltage_power", inputs).iloc[0]
    expected = INSTALLED_PER_KW * 10 + EVENING_PRICE["low_voltage_power"]
    assert bill["total"] == pytest.approx(expected / 1.05)


@pytest.mark.parametrize(
    ("meter_voltage_v", "metered", "billed"),
    [
        (380, 1000.0, 1000.0 + (100 - 50) * 720 * 0.01),
        (11400, 10000.0, 0.98 * (10000.0 - 100 * 720 * 0.01)),
        (11400, 5000.0, 0.98 * (5000.0 - 5000.0 * 0.10)),
    ],
    ids=["low-voltage-meter", "high-voltage-meter", "iron-loss-capped-at-10pct"],
)
@pytest.mark.xfail(
    strict=True, reason="not supported: no input for the supply transformer's kVA"
)
def test_high_voltage_supply_counts_transformer_losses(
    meter_voltage_v, metered, billed
):
    """八(三) lines 800-805, with 第三章 七(三)(四) lines 477-484. 低壓電表:
    抄見度數＋(變壓器容量－契約容量)×720×0.01. 高壓電表: 0.98×(抄見度數－
    變壓器容量×720×0.01), the 鐵損 at most 10% of 抄見度數. A 100 kVA
    transformer, 50 kW 裝置契約, at the 非夏月 3.87 (line 526)."""
    inputs = tou.BillingInputs(
        taipower_rounding=False,
        basic_fee_inputs={"裝置契約": 50},
        meter_voltage_v=meter_voltage_v,
        transformer_kva=100,
        billing_cycle_months=1,
    )
    usage = pd.Series(metered / len(JANUARY), index=JANUARY)
    bill = tou.calculate_bill(usage, "low_voltage_power", inputs).iloc[0]
    assert bill["energy_cost"] == pytest.approx(3.87 * billed)


@pytest.mark.xfail(
    strict=True,
    reason="not supported: no input for 充換電設備 and 附屬設備 capacity",
)
def test_ev_use_that_stops_qualifying_is_billed_two_stage():
    """八(七) lines 816-819: 如實際用電不符本章第一條第二款規定時，自不符規定之月份
    起改按低壓電力二段式時間電價計費. 一(二) lines 501-503 needs 充換電設備容量
    超過附屬設備容量; 8 kW of chargers and 12 kW of the rest do not."""
    inputs = tou.BillingInputs(
        taipower_rounding=False,
        contract_capacities={"regular": 20},
        ev_charging_kw=8,
        ev_auxiliary_kw=12,
        billing_cycle_months=1,
    )
    bill = tou.calculate_bill(_evening(), "low_voltage_ev", inputs).iloc[0]
    expected = HOUSEHOLD + REGULAR["summer"] * 20 + EVENING_PRICE["low_voltage_2_tier"]
    assert bill["total"] == pytest.approx(expected)
