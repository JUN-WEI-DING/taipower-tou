import warnings
from datetime import datetime

import pandas as pd
import pytest

import taipower_tou as tou

# The warnings these tests cause on purpose. Any other fails them.
pytestmark = [
    # dates outside the bundled price table
    pytest.mark.filterwarnings("ignore::taipower_tou.UncheckedPriceWarning"),
    # bills that cover part of a month
    pytest.mark.filterwarnings("ignore::taipower_tou.PartialPeriodWarning"),
    # readings a whole number of days apart
    pytest.mark.filterwarnings("ignore:Usage timestamps are"),
]


def test_calculate_bill_basic_fee() -> None:
    index = pd.to_datetime(["2025-07-15 10:00", "2025-07-15 23:00"])
    usage = pd.Series([1.0, 2.0], index=index)
    result = tou.calculate_bill(
        usage,
        "residential_simple_2_tier",
    )

    assert list(result.columns) == [
        "energy_cost",
        "basic_cost",
        "surcharge",
        "adjustment",
        "total",
    ]
    assert result["basic_cost"].iloc[0] == 75.0
    items = result[["energy_cost", "basic_cost", "surcharge", "adjustment"]].sum(axis=1)
    assert ((result["total"] - items).abs() <= 0.5).all()


def test_calculate_bill_minimum_usage_rule() -> None:
    index = pd.to_datetime([datetime(2025, 7, 1, 0, 0)])
    usage = pd.Series([0.0], index=index)
    inputs = tou.BillingInputs(
        taipower_rounding=False,
        meter_phase="single",
        meter_voltage_v=110,
        meter_ampere=10,
    )
    result = tou.calculate_bill(
        usage,
        "residential_non_tou",
        inputs=inputs,
    )

    assert result["energy_cost"].iloc[0] > 0


def test_calculate_bill_two_month_cycle() -> None:
    index = pd.to_datetime(["2025-07-01 00:00", "2025-08-01 00:00"])
    usage = pd.Series([10.0, 10.0], index=index)
    inputs = tou.BillingInputs(
        taipower_rounding=False,
        meter_phase="single",
        meter_voltage_v=110,
        meter_ampere=10,
    )
    result = tou.calculate_bill(
        usage,
        "residential_non_tou",
        inputs=inputs,
    )
    assert len(result.index) == 1


def test_calculate_bill_breakdown() -> None:
    index = pd.to_datetime(["2025-07-15 10:00", "2025-07-15 23:00"])
    usage = pd.Series([1.0, 2.0], index=index)
    breakdown = tou.calculate_bill_breakdown(
        usage,
        "residential_simple_2_tier",
    )

    assert {"summary", "details", "basic_details", "adjustment_details"} <= set(
        breakdown.keys()
    )
    summary = breakdown["summary"]
    details = breakdown["details"]
    basic_details = breakdown["basic_details"]
    adjustment_details = breakdown["adjustment_details"]
    assert "total" in summary.columns
    assert {"period", "season", "period_type", "usage_kwh", "energy_cost"} <= set(
        details.columns
    )
    assert {"period", "label", "quantity", "rate", "cost"} <= set(basic_details.columns)
    if not adjustment_details.empty:
        assert {"period", "type", "amount"} <= set(adjustment_details.columns)


def test_calculate_bill_rejects_negative_usage() -> None:
    usage = pd.Series(
        [1.0, -0.5],
        index=pd.to_datetime(["2025-07-15 10:00", "2025-07-15 11:00"]),
    )
    with pytest.raises(tou.InvalidUsageInput):
        tou.calculate_bill(usage, "residential_simple_2_tier")


def test_calculate_bill_rejects_nan_usage() -> None:
    usage = pd.Series(
        [1.0, float("nan")],
        index=pd.to_datetime(["2025-07-15 10:00", "2025-07-15 11:00"]),
    )
    with pytest.raises(tou.InvalidUsageInput):
        tou.calculate_bill(usage, "residential_simple_2_tier")


def test_calculate_bill_rejects_infinite_usage() -> None:
    usage = pd.Series(
        [1.0, float("inf")],
        index=pd.to_datetime(["2025-07-15 10:00", "2025-07-15 11:00"]),
    )
    with pytest.raises(tou.InvalidUsageInput):
        tou.calculate_bill(usage, "residential_simple_2_tier")


def test_calculate_bill_rejects_unsorted_usage() -> None:
    usage = pd.Series(
        [1.0, 2.0],
        index=pd.to_datetime(["2025-07-15 11:00", "2025-07-15 10:00"]),
    )
    with pytest.raises(tou.InvalidUsageInput):
        tou.calculate_bill(usage, "residential_simple_2_tier")


def test_calculate_bill_breakdown_rejects_invalid_usage() -> None:
    usage = pd.Series(
        [1.0, -0.5],
        index=pd.to_datetime(["2025-07-15 10:00", "2025-07-15 11:00"]),
    )
    with pytest.raises(tou.InvalidUsageInput):
        tou.calculate_bill_breakdown(usage, "residential_simple_2_tier")


def test_for_residential_does_not_warn_unknown_basic_fee() -> None:
    usage = pd.Series([1.0], index=pd.to_datetime(["2025-07-15 10:00"]))
    inputs = tou.BillingInputs.for_residential(phase="single", voltage=110, ampere=10)
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        tou.calculate_bill(
            usage,
            "residential_simple_2_tier",
            inputs=inputs,
        )
    assert not any("Unknown keys in basic_fee_inputs" in str(w.message) for w in record)


def test_bimonthly_tiers_are_doubled() -> None:
    """電價表：用戶因2個月抄表、收費一次，計費時各段度數係加倍計算。"""
    usage = pd.Series(200.0, index=pd.to_datetime(["2026-07-10", "2026-08-10"]))
    inputs = tou.BillingInputs(
        taipower_rounding=False,
        meter_phase="single",
        meter_voltage_v=110,
        meter_ampere=10,
    )
    bill = tou.calculate_bill(usage, "residential_non_tou", inputs=inputs)
    assert bill["energy_cost"].tolist() == pytest.approx([240 * 1.78 + 160 * 2.55])


def test_monthly_tiers_are_not_doubled() -> None:
    usage = pd.Series([200.0], index=pd.to_datetime(["2026-07-10"]))
    inputs = tou.BillingInputs(
        taipower_rounding=False,
        meter_phase="single",
        meter_voltage_v=110,
        meter_ampere=10,
        billing_cycle_months=1,
    )
    bill = tou.calculate_bill(usage, "residential_non_tou", inputs=inputs)
    assert bill["energy_cost"].tolist() == pytest.approx([120 * 1.78 + 80 * 2.55])


def test_for_high_voltage_names_the_four_contracts():
    """for_high_voltage is BillingInputs with its four contracts by key."""
    demand = pd.Series(80.0, index=pd.date_range("2026-07-01", periods=4, freq="15min"))
    inputs = tou.BillingInputs.for_high_voltage(
        200, 10, 20, 30, power_factor=90, demand_kw=demand
    )
    assert inputs.contract_capacities == {
        "regular": 200,
        "non_summer": 10,
        "saturday_semi_peak": 20,
        "off_peak": 30,
    }
    assert inputs.power_factor == 90
    assert inputs.demand_kw is demand
