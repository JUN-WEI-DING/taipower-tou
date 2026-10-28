"""Bill one household's month on each residential plan and rank the bills."""

from __future__ import annotations

import pandas as pd

import taipower_tou as tou

RESIDENTIAL_PLANS = [
    "residential_non_tou",
    "residential_simple_2_tier",
    "residential_simple_3_tier",
]
# One-month bills on every plan, so they compare. residential_non_tou bills
# two months by default, and its 底度 depends on the meter.
INPUTS = tou.BillingInputs(
    meter_phase="single", meter_voltage_v=110, meter_ampere=20, billing_cycle_months=1
)


def create_household_usage(summer_month: bool = True) -> pd.Series:
    """Hourly kWh for July 2026, or January 2026 if not summer_month."""
    month = 7 if summer_month else 1
    dates = pd.date_range(f"2026-{month:02d}-01", periods=24 * 31, freq="h")
    hour = dates.hour
    day_of_week = dates.day_of_week

    usage_values = []
    for h, dow in zip(hour, day_of_week):
        if dow >= 5:
            usage_values.append(1.0)
        elif 9 <= h < 21:
            usage_values.append(2.5)
        else:
            usage_values.append(0.8)

    return pd.Series(usage_values, index=dates)


def compare_residential_plans(usage: pd.Series) -> pd.DataFrame:
    """Each residential plan's bill for the usage, cheapest first."""
    total_kwh = usage.sum()
    results = []
    for plan_id in RESIDENTIAL_PLANS:
        total_cost = tou.calculate_bill(usage, plan_id, inputs=INPUTS)["total"].sum()
        results.append(
            {
                "plan_id": plan_id,
                "name": tou.plan(plan_id).name,
                "total_cost": total_cost,
                "total_kwh": total_kwh,
                "avg_rate": total_cost / total_kwh,
            }
        )
    df = pd.DataFrame(results).sort_values("total_cost").reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    return df


def print_comparison_table(df: pd.DataFrame, title: str = "Plan Comparison") -> None:
    """Pretty print comparison table."""
    print("=" * 80)
    print(title)
    print("=" * 80)
    print()

    for i, row in df.iterrows():
        rank_emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"  {i + 1}"
        print(f"{rank_emoji} #{row['rank']} {row['name']}")
        print(f"    Cost: {row['total_cost']:8.2f} TWD", end="")
        if "avg_rate" in row:
            print(f"  |  Avg: {row['avg_rate']:.2f} TWD/kWh")
        else:
            print()
        print()

    print("=" * 80)
    print()


def compare_summer_vs_winter() -> None:
    """Compare July and January bills on the two 簡易型 plans."""
    print()
    print("Seasonal Cost Comparison")
    print("=" * 80)

    plans = ["residential_simple_2_tier", "residential_simple_3_tier"]

    print(f"{'Plan':<30} {'Summer (July)':>15} {'Winter (Jan)':>15} {'Difference':>15}")
    print("-" * 80)

    for plan_id in plans:
        plan = tou.plan(plan_id)
        summer_usage = create_household_usage(summer_month=True)
        summer_cost = tou.calculate_bill(summer_usage, plan_id)["total"].sum()
        winter_usage = create_household_usage(summer_month=False)
        winter_cost = tou.calculate_bill(winter_usage, plan_id)["total"].sum()

        diff = summer_cost - winter_cost
        diff_pct = (diff / winter_cost) * 100

        line = (
            f"{plan.name:<30} {summer_cost:10.2f} TWD  {winter_cost:10.2f} TWD  "
            f"{diff:+7.2f} ({diff_pct:+.1f}%)"
        )
        print(line)

    print("=" * 80)


def show_time_of_day_breakdown(usage: pd.Series, plan_id: str) -> None:
    """Show the energy cost by time of day, without the basic fee."""
    print()
    print("Time-of-Day Energy Cost")
    print("=" * 80)

    plan = tou.plan(plan_id)
    breakdown = plan.monthly_breakdown(usage, include_shares=True)

    print(f"{'Period':<15} {'Usage (kWh)':>15} {'Cost (TWD)':>15} {'Cost Share':>12}")
    print("-" * 80)

    for _, row in breakdown.iterrows():
        period_short = str(row["period"])[:12]
        cost_share = row["cost_share"] * 100
        print(
            f"{period_short:<15} {row['usage_kwh']:13.2f}  {row['cost']:13.2f}  "
            f"{cost_share:8.1f}%"
        )

    print("=" * 80)


def main() -> None:
    print("Plan Comparison Example")
    print("=" * 80)
    print()

    usage = create_household_usage(summer_month=True)

    print("Sample Usage: July 2026 (31 days)")
    print(f"  Total: {usage.sum():.1f} kWh")
    print("  Pattern: 2.5 kWh an hour on weekdays 09:00-21:00, less otherwise")
    print()

    print("1. RESIDENTIAL PLANS")
    print("-" * 80)
    df_residential = compare_residential_plans(usage)
    print_comparison_table(df_residential)

    cheapest = df_residential.iloc[0]
    print(f"💡 Recommendation: {cheapest['name']}")
    savings = df_residential["total_cost"].iloc[-1] - cheapest["total_cost"]
    print(f"    Saves {savings:.2f} TWD vs most expensive")
    print()

    show_time_of_day_breakdown(usage, cheapest["plan_id"])
    compare_summer_vs_winter()


if __name__ == "__main__":
    main()
