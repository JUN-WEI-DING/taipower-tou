"""A simulated household's month on residential_simple_2_tier.

The usage has a base load all day, morning and evening use, more daytime use
at weekends, and air conditioning in summer.
"""

from __future__ import annotations

import pandas as pd

import taipower_tou as tou

PLAN = "residential_simple_2_tier"


def create_realistic_household_usage(
    year: int = 2026,
    month: int = 7,
    include_ac: bool = True,
    ac_hours_start: int = 14,
    ac_hours_end: int = 23,
) -> pd.Series:
    """Hourly kWh for one month, with AC from ac_hours_start to ac_hours_end
    on summer days."""
    start = pd.Timestamp(year, month, 1)
    dates = pd.date_range(start, periods=24 * start.days_in_month, freq="h")

    usage_values = []
    for dt in dates:
        hour = dt.hour
        dow = dt.day_of_week
        is_summer = month in [6, 7, 8, 9]
        is_weekend = dow >= 5

        base_load = 0.15  # Refrigerator, WiFi router, standby devices
        morning_load = 0.0
        daytime_load = 0.0
        evening_load = 0.0
        night_load = 0.0
        ac_load = 0.0

        if 6 <= hour < 9:
            morning_load = 0.8 if is_weekend else 1.2  # Shower pump, cooking

        if 9 <= hour < 17:
            if is_weekend:
                daytime_load = 1.0
            else:
                daytime_load = 0.3  # Most people at work

        if 17 <= hour < 23:
            if is_weekend:
                evening_load = 1.5
            else:
                evening_load = 2.0

        if hour >= 23 or hour < 6:
            night_load = 0.2

        if include_ac and is_summer:
            if ac_hours_start <= hour < ac_hours_end:
                if is_weekend:
                    ac_load = 1.5  # Weekend AC use
                else:
                    ac_load = 2.5  # Weekday AC use (higher temp)

        total = (
            base_load
            + morning_load
            + daytime_load
            + evening_load
            + night_load
            + ac_load
        )
        usage_values.append(total)

    return pd.Series(usage_values, index=dates)


def calculate_monthly_bill(usage: pd.Series) -> pd.DataFrame:
    """The month's bill, with its basic fee."""
    inputs = tou.BillingInputs.for_residential(phase="single", voltage=110, ampere=20)
    return tou.calculate_bill(usage, PLAN, inputs=inputs)


def show_consumption_analysis(usage: pd.Series) -> None:
    """Analyze consumption patterns."""
    print("=" * 70)
    print("Consumption Analysis")
    print("=" * 70)

    total_kwh = usage.sum()
    daily_avg = total_kwh / len(usage) * 24
    # 尖峰 is on weekdays only. Saturdays and 離峰日 are 離峰 all day.
    by_period = tou.monthly_breakdown(usage, PLAN).groupby("period")["usage_kwh"].sum()
    weekday_usage = usage[usage.index.day_of_week < 5].sum()
    weekend_usage = usage[usage.index.day_of_week >= 5].sum()

    print(f"Total Monthly Usage:      {total_kwh:8.2f} kWh")
    print(f"Daily Average:            {daily_avg:8.2f} kWh/day")
    print()
    for period, kwh in by_period.items():
        share = kwh / total_kwh * 100
        print(f"{period + ':':<26}{kwh:8.2f} kWh ({share:5.1f}%)")
    print()
    print(f"Weekday Usage:            {weekday_usage:8.2f} kWh")
    print(f"Weekend Usage:            {weekend_usage:8.2f} kWh")
    print("=" * 70)
    print()


