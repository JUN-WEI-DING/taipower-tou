"""Two-month bills on residential_non_tou.

calculate_bill cuts usage into bills of BillingInputs.billing_cycle_months
calendar months, counted from the first month of usage, and
residential_non_tou bills two months at a time by default.
TariffPlan.calculate_costs and monthly_breakdown pair months by the reading
month that BillingCycleType names instead. A two-month period doubles each
tier's kWh either way.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import taipower_tou as tou
from taipower_tou import BillingCycleType

# residential_non_tou has a 底度, so it warns without the meter.
METER = tou.BillingInputs.for_residential(phase="single", voltage=110, ampere=10)


def print_section(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"{title:^70}")
    print(f"{'=' * 70}\n")


def daily_usage(start: str, end: str, total_kwh: float) -> pd.Series:
    """total_kwh spread evenly over the days from start to end."""
    days = pd.date_range(start, end, freq="D")
    return pd.Series(total_kwh / len(days), index=days)


def example_billing_cycle_types() -> None:
    print_section("BillingCycleType on TariffPlan.monthly_breakdown")
    usage = pd.Series(5.0, index=pd.date_range("2025-12-01", "2026-03-31", freq="D"))
    print("5 kWh a day from 2025-12-01 to 2026-03-31.")
    print("Each period is named by its reading month.\n")
    for cycle_type in BillingCycleType:
        plan = tou.plan("residential_non_tou", billing_cycle_type=cycle_type)
        breakdown = plan.monthly_breakdown(usage)
        print(f"{cycle_type.name}:")
        print(breakdown[["month", "usage_kwh", "cost"]].to_string(index=False))
        print()
    print("ODD_MONTH bills December with the next January.")
    print("EVEN_MONTH bills January with February, and December with November.")


def example_tier_doubling() -> None:
    print_section("Tier limits double for a two-month bill")
    print("One month: 0-120 kWh at 1.78, 121-330 kWh at 2.55 summer, 2.26 otherwise.")
    print("Two months: 0-240 kWh at 1.78, 241-660 kWh at 2.55 or 2.26.\n")

    for total_kwh in (200, 300):
        usage = daily_usage("2026-02-01", "2026-03-31", total_kwh)
        bill = tou.calculate_bill(usage, "residential_non_tou", inputs=METER)
        print(f"{total_kwh} kWh in February and March:")
        print(f"  energy_cost {bill['energy_cost'].iloc[0]:.1f} TWD")
    print(f"  200 x 1.78 = {200 * 1.78:.1f}")
    print(f"  240 x 1.78 + 60 x 2.26 = {240 * 1.78 + 60 * 2.26:.1f}")


def example_season_split() -> None:
    print_section("A bill that spans 夏月 and 非夏月")
    print("夏月 is 6/1-9/30 on residential_non_tou.")
    print("610 kWh over May and June 2026, 31 非夏月 days and 30 夏月 days.\n")

    usage = daily_usage("2026-05-01", "2026-06-30", 610)
    breakdown = tou.calculate_bill_breakdown(usage, "residential_non_tou", inputs=METER)
    print(breakdown["details"].to_string(index=False))
    print()
    print(f"energy_cost {breakdown['summary']['energy_cost'].iloc[0]:.1f} TWD")

    non_summer = 240 * 1.78 + 370 * 2.26
    summer = 240 * 1.78 + 370 * 2.55
    weighted = non_summer * 31 / 61 + summer * 30 / 61
    print("All 610 kWh at each season's rates, weighted by its share of the days:")
    print(f"  {non_summer:.1f} x 31/61 + {summer:.1f} x 30/61 = {weighted:.2f}")
    print("  The bill cuts each item to the 角.")


def example_bill_months() -> None:
    print_section("calculate_bill counts bills from the first month of usage")
    hours = pd.date_range("2026-01-01", "2026-04-30 23:00", freq="h")
    rng = np.random.default_rng(seed=0)
    usage = pd.Series(rng.uniform(0.2, 0.5, size=len(hours)), index=hours)
    print(f"Hourly usage from January to April 2026, {usage.sum():.0f} kWh.\n")

    print("residential_non_tou bills January-February and March-April:")
    print(tou.calculate_bill(usage, "residential_non_tou", inputs=METER))
    print()
    print("residential_simple_2_tier bills every month:")
    print(tou.calculate_bill(usage, "residential_simple_2_tier"))
    print()
    print("calculate_bill takes no BillingCycleType. Usage from February")
    print("would make February-March and April-May bills.")


def main() -> None:
    example_billing_cycle_types()
    example_tier_doubling()
    example_season_split()
    example_bill_months()


if __name__ == "__main__":
    main()
