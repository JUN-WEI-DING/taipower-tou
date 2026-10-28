"""Read hourly usage from a CSV file, price it, and write each hour's cost."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import taipower_tou as tou


def create_sample_csv(filename: str = "sample_usage.csv") -> None:
    """Create a sample CSV file for demonstration."""
    dates = pd.date_range("2026-07-01", periods=24 * 7, freq="h")  # 1 week
    data = {
        "timestamp": dates.strftime("%Y-%m-%d %H:%M"),
        "usage_kwh": [1.0 + (i % 3) * 0.5 for i in range(len(dates))],
    }
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"Created sample file: {filename}")


def import_from_csv_format_a(filename: str) -> pd.Series:
    """Import CSV Format A: timestamp and usage columns."""
    df = pd.read_csv(filename, encoding="utf-8-sig")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.set_index("timestamp")["usage_kwh"]


def import_from_csv_format_b(filename: str) -> pd.Series:
    """Import CSV Format B: Chinese column names."""
    df = pd.read_csv(filename, encoding="utf-8-sig")
    df["時間"] = pd.to_datetime(df["時間"])
    return df.set_index("時間")["用電度數"]


def import_from_csv_format_c(filename: str) -> pd.Series:
    """Import CSV Format C: cumulative meter readings, one kWh total per row."""
    df = pd.read_csv(filename, encoding="utf-8-sig")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime")
    return df["reading"].diff().fillna(0)


def calculate_and_show(
    usage: pd.Series, plan_name: str = "residential_simple_2_tier"
) -> None:
    """Print the energy cost, without the basic fee, and its breakdown."""
    print("=" * 60)
    print("Energy Cost Calculation")
    print("=" * 60)
    print()

    start_date = usage.index.min()
    end_date = usage.index.max()
    plan = tou.plan(plan_name)
    costs = plan.calculate_costs(usage)
    breakdown = plan.monthly_breakdown(usage, include_shares=True)

    print(f"Plan: {plan.name}")
    print(
        f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )
    print()

    print(f"Total Usage: {usage.sum():.2f} kWh")
    print(f"Energy Cost: {costs.sum():.2f} TWD")
    print(f"Average Rate: {costs.sum() / usage.sum():.2f} TWD/kWh")
    print()

    print("Monthly Breakdown:")
    print(breakdown.to_string(index=False))
    print()


def export_to_csv(
    usage: pd.Series,
    plan_id: str = "residential_simple_2_tier",
    filename: str = "result.csv",
) -> None:
    """Write each hour's price and energy cost to a CSV file."""
    context = tou.pricing_context(usage.index, plan_id, usage=usage)
    result = pd.DataFrame(
        {
            "timestamp": usage.index.strftime("%Y-%m-%d %H:%M"),
            "usage_kwh": usage.values,
            "rate_twd_per_kwh": context["rate"].values,
            "cost_twd": context["cost"].values,
        }
    )
    result.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"Results exported to: {filename}")


def main() -> None:
    print("CSV Import Example")
    print("=" * 60)
    print()

    print("Step 1: Creating sample CSV file...")
    create_sample_csv("sample_usage.csv")
    print()

    print("Step 2: Importing CSV file...")
    usage = import_from_csv_format_a("sample_usage.csv")
    print(f"Imported {len(usage)} records")
    print(f"Date range: {usage.index.min()} to {usage.index.max()}")
    print()

    print("Step 3: Calculating electricity costs...")
    calculate_and_show(usage)
    print()

    print("Step 4: Exporting results to CSV...")
    export_to_csv(usage, "residential_simple_2_tier", "result.csv")
    print()

    Path("sample_usage.csv").unlink(missing_ok=True)
    Path("result.csv").unlink(missing_ok=True)

    print("=" * 60)
    print("CSV Import Example Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