def show_appliance_breakdown(usage: pd.Series) -> None:
    """Estimate usage by appliance category."""
    print("=" * 70)
    print("Estimated Appliance Breakdown")
    print("=" * 70)

    total_kwh = usage.sum()
    base_load_kwh = 0.15 * len(usage)
    ac_hours = (usage.index.hour >= 14) & (usage.index.hour < 23)
    ac_hours_count = ac_hours.sum()
    ac_kwh = 2.0 * ac_hours_count  # Approx 2 kW when running
    other_kwh = total_kwh - base_load_kwh - ac_kwh

    base_pct = base_load_kwh / total_kwh * 100
    print(f"Base Load (24/7):        {base_load_kwh:8.2f} kWh ({base_pct:5.1f}%)")
    print("  - Refrigerator, WiFi, standby")
    print()
    ac_pct = ac_kwh / total_kwh * 100
    print(f"Air Conditioning:         {ac_kwh:8.2f} kWh ({ac_pct:5.1f}%)")
    print(f"  - ~{ac_hours_count} hours at ~2 kW")
    print()
    other_pct = other_kwh / total_kwh * 100
    print(f"Other Appliances:        {other_kwh:8.2f} kWh ({other_pct:5.1f}%)")
    print("  - Cooking, shower, TV, lights")
    print("=" * 70)
    print()


def suggest_cost_saving_tips(usage: pd.Series, bill: pd.DataFrame) -> None:
    """Suggest cost-saving tips based on usage patterns."""
    print("=" * 70)
    print("Money-Saving Tips")
    print("=" * 70)

    breakdown = tou.monthly_breakdown(usage, PLAN).set_index("period")
    peak, off_peak = breakdown.loc["peak"], breakdown.loc["off_peak"]
    peak_rate = peak["cost"] / peak["usage_kwh"]
    off_peak_rate = off_peak["cost"] / off_peak["usage_kwh"]
    shifted_kwh = peak["usage_kwh"] * 0.2
    potential_savings = shifted_kwh * (peak_rate - off_peak_rate)

    print("💡 Shift 20% of peak usage to off-peak:")
    print(f"    Save ~{potential_savings:.2f} TWD/month")
    print("   - Run dishwasher/washing machine at night")
    print("   - Set AC timer to cool room before peak hours")
    print()

    total_kwh = usage.sum()
    ac_kwh = 2.0 * ((usage.index.hour >= 14) & (usage.index.hour < 23)).sum()
    ac_pct = ac_kwh / total_kwh * 100

    print(f"💡 AC accounts for ~{ac_pct:.0f}% of your kWh")
    print("   - Set AC to 26-28°C instead of 24-25°C")
    print("   - Use fan during cooler hours")
    print("   - Close curtains during hot hours")
    print()

    weekday_avg = usage[usage.index.day_of_week < 5].mean()
    weekend_avg = usage[usage.index.day_of_week >= 5].mean()

    if weekday_avg > weekend_avg:
        print("💡 Weekday usage is higher: Consider weekend activities")
        print(f"   - Weekday: {weekday_avg:.2f} kWh/hour avg")
        print(f"   - Weekend: {weekend_avg:.2f} kWh/hour avg")

    print("=" * 70)


def main() -> None:
    print("Household Electricity Cost Calculator")
    print("=" * 70)
    print()

    print("Scenario: July 2026 (Summer) with Air Conditioning")
    print("-" * 70)

    usage_july = create_realistic_household_usage(year=2026, month=7, include_ac=True)
    show_consumption_analysis(usage_july)
    show_appliance_breakdown(usage_july)

    bill_july = calculate_monthly_bill(usage_july)

    print("Monthly Bill Breakdown:")
    print("-" * 70)
    print(f"Energy Cost:    {bill_july['energy_cost'].iloc[0]:8.2f} TWD")
    print(f"Basic Fee:      {bill_july['basic_cost'].iloc[0]:8.2f} TWD")
    print(f"Total Bill:      {bill_july['total'].iloc[0]:8.2f} TWD")
    print()

    suggest_cost_saving_tips(usage_july, bill_july)

    print()
    print("Scenario: January 2026 (Winter) - No AC")
    print("-" * 70)

    usage_jan = create_realistic_household_usage(year=2026, month=1, include_ac=False)
    bill_jan = calculate_monthly_bill(usage_jan)

    total_july = bill_july["total"].iloc[0]
    total_jan = bill_jan["total"].iloc[0]

    print(f"Total Bill: {total_jan:8.2f} TWD")
    print()
    print(f"Summer vs Winter: July costs {total_july - total_jan:+.2f} TWD more")

    print()
    print("=" * 70)
    print("Example Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
