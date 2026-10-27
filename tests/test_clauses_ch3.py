"""第三章 表燈(住商)電價 clauses that no other test checks.

Amounts are worked from src/taipower_tou/data/詳細電價表.md (114/10/1) with the
prices as constants. tests/data/clauses/ch3.json names the tests of every
clause in the chapter.
"""

from datetime import datetime

import pandas as pd
import pytest

import taipower_tou as tou

JULY = pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min")
JANUARY = pd.date_range("2026-01-01", "2026-01-31 23:45", freq="15min")
# July 2026 has no 離峰日 (lines 313-325).
WEEKDAYS, SATURDAYS, SUNDAYS = 23, 4, 4

# 1 kWh in every hour of July 2026.
# 簡易型二段式, lines 191-202: weekday 尖峰 09:00-24:00 5.16, 離峰 2.06.
SIMPLE_2_JULY = (
    WEEKDAYS * 15 * 5.16 + (WEEKDAYS * 9 + (SATURDAYS + SUNDAYS) * 24) * 2.06
)
# 簡易型三段式, lines 212-224: 尖峰 16:00-22:00 7.13, 半尖峰 09:00-16:00 and
# 22:00-24:00 4.69, 離峰 2.06.
SIMPLE_3_JULY = (
    WEEKDAYS * 6 * 7.13
    + WEEKDAYS * 9 * 4.69
    + (WEEKDAYS * 9 + (SATURDAYS + SUNDAYS) * 24) * 2.06
)
# 標準型二段式, lines 242-263: weekday 尖峰 09:00-24:00 5.54, Saturday 半尖峰
# 09:00-24:00 2.76, 離峰 2.27.
STANDARD_2_JULY = (
    WEEKDAYS * 15 * 5.54
    + SATURDAYS * 15 * 2.76
    + ((WEEKDAYS + SATURDAYS) * 9 + SUNDAYS * 24) * 2.27
)
# 標準型三段式, lines 282-306: 尖峰 16:00-22:00 8.12, weekday 半尖峰 5.02,
# Saturday 半尖峰 09:00-24:00 2.50, 離峰 2.23.
STANDARD_3_JULY = (
    WEEKDAYS * 6 * 8.12
    + WEEKDAYS * 9 * 5.02
    + SATURDAYS * 15 * 2.50
    + ((WEEKDAYS + SATURDAYS) * 9 + SUNDAYS * 24) * 2.23
)
# 住宅用 夏月, lines 138-144: 744 kWh.
RESIDENTIAL_JULY = 120 * 1.78 + 210 * 2.55 + 170 * 3.80 + 200 * 5.14 + 44 * 6.44

SIMPLE_HOUSEHOLD = 75.00  # lines 189, 210
HOUSEHOLD_THREE = 262.50  # lines 236, 276
REGULAR = {"summer": 236.20, "non_summer": 173.20}  # lines 237, 277
NON_SUMMER_CONTRACT = 173.20  # line 238
SEMI_PEAK_CONTRACT = 173.20  # line 278
WEEKEND = {"summer": 47.20, "non_summer": 34.60}  # lines 240-241, 280-281


def _days(start, end, kwh):
    days = pd.date_range(start, end, freq="D")
    return pd.Series(kwh / len(days), index=days)


def _meter(phase="single", ampere=10, voltage=None, months=1, **extra):
    return tou.BillingInputs(
        meter_phase=phase,
        meter_voltage_v=voltage or (220 if phase == "three" else 110),
        meter_ampere=ampere,
        billing_cycle_months=months,
        **extra,
    )


def _bill(plan, index, kwh=0.25, demand=None, **inputs):
    usage = kwh if isinstance(kwh, pd.Series) else pd.Series(kwh, index=index)
    if demand is not None:
        inputs["demand_kw"] = demand
    inputs.setdefault("billing_cycle_months", 1)
    return tou.calculate_bill(usage, plan, tou.BillingInputs(**inputs)).iloc[0]


def _contracts(plan, **kw):
    """Every contract of a 標準型 plan, 0 kW unless given."""
    second = "semi_peak" if plan == "lighting_standard_3_tier" else "non_summer"
    return {"regular": 0, second: 0, "saturday_semi_peak": 0, "off_peak": 0, **kw}


def _by_hour(index, values, base=0.0):
    """base all month, and values[(day, hour)] in each quarter of that hour."""
    series = pd.Series(base, index=index)
    for (day, hour), value in values.items():
        series[(index.day == day) & (index.hour == hour)] = value
    return series


