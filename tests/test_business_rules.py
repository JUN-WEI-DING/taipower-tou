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
    inputs = tou.BillingInputs(contract_capacities={"regular": 200}, **inputs)
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


@pytest.mark.xfail(
    strict=True,
    reason="open decision: bills are not rounded to 角 and 元 (第二十九條)",
)
def test_bill_items_are_cut_to_the_jiao_and_the_total_rounded_to_the_yuan():
    """第二十九條: 應計電費各項均計至角位，分位以下捨棄；電費總金額...均以元為
    單位，角位四捨五入進整. 1 kWh at 6.75 TWD every 15 minutes in July has an
    energy cost with 分, so the total is a whole number of 元."""
    bill = _bill(kwh=1.0)
    assert bill["total"] == round(bill["total"])
