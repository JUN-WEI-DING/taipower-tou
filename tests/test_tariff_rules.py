"""基本電費, 功率因數 and 超約 rules, with amounts worked from the 電價表 text.

Prices are from src/taipower_tou/data/詳細電價表.md (114/10/1):
high_voltage_2_tier lines 856-859, lighting_standard_3_tier lines 274-281.
"""

import pandas as pd
import pytest

import taipower_tou as tou

JULY = pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min")
JANUARY = pd.date_range("2026-01-01", "2026-01-31 23:45", freq="15min")

HV_REGULAR = {"summer": 223.60, "non_summer": 166.90}
HV_NON_SUMMER = 166.90
HV_WEEKEND = {"summer": 44.70, "non_summer": 33.30}
LS_HOUSEHOLD_SINGLE = 129.10
LS_REGULAR_SUMMER = 236.20
LS_SEMI_PEAK_SUMMER = 173.20
LS_WEEKEND_SUMMER = 47.20


def _bill(plan, index, kwh=0.25, demand=None, **inputs):
    usage = pd.Series(kwh, index=index)
    if demand is not None:
        inputs["demand_kw"] = demand
    return tou.calculate_bill(usage, plan, tou.BillingInputs(**inputs)).iloc[0]


def _demand(index, peaks):
    """100 kW all month, with the kW in peaks at (day, hour) on that hour."""
    demand = pd.Series(100.0, index=index)
    for (day, hour), kw in peaks.items():
        demand[(index.day == day) & (index.hour == hour)] = kw
    return demand


@pytest.mark.parametrize(
    ("index", "season"), [(JULY, "summer"), (JANUARY, "non_summer")]
)
def test_two_stage_basic_fee_formula(index, season):
    """第五章 五(一)1: 週六半尖峰或離峰契約 is billed on
    (週六半尖峰 + 離峰) - (經常 + 非夏月) x 0.5, and 非夏月契約 only in 非夏月."""
    capacities = {
        "regular": 200,
        "non_summer": 50,
        "saturday_semi_peak": 100,
        "off_peak": 300,
    }
    weekend = (100 + 300) - (200 + 50) * 0.5
    expected = HV_REGULAR[season] * 200 + HV_WEEKEND[season] * weekend
    if season == "non_summer":
        expected += HV_NON_SUMMER * 50
    bill = _bill("high_voltage_2_tier", index, contract_capacities=capacities)
    assert bill["basic_cost"] == pytest.approx(expected)


def test_weekend_contract_below_half_the_others_costs_nothing():
    capacities = {"regular": 200, "saturday_semi_peak": 50}
    bill = _bill("high_voltage_2_tier", JULY, contract_capacities=capacities)
    assert bill["basic_cost"] == pytest.approx(HV_REGULAR["summer"] * 200)


def test_three_stage_basic_fee_is_per_household_and_per_contract():
    """第三章 五(二)2: 基本電費按戶及按契約容量計算."""
    capacities = {
        "regular": 30,
        "semi_peak": 10,
        "saturday_semi_peak": 10,
        "off_peak": 40,
    }
    weekend = (10 + 40) - (30 + 10) * 0.5
    expected = (
        LS_HOUSEHOLD_SINGLE
        + LS_REGULAR_SUMMER * 30
        + LS_SEMI_PEAK_SUMMER * 10
        + LS_WEEKEND_SUMMER * weekend
    )
    bill = _bill(
        "lighting_standard_3_tier",
        JULY,
        contract_capacities=capacities,
        meter_phase="single",
    )
    assert bill["basic_cost"] == pytest.approx(expected)


def test_no_usage_pays_half_the_basic_fee():
    """第五章 五(二): 抄見度數與最高需量均為0 → 基本電費按核定電價50%."""
    bill = _bill(
        "high_voltage_2_tier",
        JULY,
        kwh=0.0,
        demand=pd.Series(0.0, index=JULY),
        contract_capacities={"regular": 200},
    )
    assert bill["total"] == pytest.approx(0.5 * HV_REGULAR["summer"] * 200)