def _sundays(index):
    """1 kWh an hour on Sundays, which are 離峰 on every plan."""
    return pd.Series(0.25, index=index).where(index.day_of_week == 6, 0.0)


@pytest.mark.parametrize(
    ("plan", "kwh", "expected"),
    [
        ("residential_non_tou", 661, 240 * 1.78 + 420 * 2.26 + 3.13),
        ("lighting_non_business_tiered", 240, 240 * 1.78),
        ("lighting_non_business_tiered", 241, 240 * 1.78 + 2.26),
        ("lighting_non_business_tiered", 661, 240 * 1.78 + 420 * 2.26 + 3.13),
        ("lighting_business_tiered", 660, 660 * 2.28),
        ("lighting_business_tiered", 661, 660 * 2.28 + 3.10),
        ("lighting_business_tiered", 1401, 660 * 2.28 + 740 * 3.10 + 3.61),
    ],
)
def test_two_month_bill_doubles_every_tier_limit(plan, kwh, expected):
    """Lines 145-146, 163-164, 175-176 and 347-348: 2個月抄表 doubles each
    tier's kWh. 非夏月 prices, lines 138-144, 156-162 and 170-174."""
    usage = _days("2026-01-01", "2026-02-28", kwh)
    bill = tou.calculate_bill(usage, plan, _meter(months=2))
    assert bill["energy_cost"].iloc[0] == pytest.approx(expected)


@pytest.mark.xfail(strict=True, reason="not supported: 公用路燈 input")
def test_public_street_lighting_pays_half_the_non_business_prices():
    """Line 165: 公用路燈照上表單價減收50%. 600 kWh in January, lines 156-162."""
    usage = _days("2026-01-01", "2026-01-31", 600)
    inputs = _meter(public_street_lighting=True)
    bill = tou.calculate_bill(usage, "lighting_non_business_tiered", inputs)
    expected = 0.5 * (120 * 1.78 + 210 * 2.26 + 170 * 3.13 + 100 * 4.24)
    assert bill["total"].iloc[0] == pytest.approx(expected)


TIERED_200_KWH = {
    "residential_non_tou": {
        "summer": 120 * 1.78 + 80 * 2.55,
        "non_summer": 120 * 1.78 + 80 * 2.26,
    },
    "lighting_non_business_tiered": {
        "summer": 120 * 1.78 + 80 * 2.55,
        "non_summer": 120 * 1.78 + 80 * 2.26,
    },
    "lighting_business_tiered": {"summer": 200 * 2.71, "non_summer": 200 * 2.28},
}


@pytest.mark.parametrize("plan", TIERED_200_KWH)
@pytest.mark.parametrize(
    ("start", "end", "season"),
    [
        ("2026-05-01", "2026-05-31", "non_summer"),
        ("2026-06-01", "2026-06-30", "summer"),
        ("2026-09-01", "2026-09-30", "summer"),
        ("2026-10-01", "2026-10-31", "non_summer"),
    ],
    ids=["may", "june", "september", "october"],
)
def test_tiered_summer_runs_june_1_to_september_30(plan, start, end, season):
    """Lines 135-137, 153-155 and 167-169: 夏月 is 6月1日至9月30日."""
    bill = tou.calculate_bill(_days(start, end, 200), plan, _meter())
    assert bill["energy_cost"].iloc[0] == pytest.approx(TIERED_200_KWH[plan][season])


# A weekday's 10:00 price, (夏月, 非夏月).
WEEKDAY_10AM = {
    "residential_simple_2_tier": (5.16, 4.93),  # lines 192, 194 尖峰
    "residential_simple_3_tier": (4.69, 4.48),  # lines 215, 218 半尖峰
    "lighting_standard_2_tier": (5.54, 5.39),  # lines 243-244 尖峰
    "lighting_standard_3_tier": (5.02, 4.86),  # lines 286-288 半尖峰
}


@pytest.mark.parametrize("plan", WEEKDAY_10AM)
def test_tou_summer_runs_june_1_to_september_30(plan):
    """Lines 186-187, 207-208, 232-233 and 272-273: 夏月 is 6月1日至9月30日."""
    summer, non_summer = WEEKDAY_10AM[plan]
    cases = [
        (datetime(2026, 5, 29, 10), non_summer),
        (datetime(2026, 6, 1, 10), summer),
        (datetime(2026, 9, 30, 10), summer),
        (datetime(2026, 10, 1, 10), non_summer),
    ]
    tariff = tou.plan(plan)
    assert [tariff.pricing_context(when)["rate"] for when, _ in cases] == [
        pytest.approx(rate) for _, rate in cases
    ]


