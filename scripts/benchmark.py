"""Time the package's main calls on a year of 15-minute usage, so a change
that claims to be faster is measured the same way each time.

Usage:

    python scripts/benchmark.py
    python scripts/benchmark.py --repeat 50

Each line is the mean of --repeat runs after one warm-up run. Compare runs
on the same machine only.
"""

from __future__ import annotations

import argparse
import time
import warnings
from typing import Callable

import numpy as np
import pandas as pd

import taipower_tou as tou

INDEX = pd.date_range("2026-01-01", "2026-12-31 23:45", freq="15min")
USAGE = pd.Series(np.random.default_rng(0).uniform(0, 3, len(INDEX)), index=INDEX)
HIGH_VOLTAGE = tou.BillingInputs(contract_capacities={"regular": 100.0})
WITH_DEMAND = tou.BillingInputs(
    contract_capacities={"regular": 100.0}, demand_kw=USAGE * 4, power_factor=90
)


def _meter(contracts: dict[str, float] | None = None) -> tou.BillingInputs:
    return tou.BillingInputs(
        contract_capacities=contracts or {},
        meter_phase="single",
        meter_voltage_v=110,
        meter_ampere=30,
    )


def _all_plans() -> None:
    for plan_id in sorted(tou.available_plans()):
        keys = tou.get_plan_requirements(plan_id)["contract_keys"]
        tou.calculate_bill(USAGE, plan_id, _meter(dict.fromkeys(keys, 100.0)))


CASES: dict[str, Callable[[], object]] = {
    "period_codes": lambda: tou.period_codes(INDEX, "high_voltage_2_tier"),
    "period_context": lambda: tou.period_context(INDEX, "high_voltage_2_tier"),
    "costs": lambda: tou.costs(USAGE, "high_voltage_2_tier"),
    "monthly_breakdown": lambda: tou.monthly_breakdown(USAGE, "high_voltage_2_tier"),
    "calculate_bill high_voltage_2_tier": lambda: tou.calculate_bill(
        USAGE, "high_voltage_2_tier", HIGH_VOLTAGE
    ),
    "calculate_bill with demand and power factor": lambda: tou.calculate_bill(
        USAGE, "high_voltage_2_tier", WITH_DEMAND
    ),
    "calculate_bill_breakdown with demand": lambda: tou.calculate_bill_breakdown(
        USAGE, "high_voltage_2_tier", WITH_DEMAND
    ),
    "calculate_bill residential_non_tou": lambda: tou.calculate_bill(
        USAGE, "residential_non_tou", _meter()
    ),
    "calculate_bill one day": lambda: tou.calculate_bill(
        USAGE[:96], "high_voltage_2_tier", HIGH_VOLTAGE
    ),
    "calculate_bill all 18 plans": _all_plans,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeat", type=int, default=20)
    args = parser.parse_args()
    warnings.simplefilter("ignore")
    print(f"taipower_tou {tou.__version__}, pandas {pd.__version__}")
    for name, call in CASES.items():
        call()
        start = time.perf_counter()
        for _ in range(args.repeat):
            call()
        print(f"{name:46} {(time.perf_counter() - start) / args.repeat * 1000:8.1f} ms")


if __name__ == "__main__":
    main()
