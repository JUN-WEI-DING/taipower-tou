"""calculate_bill with and without BillingInputs, and its breakdown."""

from __future__ import annotations

import pandas as pd

import taipower_tou as tou


def main() -> None:
    # Whole calendar months, so no bill is partial. residential_non_tou bills
    # two months at a time.
    hours = pd.date_range("2026-07-01", "2026-08-31 23:00", freq="h")
    usage = pd.Series(1.0, index=hours)

    print("simple_bill:")
    print(tou.calculate_bill_simple(usage, "residential_simple_2_tier"))

    # residential_non_tou's 底度 depends on the meter.
    inputs = tou.BillingInputs.for_residential(phase="single", voltage=110, ampere=10)
    print("advanced_bill:")
    print(tou.calculate_bill(usage, "residential_non_tou", inputs=inputs))

    # 120 kW of demand on 2026-07-15 against a 100 kW 經常契約 pays 超約.
    demand_index = pd.date_range("2026-07-15 00:00", periods=96, freq="15min")
    demand_kw = pd.Series(120.0, index=demand_index)
    inputs = tou.BillingInputs(
        contract_capacities={
            "regular": 100,
            "non_summer": 20,
            "saturday_semi_peak": 10,
            "off_peak": 10,
        },
        demand_kw=demand_kw,
        power_factor=82,
    )
    print("advanced_bill_demand:")
    print(tou.calculate_bill(usage, "high_voltage_2_tier", inputs=inputs))

    print("breakdown:")
    breakdown = tou.calculate_bill_breakdown(usage, "residential_simple_2_tier")
    print(breakdown["summary"])
    print(breakdown["details"])


if __name__ == "__main__":
    main()