# The all-day 離峰 price of 週六、週日及離峰日, (夏月, 非夏月).
ALL_DAY_OFF_PEAK = {
    "residential_simple_2_tier": (2.06, 1.99),  # line 202
    "residential_simple_3_tier": (2.06, 1.99),  # line 224
    "lighting_standard_2_tier": (2.27, 2.15),  # line 263
    "lighting_standard_3_tier": (2.23, 2.12),  # line 306
}
# Lines 314-325 in 2026. 春節 runs from the day before 除夕 (2/15) to 農曆1月5日
# (2/21). 民族掃墓節 is 4/5, 端午節 6/19 and 中秋節 9/25.
OFF_PEAK_DAYS_2026 = [
    "2026-01-01",
    "2026-02-15",
    "2026-02-16",
    "2026-02-17",
    "2026-02-18",
    "2026-02-19",
    "2026-02-20",
    "2026-02-21",
    "2026-02-28",
    "2026-04-04",
    "2026-04-05",
    "2026-05-01",
    "2026-06-19",
    "2026-09-25",
    "2026-09-28",
    "2026-10-10",
    "2026-10-25",
    "2026-12-25",
]
SUMMER_OFF_PEAK_DAYS = {"2026-06-19", "2026-09-25", "2026-09-28"}


@pytest.mark.parametrize("plan", ALL_DAY_OFF_PEAK)
def test_listed_off_peak_days_are_off_peak_all_day(plan):
    summer, non_summer = ALL_DAY_OFF_PEAK[plan]
    tariff = tou.plan(plan)
    wrong = []
    for day in OFF_PEAK_DAYS_2026:
        rate = summer if day in SUMMER_OFF_PEAK_DAYS else non_summer
        for hour in (10, 17):
            context = tariff.pricing_context(datetime.fromisoformat(f"{day}T{hour}:00"))
            if (context["period"], round(context["rate"], 4)) != ("off_peak", rate):
                wrong.append((day, hour, context["period"], context["rate"]))
    assert wrong == []


@pytest.mark.parametrize(
    "day", ["2026-02-27", "2026-04-03", "2026-04-06", "2026-10-09", "2026-10-26"]
)
def test_days_off_work_missing_from_the_list_bill_as_weekdays(day):
    """Line 313: 離峰日如下表所列日期, so a 補假 not in the list is a weekday."""
    when = datetime.fromisoformat(f"{day}T10:00")
    rates = {
        plan: tou.plan(plan).pricing_context(when)["rate"] for plan in WEEKDAY_10AM
    }
    assert rates == {
        plan: pytest.approx(non_summer)
        for plan, (_, non_summer) in WEEKDAY_10AM.items()
    }


@pytest.mark.parametrize(
    ("plan", "start", "end", "kwh", "phase", "expected"),
    [
        ("lighting_business_tiered", "2026-01-01", "2026-01-31", 0, "three", 60 * 2.28),
        ("lighting_business_tiered", "2026-07-01", "2026-07-31", 0, "three", 60 * 2.71),
        (
            "lighting_non_business_tiered",
            "2026-01-01",
            "2026-01-31",
            0,
            "three",
            60 * 1.78,
        ),
        ("residential_non_tou", "2026-01-01", "2026-01-31", 30, "three", 60 * 1.78),
        ("lighting_business_tiered", "2026-01-01", "2026-01-31", 30, "single", 100.0),
        (
            "lighting_business_tiered",
            "2026-01-01",
            "2026-01-31",
            50,
            "single",
            50 * 2.28,
        ),
    ],
    ids=[
        "business-empty",
        "business-empty-summer",
        "non-business-empty",
        "residential-30-kwh",
        "business-68.40-is-raised-to-100",
        "business-114-stays",
    ],
)
def test_minimum_usage_and_fee_for_each_tiered_plan(
    plan, start, end, kwh, phase, expected
):
    """Lines 333-339: under 底度 (6 kWh an ampere three-phase, 10 A at most)
    the bill is 底度 at the plan's prices, and a bill under 100 元 is 100 元."""
    bill = tou.calculate_bill(_days(start, end, kwh), plan, _meter(phase=phase))
    assert bill["total"].iloc[0] == pytest.approx(expected)


