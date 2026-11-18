"""需量 and 超約: each 需量 as Taipower reads it, the 超約瓩數 over each
contract, and its fee."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from taipower_tou import _warnings
from taipower_tou.billing_inputs import BillingInputs
from taipower_tou.calendar import taiwan_wall_time
from taipower_tou.errors import (
    TariffError,
)
from taipower_tou.factory import (
    OverContractRule,
    PlanRules,
)


def _quarter_hour_demand(demand: pd.Series) -> pd.Series:
    """營業規章 第三條: 需量 is the 十五分鐘平均瓩數, so readings finer than 15
    minutes are averaged over each quarter hour."""
    if len(demand) < 2:
        return demand
    if demand.index.to_series().diff().median() >= pd.Timedelta("15min"):
        return demand
    return demand.resample("15min").mean().dropna()


def _check_demand_resolution(demand: pd.Series) -> None:
    """Warn when demand readings are more than 15 minutes apart. 需量 is a
    15-minute average (營業規章 第三條), so coarser readings can miss the
    最高需量."""
    if len(demand) < 2:
        return

    minutes = demand.index.to_series().diff().median().total_seconds() / 60
    if minutes > 15:
        _warnings.warn(
            f"Demand data resolution is approximately {int(minutes)} minutes, "
            f"which is coarser than the recommended 15-minute resolution. "
            f"Taiwan Power Company calculates demand penalties based on 15-minute "
            f"intervals. Using coarser data may underestimate peak demand and result "
            f"in inaccurate penalty calculations. "
            f"Consider using 'demand_adjustment_factor' parameter to apply a "
            f"conservative adjustment (e.g., 1.1-1.2 for hourly data).",
            UserWarning,
        )


def _read_demand(
    inputs: BillingInputs,
    profile: Any,
    bills: Callable[[pd.DatetimeIndex], pd.PeriodIndex],
    local: pd.DatetimeIndex,
    lookup: Any,
    times: np.ndarray,
    billing_periods: pd.PeriodIndex,
) -> pd.DataFrame | None:
    """Each 需量 as Taipower reads it, in Taiwan wall time, with the bill,
    season and time it falls in. 需量 is the 十五分鐘平均瓩數 (營業規章 第三條),
    times demand_adjustment_factor, cut to whole kW (施行細則 第二十八條).
    Demand on the usage's own timestamps reuses the usage's lookup."""
    demand = inputs.demand_kw
    if demand is None:
        return None
    demand = pd.Series(
        demand.to_numpy(dtype="float64"), index=taiwan_wall_time(demand.index)
    )
    _check_demand_resolution(demand)
    demand = _quarter_hour_demand(demand) * inputs.demand_adjustment_factor
    if not demand.index.equals(local):
        lookup = profile.engine.lookup(demand.index)
        times = _times(lookup)
        billing_periods = bills(demand.index)
    return pd.DataFrame(
        {
            "kw": np.floor(np.round(demand.to_numpy(), 6)),
            "bill": billing_periods,
            "season": lookup.season_names(),
            "time": times,
        },
        index=demand.index,
    )


def _times(lookup: Any) -> np.ndarray:
    """Each timestamp's time of day: 尖峰, 半尖峰, 週六半尖峰 or 離峰, the
    register its kWh is read on and the time its 最高需量 counts in. A
    非時間電價 meter has one register, and one 最高需量 against 經常 (+ 非夏月).
    Decided once per day type and period, then expanded by position."""
    periods = np.array(
        ["peak" if name == "flat" else name for name in lookup.period_names()],
        dtype=object,
    )
    saturday = np.array(
        [name == "saturday" for name in lookup.day_type_names()], dtype=bool
    )
    table = np.where(
        saturday[:, None] & (periods == "semi_peak")[None, :],
        "saturday_semi_peak",
        periods[None, :],
    ).astype(object)
    return table[lookup.day_of, lookup.period]


_SEGMENT_FEE_LABELS = {
    "peak": "regular_label",
    "semi_peak": "semi_peak_label",
    "saturday_semi_peak": "saturday_label",
    "off_peak": "off_peak_label",
}


def _times_outside_contract(capacities: dict[str, float]) -> set[str]:
    """Times a 週六半尖峰 or 離峰 contract alone does not cover (第八章 二(一)8).

    A 週六半尖峰契約容量 covers 週六半尖峰 and 離峰, a 離峰契約容量 離峰 only.
    Any other contract covers every time.
    """
    if any(capacities.get(k) for k in ("regular", "non_summer", "semi_peak")):
        return set()
    if capacities.get("saturday_semi_peak"):
        return {"peak", "semi_peak"}
    if capacities.get("off_peak"):
        return {"peak", "semi_peak", "saturday_semi_peak"}
    return set()


def _compute_over_contract_kw(
    inputs: BillingInputs,
    demand: pd.DataFrame | None,
    parts: dict[pd.Timestamp, dict[str, float]],
    oc_rule: OverContractRule,
    outside: set[str],
) -> dict[pd.Timestamp, dict[str, dict[str, tuple[float, float]]]] | None:
    """Each bill's 超約瓩數 in each of its seasons, with the contract it is
    over, by time in the order the 電價表 deducts them."""
    if inputs.over_contract_kw is not None:
        contract_kw = inputs.contract_capacities.get("regular", 0.0)
        over = {"peak": (float(inputs.over_contract_kw), contract_kw)}
        return {ts: dict.fromkeys(seasons, over) for ts, seasons in parts.items()}
    if demand is None:
        return None
    highest: dict[tuple[pd.Timestamp, str], dict[str, float]] = {
        (ts, season): {} for ts, seasons in parts.items() for season in seasons
    }
    peaks = demand.groupby(["bill", "season", "time"])["kw"].max()
    for (bill, season, time), kw in peaks.items():
        if (bill.to_timestamp(), season) in highest:
            highest[(bill.to_timestamp(), season)][time] = kw
    return {
        ts: {
            season: _calculate_over_contract_from_categories(
                highest[(ts, season)],
                inputs.contract_capacities,
                oc_rule,
                season,
                outside,
            )
            for season in seasons
        }
        for ts, seasons in parts.items()
    }


def _calculate_over_contract_from_categories(
    max_demand: dict[str, float],
    capacities: dict[str, float],
    oc_rule: OverContractRule,
    season: str,
    outside: set[str],
) -> dict[str, tuple[float, float]]:
    """超約瓩數 per time from each time's highest demand (第五章 七(一)).

    Each time's excess leaves out the largest excess of the times before it,
    so no kW is counted twice.
    """
    regular = capacities.get("regular", 0.0)
    if oc_rule.tier == "three_stage":
        second, second_kw = "semi_peak", capacities.get("semi_peak", 0.0)
        peak_base = regular
    else:
        second, second_kw = None, capacities.get("non_summer", 0.0)
        # 夏月尖峰時間超約瓩數＝當月尖峰時間用電最高需量－經常契約容量.
        peak_base = regular if season == "summer" else regular + second_kw
    bases = {"peak": peak_base}
    if second:
        bases[second] = regular + second_kw
    bases["saturday_semi_peak"] = (
        regular + second_kw + capacities.get("saturday_semi_peak", 0.0)
    )
    bases["off_peak"] = bases["saturday_semi_peak"] + capacities.get("off_peak", 0.0)

    over: dict[str, tuple[float, float]] = {}
    largest = 0.0
    for segment, base in bases.items():
        excess = max(0.0, max_demand.get(segment, 0.0) - base)
        if segment in outside:
            # Billed at 4.8x on its own 最高需量, not 超約 later times deduct.
            over[segment] = (excess, base)
            continue
        over[segment] = (max(0.0, excess - largest), base)
        largest = max(largest, excess)
    return over


def _over_contract_fee(
    rules: PlanRules,
    oc_rule: OverContractRule,
    over: dict[str, tuple[float, float]],
    season: str,
    outside: set[str],
) -> float:
    """A month's 超約 fee at a season's prices. 超出部分依適用電價，在契約容量10%
    以下部分按2倍、超過部分按3倍 (第三章 五(三)5, 第四章 七(二), 第五章 七(二)).
    Use outside the times a 週六半尖峰 or 離峰 contract alone covers pays 4.8倍
    (第三章 七(六), 第四章 八(六), 第五章 八(六))."""
    base_label = oc_rule.base_fee_label
    amount = 0.0
    counted = 0.0
    for segment, (kw, base) in over.items():
        label = (
            getattr(rules.formula, _SEGMENT_FEE_LABELS[segment])
            if rules.formula
            else None
        ) or base_label
        rate = _label_rate(rules, label, season)
        if rate is None:
            rate = _label_rate(rules, base_label, season)
        if rate is None:
            continue
        if segment in outside:
            amount += rate * kw * _ratio(oc_rule.outside_contract_basic_ratio)
            continue
        # 在契約容量10%以下部分: the contract this time's excess is over.
        low = min(kw, max(0.0, base * oc_rule.threshold_ratio - counted))
        counted += kw
        amount += rate * (low * oc_rule.rate_low + (kw - low) * oc_rule.rate_high)
    return amount


def _label_rate(rules: PlanRules, label: str, season: str) -> float | None:
    """The price of the basic fee with this label, or None if the plan has none."""
    fee = rules.fee(label)
    if fee is None:
        return None
    return fee.rate(season) or 0.0


def _ratio(value: float | None) -> float:
    """A ratio plans.json must give where it is read."""
    if value is None:
        raise TariffError("plans.json lacks a ratio this bill needs")
    return float(value)


def _warn_installed_demand_over_capacity(
    inputs: BillingInputs, demand: pd.DataFrame | None
) -> None:
    """第四章 七(一)2: a metered 裝置契約 user stays on 裝置契約電價 and pays no
    超約, until 最高需量 passes the 裝置契約容量. From that month the bill moves
    to 需量契約電價, at a 契約容量 the 電價表 does not give."""
    if demand is None:
        return
    installed = inputs.basic_fee_inputs["裝置契約"]
    peaks = demand.groupby("bill")["kw"].max()
    over = peaks[peaks > installed]
    if not over.empty:
        _warnings.warn(
            f"最高需量 {over.iloc[0]:g} kW in {over.index[0]} passes the 裝置契約 "
            f"{installed:g} kW. From that month Taipower bills 需量契約電價; pass "
            "contract_capacities with the new 契約容量 to bill it.",
            UserWarning,
        )
