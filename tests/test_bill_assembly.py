"""How calculate_bill_breakdown puts one bill together: 底度, energy, the basic
fee of a month without use, 超約, 功率因數, high_voltage_ev's 95% and the
minimum fee, in combinations the other tests leave out.

The rules are 營業規章施行細則 第二十八、二十九、三十、三十八條
(docs/references/營業規章施行細則第四章.txt), the 電價表
(src/taipower_tou/data/詳細電價表.md, 114/10/1) and page 16 of 各類電價表及計算範例
(docs/references/各類電價表及計算範例_1141001.txt). Line numbers are of
詳細電價表.md. Every amount is cut to the 角 and the total rounded half up to
the 元 (第二十九條).
"""

import pandas as pd
import pytest

import taipower_tou as tou

JULY = pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min")
JAN_FEB = pd.date_range("2026-01-01", "2026-02-28", freq="D")
DEMAND_31_KW = {"regular": 31, "non_summer": 0, "saturday_semi_peak": 0, "off_peak": 0}
# low_voltage_2_tier 需量契約 in July: 按戶 262.50 + 經常契約 236.20 x 31 kW
# (lines 538-540).
DEMAND_31_KW_BASIC = 262.50 + 236.20 * 31
# low_voltage_2_tier 裝置契約: 按戶 105.00 + 137.50 x 21 kW (lines 535-537).
INSTALLED_21_KW_BASIC = 105.00 + 137.50 * 21


def _summary(usage, plan, **inputs):
    inputs = tou.BillingInputs(**inputs)
    return tou.calculate_bill_breakdown(usage, plan, inputs)["summary"].iloc[0]


def _sundays(kwh):
    """kwh every quarter hour of July 2026's four Sundays, all 離峰 (line 567)."""
    usage = pd.Series(0.0, index=JULY)
    usage[JULY.day_of_week == 6] = kwh
    return usage


def _installed(usage, **inputs):
    return _summary(
        usage,
        "low_voltage_2_tier",
        basic_fee_inputs={"裝置契約": 21},
        meter_phase="three",
        **inputs,
    )


def _demand_contract(usage, **inputs):
    return _summary(
        usage,
        "low_voltage_2_tier",
        contract_capacities=DEMAND_31_KW,
        meter_phase="three",
        **inputs,
    )


def _three_phase_lighting(kwh, power_factor):
    """residential_non_tou on a 30 A three-phase meter, billed for January and
    February 2026 together."""
    return _summary(
        pd.Series(kwh / len(JAN_FEB), index=JAN_FEB),
        "residential_non_tou",
        meter_phase="three",
        meter_voltage_v=220,
        meter_ampere=30,
        billing_cycle_months=2,
        power_factor=power_factor,
    )


@pytest.mark.parametrize("power_factor", [70, 95])
def test_month_without_use_at_its_minimum_usage_gets_no_power_factor_change(
    power_factor,
):
    """第三十八條: 全月均無用電之用戶，當月功率因數按80％計算. The empty house is
    still billed its 底度 (第三章 五(一)1, line 338): 60 kWh a month at 1.78
    (line 138), 213.6 for two months, and the 功率因數 changes nothing."""
    bill = _three_phase_lighting(0.0, power_factor)
    assert bill["energy_cost"] == pytest.approx(213.6)
    assert bill["adjustment"] == pytest.approx(0.0)
    assert bill["total"] == 214


def test_used_month_under_its_minimum_usage_adjusts_the_minimum_usage_bill():
    """第三章 五(一)1 bills 20 kWh at the 底度 of 120 kWh, 213.6, and 六 (lines
    461-469) moves that month's bill 1% at 70%: 2.136, cut to 2.1."""
    bill = _three_phase_lighting(20.0, 70)
    assert bill["energy_cost"] == pytest.approx(213.6)
    assert bill["adjustment"] == pytest.approx(2.1)
    assert bill["total"] == 216


def test_over_contract_kw_makes_the_month_used():
    """第四章 五(五) (lines 712-715) halves the basic fee only when 抄見度數與最高
    需量均為0. 2 kW of 超約 means a 最高需量 of 33 kW, so the month pays the whole
    basic fee, 7584.7, and 2 kW x 2 x 236.20 = 944.8 of 超約 (七(二)2, line 790)."""
    bill = _demand_contract(pd.Series(0.0, index=JULY), over_contract_kw=2)
    assert bill["basic_cost"] == pytest.approx(DEMAND_31_KW_BASIC)
    assert bill["adjustment"] == pytest.approx(944.8)
    assert bill["total"] == 8530