@pytest.mark.parametrize(("ampere", "minimum_kwh"), [(5, 10), (10, 20), (30, 20)])
def test_single_phase_minimum_usage_is_2_kwh_an_ampere_up_to_10_amperes(
    ampere, minimum_kwh
):
    """Lines 333-337: an empty month is billed its 底度 at 1.78 (line 138), and
    the bill is raised to 100 元."""
    usage = _days("2026-01-01", "2026-01-31", 0)
    bill = tou.calculate_bill(usage, "residential_non_tou", _meter(ampere=ampere))
    assert (bill["energy_cost"].iloc[0], bill["total"].iloc[0]) == (
        pytest.approx(minimum_kwh * 1.78),
        pytest.approx(100.0),
    )


@pytest.mark.parametrize(
    ("phase", "voltage", "ampere", "expected"),
    [
        ("single", 3300, 1, 60 * 1.78),
        ("single", 3300, 11, 120 * 1.78 + 210 * 2.26 + 170 * 3.13 + 160 * 4.24),
        ("single", 6600, 1, 120 * 1.78),
        ("three", 3300, 1, 100 * 1.78),
        ("three", 5700, 1, 120 * 1.78 + 60 * 2.26),
        ("three", 11400, 1, 120 * 1.78 + 210 * 2.26 + 30 * 3.13),
    ],
    ids=str,
)
def test_high_voltage_meter_minimum_usage(phase, voltage, ampere, expected):
    """Lines 340-346: 高壓電表 底度 per ampere is 60 or 120 kWh single-phase
    and 100, 180 or 360 kWh three-phase, with no 10 A limit. 非夏月 prices,
    lines 138-144."""
    usage = _days("2026-01-01", "2026-01-31", 0)
    inputs = _meter(phase=phase, ampere=ampere, voltage=voltage)
    bill = tou.calculate_bill(usage, "residential_non_tou", inputs)
    assert bill["total"].iloc[0] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("plan", "energy"),
    [
        ("residential_simple_2_tier", SIMPLE_2_JULY),
        ("residential_simple_3_tier", SIMPLE_3_JULY),
    ],
)
def test_simple_tou_bill_is_the_household_fee_plus_energy(plan, energy):
    """Lines 350-356: 每月電費為基本電費與流動電費之總和, 基本電費按戶計收."""
    bill = _bill(plan, JULY)
    assert (bill["energy_cost"], bill["total"]) == (
        pytest.approx(energy),
        pytest.approx(SIMPLE_HOUSEHOLD + energy),
    )


@pytest.mark.parametrize(
    "plan", ["residential_simple_2_tier", "residential_simple_3_tier"]
)
@pytest.mark.parametrize("index", [JULY, JANUARY], ids=["summer", "non-summer"])
@pytest.mark.parametrize(("kwh", "expected"), [(2000, 0.0), (2500, 500 * 1.04)])
def test_simple_tou_adds_1_04_a_kwh_above_2000_kwh(plan, index, kwh, expected):
    """Lines 204, 226 and 351-356: 每月總度數超過2000度之部分 每度加 1.04."""
    bill = _bill(plan, index, kwh=kwh / len(index))
    assert bill["surcharge"] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("plan", "energy"),
    [
        ("residential_simple_2_tier", SIMPLE_2_JULY),
        ("residential_simple_3_tier", SIMPLE_3_JULY),
    ],
)
def test_simple_tou_power_factor_leaves_out_the_household_fee(plan, energy):
    """Line 357: 按戶計收之基本電費，不列計功率因數調整費. 70% adds 1% to the
    rest of the month's bill (lines 467-469)."""
    bill = _bill(plan, JULY, meter_phase="three", power_factor=70)
    assert bill["adjustment"] == pytest.approx(0.01 * energy)


def test_simple_three_tier_idle_month_pays_the_full_basic_fee():
    """Lines 358-359: 未用電者，基本電費按核定電價計算."""
    bill = _bill("residential_simple_3_tier", JULY, kwh=0.0)
    assert bill["total"] == pytest.approx(SIMPLE_HOUSEHOLD)


