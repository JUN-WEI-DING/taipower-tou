"""The worked bills of Taipower's 各類電價表及計算範例 (114/10/1), through
calculate_bill.

docs/references/各類電價表及計算範例_1141001.txt is the text. Each case gives
its page, the printed equation and the printed total. The usage spreads each
time period's kWh evenly over that period's quarter hours of August 2026, by
the page's 夏月 hours. Taipower's 時間電價日曆表 (tests/data/taipower_calendar/
2026.csv) gives August 2026 21 weekdays, 5 Saturdays and 5 Sundays, and no
other 離峰日.
"""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import taipower_tou as tou

AUGUST = pd.date_range("2026-08-01", "2026-08-31 23:45", freq="15min")
CALENDAR = Path(__file__).parent / "data" / "taipower_calendar" / "2026.csv"
DAY_TYPES = pd.read_csv(CALENDAR, index_col="date")["day_type"]
# Taipower names its 指定 days the day before. Any ten August weekdays do.
PEAK_DAYS = [date(2026, 8, day) for day in (3, 4, 5, 6, 7, 10, 11, 12, 13, 14)]

WEEKEND = ["saturday 00:00-24:00", "sunday_holiday 00:00-24:00"]
MONTH = {"month": ["weekday 00:00-24:00", *WEEKEND]}
# 夏月 hours of each table. Pages 4 and 5.
SIMPLE_2 = {
    "peak": ["weekday 09:00-24:00"],
    "off_peak": ["weekday 00:00-09:00", *WEEKEND],
}
SIMPLE_3 = {
    "peak": ["weekday 16:00-22:00"],
    "semi_peak": ["weekday 09:00-16:00", "weekday 22:00-24:00"],
    "off_peak": ["weekday 00:00-09:00", *WEEKEND],
}
# Pages 6, 9, 12 and 17.
TWO_STAGE = {
    "peak": ["weekday 09:00-24:00"],
    "saturday_semi_peak": ["saturday 09:00-24:00"],
    "off_peak": [
        "weekday 00:00-09:00",
        "saturday 00:00-09:00",
        "sunday_holiday 00:00-24:00",
    ],
}
# Pages 7, 10, 13 and 18.
THREE_STAGE = {
    **TWO_STAGE,
    "peak": ["weekday 16:00-22:00"],
    "semi_peak": ["weekday 09:00-16:00", "weekday 22:00-24:00"],
}
# Pages 14 and 19: 尖峰 only on 指定 days, 半尖峰 09:00-24:00 on the others.
VARIABLE_PEAK = {
    "peak": ["designated 16:00-22:00"],
    "semi_peak": [
        "designated 09:00-16:00",
        "designated 22:00-24:00",
        "weekday 09:00-24:00",
    ],
    "saturday_semi_peak": ["saturday 09:00-24:00"],
    "off_peak": ["designated 00:00-09:00", *TWO_STAGE["off_peak"]],
}
# Pages 11 and 16.
EV = {
    "peak": ["weekday 16:00-22:00"],
    "off_peak": ["weekday 00:00-16:00", "weekday 22:00-24:00", *WEEKEND],
}
# Pages 15 and 20.
BATCH = {
    "peak": ["weekday 15:30-21:30"],
    "saturday_semi_peak": ["saturday 15:30-21:30"],
    "off_peak": [
        "weekday 00:00-15:30",
        "weekday 21:30-24:00",
        "saturday 00:00-15:30",
        "saturday 21:30-24:00",
        "sunday_holiday 00:00-24:00",
    ],
}


def _contracts(regular, saturday_semi_peak=0):
    """A 經常契約, and a 週六半尖峰契約 where the page has one. No other."""
    return {
        "contract_capacities": {
            "regular": regular,
            "non_summer": 0,
            "semi_peak": 0,
            "saturday_semi_peak": saturday_semi_peak,
            "off_peak": 0,
        }
    }


