"""第八章 契約容量之決定: which contract covers which time, worked from its text.

Prices are from src/taipower_tou/data/詳細電價表.md (114/10/1): 低壓電力
非時間電價 lines 523-525 and 高壓 二段式 lines 856-859.
"""

import pandas as pd
import pytest

import taipower_tou as tou

JULY = pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min")
JANUARY = pd.date_range("2026-01-01", "2026-01-31 23:45", freq="15min")


def _demand(index, peaks, kw):
    """kw all month, with the kW in peaks at (day, hour) on that hour."""
    demand = pd.Series(kw, index=index)
    for (day, hour), value in peaks.items():
        demand[(index.day == day) & (index.hour == hour)] = value
    return demand


@pytest.mark.parametrize(
    ("index", "peak_kw", "expected"),
    [
        (JULY, 14, (1 * 2 + 3 * 3) * 236.20),
        (JANUARY, 14, 0.0),
        (JANUARY, 16, 1 * 2 * 173.20),
    ],
    ids=["summer-over-regular", "non-summer-within-both", "non-summer-over-both"],
)
def test_non_tou_non_summer_contract_joins_the_regular_one(index, peak_kw, expected):
    """二(一)1 lines 1542-1546: 非夏月契約容量於非夏月期間併同經常契約容量使用.

    With 10 kW 經常 and 5 kW 非夏月 (第四章 七(二)1(1) lines 746-750), 14 kW
    in July is 4 kW over: 1 kW within 10% at 2x and 3 kW at 3x the 236.20
    經常契約 price. In January 15 kW is the contract."""
    usage = pd.Series(0.25, index=index)
    inputs = tou.BillingInputs(
        taipower_rounding=False,
        contract_capacities={"regular": 10, "non_summer": 5},
        demand_kw=_demand(index, {(14, 10): peak_kw}, kw=5.0),
    )
    bill = tou.calculate_bill(usage, "low_voltage_power", inputs).iloc[0]
    assert bill["adjustment"] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("capacities", "peak"),
    [
        ({"saturday_semi_peak": 300}, (15, 3)),
        ({"saturday_semi_peak": 300}, (18, 17)),
        ({"off_peak": 300}, (15, 3)),
    ],
    ids=[
        "saturday-contract-at-off-peak",
        "saturday-contract-on-saturday",
        "off-peak-contract-at-off-peak",
    ],
)
def test_weekend_only_contract_is_the_contract_for_its_times(capacities, peak):
    """二(一)8 lines 1575-1578: 週六半尖峰契約容量 covers 週六半尖峰 and 離峰
    時間, 離峰契約容量 covers 離峰時間.

    310 kW at those times is 10 kW over the 300 kW contract, within its 10%,
    so 2x the 44.70 週六半尖峰或離峰契約 price (第五章 七(二)1 line 1132)."""
    demand = _demand(JULY, {peak: 310}, kw=100.0 * (JULY.hour < 6))
    inputs = tou.BillingInputs(
        taipower_rounding=False, contract_capacities=capacities, demand_kw=demand
    )
    bill = tou.calculate_bill(demand / 4, "high_voltage_2_tier", inputs).iloc[0]
    assert bill["adjustment"] == pytest.approx(2 * 10 * 44.70)