@pytest.mark.parametrize(
    ("plan", "energy"),
    [
        ("lighting_standard_2_tier", STANDARD_2_JULY),
        ("lighting_standard_3_tier", STANDARD_3_JULY),
    ],
)
def test_standard_tou_bill_is_basic_plus_energy(plan, energy):
    """Lines 362 and 390: 每月電費為基本電費與流動電費之總和. 三相 按戶 and
    10 kW of 經常契約."""
    bill = _bill(
        plan,
        JULY,
        contract_capacities=_contracts(plan, regular=10),
        meter_phase="three",
    )
    expected = HOUSEHOLD_THREE + REGULAR["summer"] * 10 + energy
    assert bill["total"] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("index", "contracts", "expected"),
    [
        (
            JULY,
            {"regular": 20, "non_summer": 5, "saturday_semi_peak": 10, "off_peak": 30},
            HOUSEHOLD_THREE
            + REGULAR["summer"] * 20
            + WEEKEND["summer"] * ((10 + 30) - (20 + 5) * 0.5),
        ),
        (
            JANUARY,
            {"regular": 20, "non_summer": 5, "saturday_semi_peak": 10, "off_peak": 30},
            HOUSEHOLD_THREE
            + REGULAR["non_summer"] * 20
            + NON_SUMMER_CONTRACT * 5
            + WEEKEND["non_summer"] * ((10 + 30) - (20 + 5) * 0.5),
        ),
        (
            JULY,
            {"regular": 20, "saturday_semi_peak": 5},
            HOUSEHOLD_THREE + REGULAR["summer"] * 20,
        ),
        (JULY, {"off_peak": 20}, HOUSEHOLD_THREE + WEEKEND["summer"] * 20),
    ],
    ids=["summer", "non-summer", "negative-weekend-term-is-0", "off-peak-only"],
)
def test_standard_two_stage_basic_fee_formula(index, contracts, expected):
    """Lines 363-388: 按戶 plus 經常契約, 非夏月契約 in 非夏月 only, and
    週六半尖峰或離峰契約 on (週六半尖峰 + 離峰) - (經常 + 非夏月) x 0.5, 0 if
    negative. A customer with only 離峰契約 pays 按戶 and that contract."""
    plan = "lighting_standard_2_tier"
    bill = _bill(
        plan,
        index,
        kwh=_sundays(index),
        contract_capacities=_contracts(plan, **contracts),
        meter_phase="three",
    )
    assert bill["basic_cost"] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("index", "contracts", "expected"),
    [
        (
            JANUARY,
            {"regular": 30, "semi_peak": 10, "saturday_semi_peak": 10, "off_peak": 40},
            HOUSEHOLD_THREE
            + REGULAR["non_summer"] * 30
            + SEMI_PEAK_CONTRACT * 10
            + WEEKEND["non_summer"] * ((10 + 40) - (30 + 10) * 0.5),
        ),
        (
            JULY,
            {"regular": 30, "saturday_semi_peak": 5, "off_peak": 5},
            HOUSEHOLD_THREE + REGULAR["summer"] * 30,
        ),
    ],
    ids=["non-summer", "negative-weekend-term-is-0"],
)
def test_standard_three_stage_basic_fee_formula(index, contracts, expected):
    """Lines 391-403: 當月經常契約電價 x 經常 + 當月半尖峰契約電價 x 半尖峰 +
    當月週六半尖峰或離峰契約電價 x [(週六半尖峰 + 離峰) - (經常 + 半尖峰) x 0.5],
    the last term 0 if negative."""
    plan = "lighting_standard_3_tier"
    bill = _bill(
        plan,
        index,
        kwh=_sundays(index),
        contract_capacities=_contracts(plan, **contracts),
        meter_phase="three",
    )
    assert bill["basic_cost"] == pytest.approx(expected)