def _usage(hours, kwh, designated=()):
    """kwh[period] spread evenly over the quarter hours hours[period] names."""
    days = DAY_TYPES.reindex(AUGUST.strftime("%Y-%m-%d")).to_numpy()
    days[np.isin(AUGUST.date, designated)] = "designated"
    clock = AUGUST.strftime("%H:%M").to_numpy()
    masks = {}
    for period, spans in hours.items():
        masks[period] = np.zeros(len(AUGUST), dtype=bool)
        for span in spans:
            day, times = span.split()
            start, end = times.split("-")
            masks[period] |= (days == day) & (clock >= start) & (clock < end)
    assert (sum(masks.values()) == 1).all(), "the page's hours cover the day once"
    usage = pd.Series(0.0, index=AUGUST)
    for period, total in kwh.items():
        usage[masks[period]] = total / masks[period].sum()
    return usage


NO_FLAT_RATE = pytest.mark.xfail(strict=True, reason="not supported: no 包制電價 plan")
NO_VARIABLE_PEAK = pytest.mark.xfail(
    strict=True,
    reason="not supported: no 三段式尖峰時間可變動 plan and no input for its 指定 days",
)

CASES = [
    pytest.param(
        "flat_rate_street_light",
        MONTH,
        {},
        {"basic_fee_inputs": {"公用路燈瓦數": 500}},
        278,
        "(500瓦-100瓦)÷100＝4, (131.43元×1＋106.02元×4)×0.5＝278元",
        id="p01-street-light",
        marks=NO_FLAT_RATE,
    ),
    pytest.param(
        "flat_rate_small_appliance",
        MONTH,
        {},
        {"basic_fee_inputs": {"小型器具瓦數": 320}},
        579,
        "(320瓦-50瓦)÷50＝5.4≒6, 115.55元×1＋77.29元×6＝579元",
        id="p01-small-appliance",
        marks=NO_FLAT_RATE,
    ),
    pytest.param(
        "residential_non_tou",
        MONTH,
        {"month": 400},
        {},
        1015,
        "1.78元×120度＋2.55元×(330度-120度)＋3.80元×(400度-330度)＝1,015元",
        id="p02-residential_non_tou",
    ),
    pytest.param(
        "lighting_non_business_tiered",
        MONTH,
        {"month": 800},
        {},
        3067,
        "1.78元×120度＋2.55元×(330度-120度)＋3.80元×(500度-330度)"
        "＋5.14元×(700度-500度)＋6.44元×(800度-700度)＝3,067元",
        id="p02-lighting_non_business_tiered",
    ),
    pytest.param(
        "lighting_business_tiered",
        MONTH,
        {"month": 1800},
        {},
        7978,
        "2.71元×330度+3.76元×(700度-330度)＋4.46元×(1,500度-700度)"
        "＋7.08元×(1,800度-1,500度)＝7,978元",
        id="p03-lighting_business_tiered",
    ),
    pytest.param(
        "residential_simple_2_tier",
        SIMPLE_2,
        {"peak": 1200, "off_peak": 1000},
        {},
        8535,
        "75.00元＋5.16元×1,200度+2.06元×1,000度"
        "＋[(1,200度+1,000度)-2,000度]×1.04元＝8,535元",
        id="p04-residential_simple_2_tier",
    ),
    pytest.param(
        "residential_simple_3_tier",
        SIMPLE_3,
        {"peak": 200, "semi_peak": 1000, "off_peak": 1000},
        {},
        8459,
        "75.00元＋7.13元×200度+4.69元×1,000度+2.06元×1,000度"
        "＋[(200度+1,000度+1,000度)-2,000度]×1.04元＝8,459元",
        id="p05-residential_simple_3_tier",
    ),
    pytest.param(
        "lighting_standard_2_tier",
        TWO_STAGE,
        {"peak": 2000, "saturday_semi_peak": 500, "off_peak": 1500},
        {**_contracts(20), "meter_phase": "three"},
        20852,
        "262.50元+236.20元×20瓩＋5.54元×2,000度+2.76元×500度+2.27元×1,500度＝20,852元",
        id="p06-lighting_standard_2_tier",
    ),
    pytest.param(
        "lighting_standard_3_tier",
        THREE_STAGE,
        {"peak": 300, "semi_peak": 1700, "saturday_semi_peak": 500, "off_peak": 1500},
        {**_contracts(20), "meter_phase": "three"},
        20552,
        "262.50元+236.20元×20瓩＋8.12元×300度+5.02元×1,700度+2.50元×500度"
        "+2.23元×1,500度＝20,552元",
        id="p07-lighting_standard_3_tier",
    ),
    pytest.param(
        "low_voltage_power",
        MONTH,
        {"month": 3000},
        {"basic_fee_inputs": {"裝置契約": 30}},
        16365,
        "137.50元×30瓩＋4.08元×3,000度＝16,365元",
        id="p08-low_voltage_power-installed",
    ),
    pytest.param(
        "low_voltage_power",
        MONTH,
        {"month": 10000},
        _contracts(95),
        63239,
        "236.20元×95瓩＋4.08元×10,000度＝63,239元",
        id="p08-low_voltage_power-demand",
    ),
    pytest.param(
        "low_voltage_2_tier",
        TWO_STAGE,
        {"peak": 2000, "saturday_semi_peak": 1000, "off_peak": 1500},
        {"basic_fee_inputs": {"裝置契約": 30}},
        21475,
        "105.00元+137.50元×30瓩＋5.54元×2,000度+2.76元×1,000度+2.27元×1,500度"
        "＝21,475元",
        id="p09-low_voltage_2_tier-installed",
    ),
    pytest.param(
        "low_voltage_2_tier",
        TWO_STAGE,
        {"peak": 6000, "saturday_semi_peak": 1000, "off_peak": 4000},
        _contracts(95),
        67782,
        "262.50元+236.20元×95瓩＋5.54元×6,000度+2.76元×1,000度+2.27元×4,000度"
        "＝67,782元",
        id="p09-low_voltage_2_tier-demand",
    ),
    pytest.param(
        "low_voltage_three_stage",
        THREE_STAGE,
        {"peak": 900, "semi_peak": 5100, "saturday_semi_peak": 1000, "off_peak": 4000},
        _contracts(95),
        67032,
        "262.50元+236.20元×95瓩＋8.12元×900度+5.02元×5,100度+2.50元×1,000度"
        "+2.23元×4,000度＝67,032元",
        id="p10-low_voltage_three_stage",
    ),
    pytest.param(
        "low_voltage_ev",
        EV,
        {"peak": 0, "off_peak": 3000},
        _contracts(49),
        11725,
        "262.50元+47.20元×49瓩＋3.05元×3,000度＝11,725元",
        id="p11-low_voltage_ev",
    ),
    pytest.param(
        "high_voltage_2_tier",
        TWO_STAGE,
        {"peak": 15600, "saturday_semi_peak": 5000, "off_peak": 13000},
        _contracts(150),
        187920,
        "223.60元×150瓩＋6.75元×15,600度+2.77元×5,000度+2.71元×13,000度＝187,920元",
        id="p12-high_voltage_2_tier",
    ),
    pytest.param(
        "high_voltage_three_stage",
        THREE_STAGE,
        {
            "peak": 10000,
            "semi_peak": 15000,
            "saturday_semi_peak": 5000,
            "off_peak": 20000,
        },
        _contracts(500),
        357050,
        "223.60元×500瓩＋9.39元×10,000度+5.85元×15,000度+2.60元×5,000度"
        "+2.53元×20,000度＝357,050元",
        id="p13-high_voltage_three_stage",
    ),
    pytest.param(
        "high_voltage_three_stage_variable_peak",
        VARIABLE_PEAK,
        {
            "peak": 3000,
            "semi_peak": 22000,
            "saturday_semi_peak": 5000,
            "off_peak": 20000,
        },
        {**_contracts(500), "peak_days": PEAK_DAYS},
        359090,
        "223.60元×500瓩＋18.33元×3,000度+5.85元×22,000度+2.60元×5,000度"
        "+2.53元×20,000度＝359,090元",
        id="p14-high_voltage_three_stage_variable_peak",
        marks=NO_VARIABLE_PEAK,
    ),
    pytest.param(
        "high_voltage_batch",
        BATCH,
        {"peak": 10000, "saturday_semi_peak": 2000, "off_peak": 38000},
        _contracts(150, saturday_semi_peak=350),
        297893,
        "223.60元×150瓩+44.70元×(350-150×0.5)瓩＋12.47元×10,000度"
        "+3.26元×2,000度+3.18元×38,000度＝297,893元",
        id="p15-high_voltage_batch",
    ),
    pytest.param(
        "high_voltage_ev",
        EV,
        {"peak": 0, "off_peak": 25000},
        _contracts(280),
        85243,
        "262.50元+47.20元×280瓩＋3.05元×25,000度＝89,729元×95%=85,243元",
        id="p16-high_voltage_ev",
    ),
    pytest.param(
        "extra_high_voltage_2_tier",
        TWO_STAGE,
        {"peak": 160000, "saturday_semi_peak": 50000, "off_peak": 130000},
        _contracts(10000),
        3628200,
        "217.30元×10,000瓩＋6.17元×160,000度+2.73元×50,000度+2.55元×130,000度"
        "＝3,628,200元",
        id="p17-extra_high_voltage_2_tier",
    ),
    pytest.param(
        "extra_high_voltage_three_stage",
        THREE_STAGE,
        {
            "peak": 100000,
            "semi_peak": 150000,
            "saturday_semi_peak": 50000,
            "off_peak": 200000,
        },
        _contracts(10000),
        4454000,
        "217.30元×10,000瓩＋8.69元×100,000度+5.38元×150,000度+2.50元×50,000度"
        "+2.40元×200,000度＝4,454,000元",
        id="p18-extra_high_voltage_three_stage",
    ),
    pytest.param(
        "extra_high_voltage_three_stage_variable_peak",
        VARIABLE_PEAK,
        {
            "peak": 30000,
            "semi_peak": 220000,
            "saturday_semi_peak": 50000,
            "off_peak": 200000,
        },
        {**_contracts(10000), "peak_days": PEAK_DAYS},
        4473100,
        "217.30元×10,000瓩＋17.05元×30,000度+5.38元×220,000度+2.50元×50,000度"
        "+2.40元×200,000度＝4,473,100元",
        id="p19-extra_high_voltage_three_stage_variable_peak",
        marks=NO_VARIABLE_PEAK,
    ),
    pytest.param(
        "extra_high_voltage_batch",
        BATCH,
        {"peak": 100000, "saturday_semi_peak": 20000, "off_peak": 380000},
        _contracts(3000, saturday_semi_peak=7000),
        3234800,
        "217.30元×3,000瓩+43.40元×(7,000-3,000×0.5)瓩＋11.44元×100,000度"
        "+3.20元×20,000度+2.99元×380,000度＝3,234,800元",
        id="p20-extra_high_voltage_batch",
    ),
]


@pytest.mark.parametrize(("plan", "hours", "kwh", "inputs", "total", "equation"), CASES)
def test_worked_bill_matches_the_printed_total(
    plan, hours, kwh, inputs, total, equation
):
    """A page's bill for its example's month and kWh. A 需量契約 bill gets its
    usage's own quarter-hour demand, which stays under the contract as every
    such example assumes (倘最高需量未超過契約容量)."""
    usage = _usage(hours, kwh, inputs.get("peak_days", ()))
    if "contract_capacities" in inputs:
        inputs = {**inputs, "demand_kw": usage * 4}
    bill = tou.calculate_bill(
        usage, plan, tou.BillingInputs(billing_cycle_months=1, **inputs)
    )
    assert bill["total"].iloc[0] == total, equation
