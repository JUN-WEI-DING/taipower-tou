"""第四章 電費之計收 of Taipower's 營業規章 and 營業規章施行細則, with amounts
worked from their text.

The 電價表 bills under both. docs/references/營業規章第四章.txt is the 營業規章
chapter (111/9/7), and docs/references/營業規章施行細則第四章.txt the 施行細則
chapter (108/9/17). A test cites 營業規章 when the article is from it, and the
施行細則 otherwise. 營業規章 第三條 (docs/references/營業規章第一章.txt) and
第十二條 (docs/references/營業規章第二章.txt) say what a 需量 is. Prices are
from src/taipower_tou/data/詳細電價表.md (114/10/1), high_voltage_2_tier line
856.
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


@pytest.mark.parametrize(
    ("freq", "readings", "over_kw"),
    [
        ("15min", {"17:00": 220.0}, 20),
        ("5min", {"17:00": 230.0, "17:05": 200.0, "17:10": 200.0}, 10),
    ],
    ids=["one-quarter-hour", "5-minute-readings"],
)
def test_demand_is_the_highest_15_minute_average(freq, readings, over_kw):
    """營業規章 第三條: 需量契約容量：契約上得使用之最大用電需量（十五分鐘平均
    瓩數）, and 第十二條: 需量契約容量以雙方約定最高需量（十五分鐘平均）為契約
    容量. One quarter hour at 220 kW is 20 kW over a 200 kW contract, though its
    hour averages 130 kW. Readings of 230, 200 and 200 kW every 5 minutes average
    210 kW over their quarter hour, 10 kW over. Both are within 10%, at 2x."""
    index = pd.date_range("2026-07-01", "2026-07-31 23:55", freq=freq)
    demand = pd.Series(100.0, index=index)
    for time, kw in readings.items():
        demand[pd.Timestamp(f"2026-07-15 {time}")] = kw
    inputs = tou.BillingInputs(
        contract_capacities={"regular": 200}, demand_kw=demand, taipower_rounding=False
    )
    usage = pd.Series(0.1, index=index)
    bill = tou.calculate_bill(usage, "high_voltage_2_tier", inputs).iloc[0]
    assert bill["adjustment"] == pytest.approx(over_kw * 2 * REGULAR_SUMMER)


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
    單位，角位四捨五入進整. 38 kWh x 5.54 = 210.52 is 210.5 TWD, and 1480.0 +
    210.5 = 1690.5 rounds up to 1691, not to the even 1690."""
    bill = _evening_bill(38, basic_fee_inputs={"裝置契約": 10})
    assert bill["energy_cost"] == pytest.approx(210.5)
    assert bill["basic_cost"] == pytest.approx(1480.0)
    assert bill["total"] == 1691


def test_power_factor_is_worked_from_the_cut_items_and_cut_itself():
    """第二十九條 with 第四章 六: 1 kWh x 5.54 is 5.5 TWD, and 70% adds 1% of
    2750.0 + 5.5 = 27.555, cut to 27.5. A 20 kW 裝置契約 bill pays 105.00 +
    137.50 x 20 = 2855.0."""
    bill = _evening_bill(1, basic_fee_inputs={"裝置契約": 20}, power_factor=70)
    assert bill["adjustment"] == pytest.approx(27.5)
    assert bill["total"] == 2855 + 5.5 + 27.5


@pytest.mark.parametrize(
    ("kwh", "energy", "basic"),
    [(1.18, 5.5, 1480.0), (1.5, 11.0, 1480.0), (0.4, 0.0, 740.0)],
    ids=["1.18-reads-1", "1.5-reads-2", "0.4-reads-0"],
)
def test_kwh_are_read_to_the_whole_kwh_half_up(kwh, energy, basic):
    """第二十八條: 有效電度以瓩小時（kWH）...為計量單位，小數點以下四捨五入進整.
    1.18 kWh at 尖峰 5.54 reads 1 kWh, 5.5 TWD, and 1.5 kWh reads 2, 11.08
    cut to 11.0. 0.4 kWh reads 0, so the 裝置契約 bill has no 尖峰 kWh and pays
    half its basic fee (第四章 五(五), line 712)."""
    bill = _evening_bill(kwh, basic_fee_inputs={"裝置契約": 10})
    assert bill["energy_cost"] == pytest.approx(energy)
    assert bill["basic_cost"] == pytest.approx(basic)