@pytest.mark.parametrize(
    "plan", ["lighting_standard_2_tier", "lighting_standard_3_tier"]
)
@pytest.mark.parametrize(
    ("demand_kw", "share"), [(0.0, 0.5), (5.0, 1.0)], ids=["no-demand", "demand"]
)
def test_standard_tou_month_without_kwh_and_demand_pays_half(plan, demand_kw, share):
    """Lines 407-408: 抄見度數與最高需量均為0 → 基本電費按核定電價50%."""
    bill = _bill(
        plan,
        JULY,
        kwh=0.0,
        demand=pd.Series(demand_kw, index=JULY),
        contract_capacities=_contracts(plan, regular=10),
        meter_phase="three",
    )
    expected = share * (HOUSEHOLD_THREE + REGULAR["summer"] * 10)
    assert bill["total"] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("index", "contracts", "peaks", "expected"),
    [
        (JULY, {"regular": 30}, {(15, 10): 31}, 2 * REGULAR["summer"]),
        (JULY, {"regular": 30}, {(15, 10): 36}, (3 * 2 + 3 * 3) * REGULAR["summer"]),
        (
            JULY,
            {"regular": 30, "non_summer": 10},
            {(15, 10): 31},
            2 * REGULAR["summer"],
        ),
        (
            JANUARY,
            {"regular": 30, "non_summer": 10},
            {(14, 10): 41},
            2 * REGULAR["non_summer"],
        ),
        (
            JULY,
            {"regular": 30, "saturday_semi_peak": 10},
            {(18, 10): 41},
            2 * WEEKEND["summer"],
        ),
        (
            JULY,
            {"regular": 30, "non_summer": 5, "saturday_semi_peak": 5, "off_peak": 5},
            {(19, 10): 46},
            2 * WEEKEND["summer"],
        ),
        (
            JULY,
            {"regular": 40, "saturday_semi_peak": 10},
            {(15, 10): 41, (18, 10): 52},
            2 * REGULAR["summer"] + 2 * WEEKEND["summer"],
        ),
        (
            JULY,
            {"regular": 40, "saturday_semi_peak": 10},
            {(15, 10): 42, (18, 10): 51, (19, 10): 53},
            2 * 2 * REGULAR["summer"] + 2 * WEEKEND["summer"],
        ),
    ],
    ids=[
        "a-peak",
        "a-peak-over-10pct",
        "a-summer-ignores-non-summer-contract",
        "b-non-summer-peak",
        "c-saturday",
        "d-off-peak",
        "e-saturday-less-peak",
        "e-off-peak-less-the-larger",
    ],
)
def test_standard_two_stage_over_contract(index, contracts, peaks, expected):
    """Lines 409-426 and 446-450: each time's 超約瓩數 over its contracts, less
    the larger excess of the times before it, at that time's 契約電價, 2x up
    to 10% of the contract and 3x above. 15 July is a weekday, 18 July a
    Saturday and 19 July a Sunday; 14 January is a weekday."""
    plan = "lighting_standard_2_tier"
    bill = _bill(
        plan,
        index,
        demand=_by_hour(index, peaks, base=10.0),
        contract_capacities=_contracts(plan, **contracts),
        meter_phase="three",
    )
    assert bill["adjustment"] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("index", "contracts", "peaks", "expected"),
    [
        (JULY, {"regular": 40}, {(15, 17): 41}, 2 * REGULAR["summer"]),
        (JULY, {"regular": 40}, {(15, 17): 46}, (4 * 2 + 2 * 3) * REGULAR["summer"]),
        (
            JULY,
            {"regular": 40, "semi_peak": 10},
            {(15, 10): 51},
            2 * SEMI_PEAK_CONTRACT,
        ),
        (
            JANUARY,
            {"regular": 40, "semi_peak": 10},
            {(14, 10): 51},
            2 * SEMI_PEAK_CONTRACT,
        ),
        (
            JULY,
            {"regular": 40, "semi_peak": 10, "saturday_semi_peak": 10},
            {(18, 10): 61},
            2 * WEEKEND["summer"],
        ),
        (
            JULY,
            {"regular": 40, "semi_peak": 5, "saturday_semi_peak": 5, "off_peak": 5},
            {(19, 10): 56},
            2 * WEEKEND["summer"],
        ),
        (
            JULY,
            {"regular": 40, "semi_peak": 10},
            {(15, 17): 41, (15, 10): 52},
            2 * REGULAR["summer"] + 2 * SEMI_PEAK_CONTRACT,
        ),
        (
            JULY,
            {"regular": 40, "semi_peak": 10},
            {(15, 10): 52, (18, 10): 51, (19, 10): 53},
            2 * 2 * SEMI_PEAK_CONTRACT + 2 * WEEKEND["summer"],
        ),
    ],
    ids=[
        "a-peak",
        "a-peak-over-10pct",
        "b-semi-peak",
        "b-non-summer-semi-peak",
        "c-saturday",
        "d-off-peak",
        "e-semi-peak-less-peak",
        "e-off-peak-less-the-larger",
    ],
)
def test_standard_three_stage_over_contract(index, contracts, peaks, expected):
    """Lines 427-450: as 二段式, with 半尖峰 over 經常 + 半尖峰契約 at 半尖峰契約電價.
    July 15 17:00 is 尖峰 and 10:00 半尖峰 (lines 283-286)."""
    plan = "lighting_standard_3_tier"
    bill = _bill(
        plan,
        index,
        demand=_by_hour(index, peaks, base=10.0),
        contract_capacities=_contracts(plan, **contracts),
        meter_phase="three",
    )
    assert bill["adjustment"] == pytest.approx(expected)