@pytest.mark.parametrize(
    ("plan", "inputs", "household"),
    [
        ("high_voltage_2_tier", {"contract_capacities": {"regular": 200}}, 0.0),
        (
            "lighting_standard_3_tier",
            {"contract_capacities": {"regular": 30}, "meter_phase": "single"},
            LS_HOUSEHOLD_SINGLE,
        ),
    ],
)
@pytest.mark.parametrize(("power_factor", "share"), [(90, -0.01), (70, 0.01)])
def test_power_factor_adjusts_the_months_bill(
    plan, inputs, household, power_factor, share
):
    """Every chapter's 六、功率因數: 該月份電費 changes 0.1% per 1% from 80%.
    按戶計收之基本電費，不列計功率因數調整費."""
    bill = _bill(plan, JULY, power_factor=power_factor, **inputs)
    month = bill["basic_cost"] - household + bill["energy_cost"]
    assert bill["adjustment"] == pytest.approx(share * month)


@pytest.mark.parametrize(
    ("index", "capacities", "peaks", "expected"),
    [
        (JULY, {"regular": 200}, {(15, 17): 205}, 5 * 2 * HV_REGULAR["summer"]),
        (
            JULY,
            {"regular": 200},
            {(15, 17): 230},
            (20 * 2 + 10 * 3) * HV_REGULAR["summer"],
        ),
        (
            JULY,
            {"regular": 200, "non_summer": 50},
            {(15, 17): 215},
            15 * 2 * HV_REGULAR["summer"],
        ),
        (
            JANUARY,
            {"regular": 200, "non_summer": 50},
            {(14, 17): 260},
            10 * 2 * HV_REGULAR["non_summer"],
        ),
        (
            JULY,
            {"regular": 200},
            {(15, 17): 205, (15, 3): 212},
            (5 * HV_REGULAR["summer"] + 7 * HV_WEEKEND["summer"]) * 2,
        ),
    ],
    ids=[
        "peak-within-10pct",
        "peak-over-10pct",
        "summer-ignores-non-summer-contract",
        "non-summer-counts-non-summer-contract",
        "peak-and-off-peak",
    ],
)
def test_over_contract_basic_fee(index, capacities, peaks, expected):
    """第五章 七: 夏月尖峰超約 = 尖峰最高需量 - 經常契約; 非夏月 also takes off
    非夏月契約. 離峰超約 takes off 尖峰超約, and each is billed at its own
    契約電價, 2x up to 10% of the contract and 3x above."""
    bill = _bill(
        "high_voltage_2_tier",
        index,
        demand=_demand(index, peaks),
        contract_capacities=capacities,
    )
    assert bill["adjustment"] == pytest.approx(expected)


HALF_WHEN_IDLE = [
    "lighting_standard_2_tier",
    "lighting_standard_3_tier",
    "low_voltage_2_tier",
    "low_voltage_three_stage",
    "low_voltage_ev",
    "high_voltage_2_tier",
    "high_voltage_three_stage",
    "high_voltage_batch",
    "high_voltage_ev",
    "extra_high_voltage_2_tier",
    "extra_high_voltage_three_stage",
    "extra_high_voltage_batch",
]


@pytest.mark.parametrize("plan", HALF_WHEN_IDLE)
def test_idle_month_pays_half_the_basic_fee_of_a_used_month(plan):
    """第三章 五(三)4, 第四章 五(五), 第五章 五(二)."""
    inputs = {"contract_capacities": {"regular": 100}, "meter_phase": "three"}
    used = _bill(plan, JULY, **inputs)
    idle = _bill(plan, JULY, kwh=0.0, **inputs)
    assert idle["total"] == pytest.approx(0.5 * used["basic_cost"])


def test_low_voltage_power_idle_month_pays_half_the_basic_fee():
    inputs = {"basic_fee_inputs": {"裝置契約": 100}}
    used = _bill("low_voltage_power", JULY, **inputs)
    idle = _bill("low_voltage_power", JULY, kwh=0.0, **inputs)
    assert idle["total"] == pytest.approx(0.5 * used["basic_cost"])
    assert used["basic_cost"] == pytest.approx(137.50 * 100)


def test_simple_tou_idle_month_pays_the_full_basic_fee():
    """第三章 五(二)4: 簡易型 未用電者，基本電費按核定電價計算."""
    bill = _bill("residential_simple_2_tier", JULY, kwh=0.0)
    assert bill["total"] == pytest.approx(75.0)
