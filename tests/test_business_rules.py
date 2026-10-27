"""營業規章 第四章 電費之計收, with amounts worked from its text.

docs/references/營業規章第四章.txt is the text of Taipower's 營業規章 chapter 4,
which the 電價表 bills under. Prices are from
src/taipower_tou/data/詳細電價表.md (114/10/1), high_voltage_2_tier line 856.
"""

import pandas as pd
import pytest

import taipower_tou as tou

JULY = pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min")
REGULAR_SUMMER = 223.60


def _bill(demand_peak=None, kwh=0.25, **inputs):
    usage = pd.Series(kwh, index=JULY)
    if demand_peak is not None:
        demand = pd.Series(100.0, index=JULY)
        demand[(JULY.day == 15) & (JULY.hour == 17)] = demand_peak
        inputs["demand_kw"] = demand
    inputs = tou.BillingInputs(
        contract_capacities={"regular": 200}, taipower_rounding=False, **inputs
    )
    return tou.calculate_bill(usage, "high_voltage_2_tier", inputs).iloc[0]


def test_highest_demand_drops_the_fraction_of_a_kw():
    """第二十八條: 用電最高需量以瓩（kW）為計量單位，小數以下捨棄. 205.9 kW on a
    200 kW contract is 5 kW over, at 2x within 10%."""
    bill = _bill(demand_peak=205.9)
    assert bill["adjustment"] == pytest.approx(5 * 2 * REGULAR_SUMMER)


@pytest.mark.parametrize(("power_factor", "share"), [(70, 0.01), (90, 0.0)])
def test_power_factor_below_80_also_adjusts_the_over_contract_fee(power_factor, share):
    """第三十條: 計算功率因數調整費，包括流動電費、按契約容量計收之基本電費及超出
    契約容量之非約定基本電費；惟功率因數在80％（含）以上之超約用戶，不另計算非約定
    基本電費之功率因數調整費. At 70% the 5 kW 超約 fee rises 1% with the rest of
    the bill. At 90% it gets no discount, as 第五章 七(二) also says."""
    over = 5 * 2 * REGULAR_SUMMER
    bill = _bill(demand_peak=205, power_factor=power_factor)
    month = bill["basic_cost"] + bill["energy_cost"]
    pf_share = (80 - power_factor) / 1000
    assert bill["adjustment"] == pytest.approx(pf_share * month + over * (1 + share))


def test_month_without_use_counts_power_factor_as_80():
    """第三十八條: 全月均無用電之用戶，當月功率因數按80％計算. The month pays half
    its basic fee (第五章 五(二)) and no 功率因數 change."""
    bill = _bill(kwh=0.0, power_factor=60)
    assert bill["adjustment"] == pytest.approx(0.0)
    assert bill["total"] == pytest.approx(0.5 * REGULAR_SUMMER * 200)


def _evening_bill(kwh, **inputs):
    """low_voltage_2_tier for July 2026, with kwh at 17:00 on Wednesday the 15th
    (尖峰 5.54 TWD, 第四章 line 547) and a 裝置契約 (按戶 105.00, 137.50 per kW,
    lines 535-537)."""
    usage = pd.Series(0.0, index=JULY)
    usage[pd.Timestamp("2026-07-15 17:00")] = kwh
    inputs = tou.BillingInputs(billing_cycle_months=1, meter_phase="three", **inputs)
    return tou.calculate_bill(usage, "low_voltage_2_tier", inputs).iloc[0]


def test_bill_items_are_cut_to_the_jiao_and_the_total_rounded_half_up():
    """第二十九條: 應計電費各項均計至角位，分位以下捨棄；電費總金額...均以元為
    單位，角位四捨五入進整. 1.18 kWh x 5.54 = 6.5372 is 6.5 TWD, and 1480.0 +
    6.5 = 1486.5 rounds up to 1487, not to the even 1486."""
    bill = _evening_bill(1.18, basic_fee_inputs={"裝置契約": 10})
    assert bill["energy_cost"] == pytest.approx(6.5)
    assert bill["basic_cost"] == pytest.approx(1480.0)
    assert bill["total"] == 1487


def test_power_factor_is_worked_from_the_cut_items_and_cut_itself():
    """第二十九條 with 第四章 六: 70% adds 1% of 2750.0 + 6.5 = 27.565, cut to
    27.5. A 20 kW 裝置契約 bill pays 105.00 + 137.50 x 20 = 2855.0."""
    bill = _evening_bill(1.18, basic_fee_inputs={"裝置契約": 20}, power_factor=70)
    assert bill["adjustment"] == pytest.approx(27.5)
    assert bill["total"] == 2855 + 6.5 + 27.5


def test_rounding_can_be_turned_off():
    bill = _evening_bill(
        1.18, basic_fee_inputs={"裝置契約": 10}, taipower_rounding=False
    )
    assert bill["energy_cost"] == pytest.approx(1.18 * 5.54)
    assert bill["total"] == pytest.approx(1480 + 1.18 * 5.54)


@pytest.mark.xfail(strict=True, reason="not supported: no input for 農業動力用電")
def test_agricultural_power_with_no_load_pays_no_basic_fee():
    """第四十條: 農業動力用電...用電負載率為零者，基本電費免收, where other users
    pay half (第四章 五(五))."""
    usage = pd.Series(0.0, index=JULY)
    inputs = tou.BillingInputs(
        basic_fee_inputs={"裝置契約": 10}, agricultural_power=True
    )
    bill = tou.calculate_bill(usage, "low_voltage_power", inputs).iloc[0]
    assert bill["total"] == pytest.approx(0.0)


@pytest.mark.xfail(strict=True, reason="not supported: no input for 優待付費 users")
@pytest.mark.parametrize(
    ("discount", "kwh"), [("military_family", 300), ("retiree_family", 250)]
)
def test_family_discounts_halve_the_first_kwh(discount, kwh):
    """第四十二條: 現役軍人家屬...每月用電在三百度以下部分...補助半數. 第四十四條:
    支領退休俸...人員家屬...二百五十度以下部分...補助半數. A month at the limit pays
    half its 非時間 energy cost."""
    usage = pd.Series(kwh / len(JULY), index=JULY)
    full = tou.calculate_bill(
        usage, "residential_non_tou", tou.BillingInputs(billing_cycle_months=1)
    ).iloc[0]
    inputs = tou.BillingInputs(billing_cycle_months=1, **{discount: True})
    bill = tou.calculate_bill(usage, "residential_non_tou", inputs).iloc[0]
    assert bill["energy_cost"] == pytest.approx(0.5 * full["energy_cost"])