def test_over_contract_fee_gets_no_power_factor_discount():
    """Lines 446-448: 超約 不給予功率因數扣減. 90% takes 1% off the month's bill
    less 按戶 (lines 406, 467-469), and nothing off the 超約 fee."""
    plan = "lighting_standard_2_tier"
    bill = _bill(
        plan,
        JULY,
        demand=_by_hour(JULY, {(15, 10): 41}, base=10.0),
        contract_capacities=_contracts(plan, regular=40),
        meter_phase="three",
        power_factor=90,
    )
    month = REGULAR["summer"] * 40 + STANDARD_2_JULY
    assert bill["adjustment"] == pytest.approx(-0.01 * month + 2 * REGULAR["summer"])


@pytest.mark.parametrize(
    ("plan", "inputs"),
    [
        (
            "residential_non_tou",
            {"meter_phase": "single", "meter_voltage_v": 110, "meter_ampere": 10},
        ),
        ("residential_simple_2_tier", {"meter_phase": "single"}),
        (
            "lighting_standard_2_tier",
            {
                "meter_phase": "single",
                "contract_capacities": _contracts(
                    "lighting_standard_2_tier", regular=30
                ),
            },
        ),
    ],
)
def test_power_factor_needs_three_phase_supply(plan, inputs):
    """Lines 461-465: only 以三相供應之用戶 have their bill adjusted."""
    bill = _bill(plan, JULY, power_factor=70, **inputs)
    assert bill["adjustment"] == pytest.approx(0.0)


@pytest.mark.parametrize(("regular", "share"), [(19, 0.0), (20, 0.01)])
def test_standard_tou_power_factor_needs_a_20_kw_contract(regular, share):
    """Lines 464-467: 標準型 is adjusted when 契約容量20瓩以上, on the bill
    less 按戶計收 (line 406)."""
    plan = "lighting_standard_2_tier"
    bill = _bill(
        plan,
        JULY,
        contract_capacities=_contracts(plan, regular=regular),
        meter_phase="three",
        power_factor=70,
    )
    month = REGULAR["summer"] * regular + STANDARD_2_JULY
    assert bill["adjustment"] == pytest.approx(share * month)


@pytest.mark.parametrize(
    ("power_factor", "share"),
    [(70, 0.01), (79, 0.001), (80, 0.0), (81, -0.001), (95, -0.015), (99, -0.015)],
)
def test_power_factor_steps_and_cap(power_factor, share):
    """Lines 467-469: 0.1% per 1% under or over 80%, and nothing more for
    超過95%部分. The bill less 按戶計收 (line 406)."""
    plan = "lighting_standard_3_tier"
    bill = _bill(
        plan,
        JULY,
        contract_capacities=_contracts(plan, regular=30),
        meter_phase="three",
        power_factor=power_factor,
    )
    month = REGULAR["summer"] * 30 + STANDARD_3_JULY
    assert bill["adjustment"] == pytest.approx(share * month)


@pytest.mark.xfail(strict=True, reason="not supported: 用電設備容量 (kVA) input")
@pytest.mark.parametrize(("kva", "share"), [(19, 0.0), (20, 0.01)])
@pytest.mark.parametrize(
    ("plan", "energy"),
    [
        ("residential_non_tou", RESIDENTIAL_JULY),
        ("residential_simple_2_tier", SIMPLE_2_JULY),
    ],
)
def test_power_factor_needs_20_kva_of_equipment(plan, energy, kva, share):
    """Lines 462-464: 非時間電價 and 簡易型 are adjusted when 三相 and
    用電設備容量20千伏安以上."""
    bill = _bill(
        plan,
        JULY,
        meter_phase="three",
        meter_voltage_v=220,
        meter_ampere=10,
        equipment_capacity_kva=kva,
        power_factor=70,
    )
    assert bill["adjustment"] == pytest.approx(share * energy)