def test_demand_under_1_kw_reads_0_kw():
    """第二十八條: 用電最高需量以瓩（kW）為計量單位，小數以下捨棄, as the README
    says (最高需量 counts whole kW). A month with no kWh and a 0.6 kW reading
    reads 0 kWh and 0 kW, so it pays half the basic fee (第四章 五(五)):
    3792.35, cut to 3792.3."""
    demand = pd.Series(0.0, index=JULY)
    demand[pd.Timestamp("2026-07-15 17:00")] = 0.6
    bill = _demand_contract(pd.Series(0.0, index=JULY), demand_kw=demand)
    assert bill["basic_cost"] == pytest.approx(3792.3)
    assert bill["total"] == 3792


@pytest.mark.parametrize("with_demand", [False, True], ids=["no-demand", "demand"])
def test_installed_contract_without_peak_kwh_pays_half_whatever_its_demand(
    with_demand,
):
    """第四章 五(五): 按裝置契約容量計費之用戶，當月份抄見度數（「時間電價」用戶為
    尖峰時間用電）為0度...基本電費按核定電價50%計算. The 裝置契約 rule reads kWh
    only, so 4 kW of metered demand (七(一)2) changes nothing. Half of 2992.5 is
    1496.25, cut to 1496.2, and 384 kWh at 離峰 2.27 is 871.68, cut to 871.6."""
    usage = _sundays(1.0)
    demand = {"demand_kw": usage * 4} if with_demand else {}
    bill = _installed(usage, **demand)
    assert bill["energy_cost"] == pytest.approx(871.6)
    assert bill["basic_cost"] == pytest.approx(1496.2)
    assert bill["total"] == 2368


def test_installed_month_without_peak_kwh_still_adjusts_power_factor():
    """The month in 五(五) pays half its basic fee but used kWh, so 第三十八條
    does not apply and 六 (lines 729-734) moves its bill 1% at 70%. The base
    leaves out the halved 按戶計收 52.5 (五(三)3, line 704): 1% of 1496.2 - 52.5
    + 871.6 is 23.153, cut to 23.1."""
    bill = _installed(_sundays(1.0), power_factor=70)
    assert bill["basic_cost"] == pytest.approx(1496.2)
    assert bill["adjustment"] == pytest.approx(23.1)
    assert bill["total"] == 2391


def test_power_factor_cap_and_over_contract_together():
    """六: 平均功率因數超過95%部分不予扣減, so 99% takes 1.5% off. 七(二)2: 超約
    不給予功率因數扣減, and 2 kW over 31 kW is within 10%, at 2x. 1001 kWh at 尖峰
    5.54 (line 547) is 5545.54, cut to 5545.5. The discount is 1.5% of 7584.7 -
    262.5 + 5545.5, -193.0155, cut to -193.0, and 超約 adds 944.8."""
    peak = (JULY.day_of_week < 5) & (JULY.hour >= 9)
    usage = pd.Series(0.0, index=JULY)
    usage[peak] = 1001 / peak.sum()
    demand = usage * 4
    demand[pd.Timestamp("2026-07-15 17:00")] = 33.0
    bill = _demand_contract(usage, demand_kw=demand, power_factor=99)
    assert bill["energy_cost"] == pytest.approx(5545.5)
    assert bill["basic_cost"] == pytest.approx(DEMAND_31_KW_BASIC)
    assert bill["adjustment"] == pytest.approx(944.8 - 193.0)
    assert bill["total"] == 13882


def test_idle_ev_month_pays_95_percent_of_its_rounded_half_basic_fee():
    """第五章 五(二) (lines 1064-1065) halves the basic fee of a month with no use,
    按戶 included, and 第三十八條 leaves 60% 功率因數 at 80%. Page 16 takes 95% of
    the 低壓 bill rounded to the 元. 262.50 + 47.20 x 281 kW (lines 627-628) is
    13525.7, half is 6762.85, cut to 6762.8 and rounded to 6763, and 95% of
    that is 6424.85, which rounds to 6425. The README lists the 低壓 amounts and
    takes the 5% off in adjustment."""
    bill = _summary(
        pd.Series(0.0, index=JULY),
        "high_voltage_ev",
        contract_capacities={"regular": 281},
        power_factor=60,
    )
    assert bill["basic_cost"] == pytest.approx(6762.8)
    assert bill["adjustment"] == pytest.approx(6425 - 6763)
    assert bill["total"] == 6425