def test_each_time_of_day_is_read_on_its_own_register():
    """README: a 時間電價 meter reads 尖峰, 半尖峰, 週六半尖峰 and 離峰 on registers
    of their own, each rounded by 第二十八條. 1.4 kWh at 尖峰 and 1.4 kWh at
    離峰 (00:00~09:00, 2.27, line 557) read 1 kWh each, 5.54 + 2.27 = 7.81,
    cut to 7.8."""
    usage = pd.Series(0.0, index=JULY)
    usage[pd.Timestamp("2026-07-15 17:00")] = 1.4
    usage[pd.Timestamp("2026-07-15 03:00")] = 1.4
    inputs = tou.BillingInputs(
        billing_cycle_months=1, basic_fee_inputs={"裝置契約": 10}
    )
    bill = tou.calculate_bill(usage, "low_voltage_2_tier", inputs).iloc[0]
    assert bill["energy_cost"] == pytest.approx(7.8)


MAY = pd.date_range("2026-05-01", "2026-05-31 23:45", freq="15min")
NON_SUMMER_PEAK = pd.Timestamp("2026-05-12 10:00")
SUMMER_PEAK = pd.Timestamp("2026-05-20 10:00")


def test_a_register_over_two_seasons_keeps_each_seasons_share():
    """高壓 夏月 starts on 5/16 (line 854). 0.6 kWh at 尖峰 on Friday 5/15 (非夏月
    6.37) and 0.6 kWh on Wednesday 5/20 (夏月 6.75) read 1 kWh on the 尖峰
    register (第二十八條), half in each season: 3.185 + 3.375 = 6.56, cut to
    6.5."""
    usage = pd.Series(0.0, index=MAY)
    usage[pd.Timestamp("2026-05-15 10:00")] = 0.6
    usage[SUMMER_PEAK] = 0.6
    inputs = tou.BillingInputs(contract_capacities={"regular": 200})
    bill = tou.calculate_bill(usage, "high_voltage_2_tier", inputs).iloc[0]
    assert bill["energy_cost"] == pytest.approx(6.5)


def test_a_month_over_the_summer_edge_is_billed_by_each_seasons_days():
    """營業規章 第二十七條 bills a mid-month change 依變更前後按實際使用日數, and
    施行細則 第三十六條 splits a month of changed prices by 使用日數. 高壓 May has
    15 days of 非夏月 and 16 of 夏月 (line 854), so it pays 15/31 of the 非夏月
    basic fee, 166.90 x (200 + 50), and 16/31 of the 夏月 one, 223.60 x 200
    (line 855). Each part's 超約 is its own: 260 kW at 尖峰 on 5/12 is 10 kW
    over 經常 + 非夏月 at 166.90, and 215 kW on 5/20 is 15 kW over 經常 at
    223.60, both 2x within 10% (第五章 七(一)1 and 七(二), lines 1093-1133)."""
    demand = pd.Series(100.0, index=MAY)
    demand[NON_SUMMER_PEAK] = 260.0
    demand[SUMMER_PEAK] = 215.0
    inputs = tou.BillingInputs(
        contract_capacities={"regular": 200, "non_summer": 50},
        demand_kw=demand,
        taipower_rounding=False,
    )
    usage = pd.Series(0.1, index=MAY)
    bill = tou.calculate_bill(usage, "high_voltage_2_tier", inputs).iloc[0]
    basic = 15 / 31 * 166.90 * 250 + 16 / 31 * REGULAR_SUMMER * 200
    over = 15 / 31 * 10 * 2 * 166.90 + 16 / 31 * 15 * 2 * REGULAR_SUMMER
    assert bill["basic_cost"] == pytest.approx(basic)
    assert bill["adjustment"] == pytest.approx(over)


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


@pytest.mark.xfail(strict=True, reason="not supported: no input for a change mid-month")
def test_contract_change_mid_month_prorates_the_basic_fee_by_days():
    """營業規章 第二十七條: 用戶於月中變更用電時...基本電費...依變更前後按實際
    使用日數照核定電價每日以三十分之一計算. 200 kW to 300 kW on 16 July is
    15/30 of 200 kW and 16/30 of 300 kW at 223.60 TWD."""
    changes = {pd.Timestamp("2026-07-16"): {"regular": 300}}
    bill = _bill(contract_changes=changes)
    expected = REGULAR_SUMMER * (200 * 15 / 30 + 300 * 16 / 30)
    assert bill["basic_cost"] == pytest.approx(expected)


@pytest.mark.xfail(strict=True, reason="not supported: no input for outages")
def test_outage_hours_take_3_per_mille_of_the_basic_fee_off():
    """營業規章 第三十九條: 高壓以上電力用戶 扣減電費金額＝基本電費×3‰×停電時數,
    and 第四十條 the same for 遙控卸除用電負載. 2 outage hours take 0.6% off
    a 44720 TWD basic fee."""
    bill = _bill(outage_hours=2)
    assert bill["adjustment"] == pytest.approx(-0.006 * REGULAR_SUMMER * 200)