@pytest.mark.xfail(strict=True, reason="not supported: 免計營業稅 input")
def test_tax_exempt_customer_pays_the_total_over_1_05():
    """Lines 472-473: 依法免計營業稅用戶每月應繳總金額為電費總金額除以1.05.
    300 kWh in January, lines 138-139."""
    usage = _days("2026-01-01", "2026-01-31", 300)
    bill = tou.calculate_bill(usage, "residential_non_tou", _meter(tax_exempt=True))
    expected = (120 * 1.78 + 180 * 2.26) / 1.05
    assert bill["total"].iloc[0] == pytest.approx(expected)


# 營業用 非夏月, lines 170-174: the first 3000 kWh; above that 5.83.
BUSINESS_FIRST_3000 = 330 * 2.28 + 370 * 3.10 + 800 * 3.61 + 1500 * 5.56


@pytest.mark.xfail(strict=True, reason="not supported: 變壓器容量 input")
@pytest.mark.parametrize(
    ("kva", "billed_kwh"),
    [(100, 0.98 * (10000 - 100 * 720 * 0.01)), (200, 0.98 * (10000 - 1000))],
    ids=["iron-loss", "iron-loss-capped-at-10pct"],
)
def test_high_voltage_meter_kwh_less_transformer_iron_loss(kva, billed_kwh):
    """Lines 477-481: 0.98 x (高壓電表抄見度數 - 變壓器容量 x 720 x 0.01),
    the 鐵損 at most 10% of the reading."""
    usage = _days("2026-01-01", "2026-01-31", 10000)
    inputs = _meter(
        phase="three", ampere=1, voltage=11400, transformer_capacity_kva=kva
    )
    bill = tou.calculate_bill(usage, "lighting_business_tiered", inputs)
    expected = BUSINESS_FIRST_3000 + (billed_kwh - 3000) * 5.83
    assert bill["energy_cost"].iloc[0] == pytest.approx(expected)


@pytest.mark.xfail(strict=True, reason="not supported: 變壓器容量 input")
def test_low_voltage_meter_kwh_plus_transformer_loss():
    """Lines 482-484: 低壓電表抄見度數 + (變壓器容量 - 契約容量) x 720 x 0.01."""
    usage = _days("2026-01-01", "2026-01-31", 10000)
    inputs = _meter(
        phase="three", contract_capacity_kw=50, transformer_capacity_kva=100
    )
    bill = tou.calculate_bill(usage, "lighting_business_tiered", inputs)
    billed_kwh = 10000 + (100 - 50) * 720 * 0.01
    expected = BUSINESS_FIRST_3000 + (billed_kwh - 3000) * 5.83
    assert bill["energy_cost"].iloc[0] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("contracts", "inside", "outside", "expected"),
    [
        (
            {"off_peak": 20},
            (19, 10),
            (18, 10),
            4.8 * WEEKEND["summer"] * 8 + 1.6 * 2.76 * 2 + 2.27 * 10,
        ),
        (
            {"saturday_semi_peak": 20},
            (18, 10),
            (15, 10),
            4.8 * REGULAR["summer"] * 8 + 1.6 * 5.54 * 2 + 2.76 * 10,
        ),
    ],
    ids=["off-peak-only-uses-saturday", "saturday-only-uses-weekday-peak"],
)
def test_weekend_only_contract_pays_more_outside_its_hours(
    contracts, inside, outside, expected
):
    """Lines 487-491: 8 kW and 2 kWh outside the contract's times pay 4.8x
    that time's 基本電費 and 1.6x its 流動電費 (lines 240-263). 10 kW and
    10 kWh inside pay the usual price, and the contract pays 按戶 plus 20 kW
    of 週六半尖峰或離峰契約 (lines 363-379). 18 July 2026 is a Saturday, 19 July
    a Sunday and 15 July a weekday."""
    plan = "lighting_standard_2_tier"
    bill = _bill(
        plan,
        JULY,
        kwh=_by_hour(JULY, {inside: 10 / 4, outside: 2 / 4}),
        demand=_by_hour(JULY, {inside: 10, outside: 8}),
        contract_capacities=_contracts(plan, **contracts),
        meter_phase="three",
    )
    contract = HOUSEHOLD_THREE + WEEKEND["summer"] * 20
    assert bill["total"] == pytest.approx(contract + expected)
