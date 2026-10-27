"""底度 and the 100 元 minimum fee for 表燈非時間電價.

電價表 第三章 五(一)1: 底度 is 2 kWh per ampere for a single-phase low-voltage
meter and 6 kWh per ampere for a three-phase one, and a meter over 10 A counts
as 10 A. A bill under 100 元 a month is charged 100 元, so a two-month bill is
at least 200 元.
"""

import pandas as pd
import pytest

import taipower_tou as tou


def _bill(phase, ampere, months, total_kwh):
    end = "2026-01-31" if months == 1 else "2026-02-28"
    days = pd.date_range("2026-01-01", end, freq="D")
    usage = pd.Series(total_kwh / len(days), index=days)
    inputs = tou.BillingInputs(
        meter_phase=phase,
        meter_voltage_v=220 if phase == "three" else 110,
        meter_ampere=ampere,
        billing_cycle_months=months,
    )
    return tou.calculate_bill(usage, "residential_non_tou", inputs)["total"].iloc[0]


@pytest.mark.parametrize(
    ("phase", "ampere", "months", "total_kwh", "expected"),
    [
        ("single", 30, 1, 0, 100.0),
        ("single", 30, 2, 600, 240 * 1.78 + 360 * 2.26),
        ("three", 30, 1, 0, 60 * 1.78),
        ("three", 30, 2, 0, 120 * 1.78),
    ],
    ids=["single-empty", "single-300-a-month", "three-empty", "three-empty-2m"],
)
def test_meter_over_10_amperes_counts_as_10(phase, ampere, months, total_kwh, expected):
    assert _bill(phase, ampere, months, total_kwh) == pytest.approx(expected)


@pytest.mark.parametrize(("months", "expected"), [(1, 100.0), (2, 200.0)])
def test_minimum_fee_is_100_per_month(months, expected):
    assert _bill("single", 10, months, 0) == pytest.approx(expected)
