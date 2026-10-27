"""calculate_bill warns when a bill does not cover whole calendar months."""

import warnings

import pandas as pd
import pytest

import taipower_tou as tou

INPUTS = tou.BillingInputs(
    taipower_rounding=False, meter_phase="single", meter_voltage_v=110, meter_ampere=10
)


def _daily(start, end, total):
    days = pd.date_range(start, end, freq="D")
    return pd.Series(total / len(days), index=days)


def _hourly(start, end, total):
    hours = pd.date_range(start, end, freq="h")
    return pd.Series(total / len(hours), index=hours)


BILLS = {
    "faq-reading-period": lambda f: f(
        _daily("2026-09-13", "2026-11-11", 350), "residential_non_tou", INPUTS
    ),
    "one-month-of-two": lambda f: f(
        _daily("2026-09-01", "2026-09-30", 300), "residential_non_tou", INPUTS
    ),
    "monthly-read-on-13th": lambda f: f(
        _hourly("2026-09-13", "2026-10-12 23:00", 2500),
        "residential_simple_2_tier",
        INPUTS,
    ),
}


@pytest.mark.parametrize("bill", BILLS)
@pytest.mark.parametrize("entry", [tou.calculate_bill, tou.calculate_bill_breakdown])
def test_bill_over_part_of_its_months_warns(bill, entry):
    with pytest.warns(tou.PartialPeriodWarning, match="calendar month"):
        BILLS[bill](entry)


@pytest.mark.parametrize(
    ("usage", "plan"),
    [
        (_daily("2026-09-01", "2026-10-31", 600), "residential_non_tou"),
        (_daily("2026-09-01", "2026-12-31", 1200), "residential_non_tou"),
        (_hourly("2026-07-01", "2026-08-31 23:00", 2500), "residential_simple_2_tier"),
    ],
    ids=["two-months", "two-bills", "two-monthly-bills"],
)
def test_bill_over_whole_months_does_not_warn(usage, plan):
    with warnings.catch_warnings():
        warnings.simplefilter("error", tou.PartialPeriodWarning)
        tou.calculate_bill(usage, plan, INPUTS)
