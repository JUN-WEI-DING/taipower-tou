"""Taipower bills from usage, by the 電價表 rules in plans.json."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from taipower_tou import _warnings
from taipower_tou.billing_inputs import (
    BillingInputs,
    _check_usage_resolution,
    _parse_inputs,
)
from taipower_tou.calendar import TaiwanCalendar, taiwan_calendar, taiwan_wall_time
from taipower_tou.custom import CustomCalendar
from taipower_tou.demand import (
    _compute_over_contract_kw,
    _over_contract_fee,
    _ratio,
    _read_demand,
    _times,
    _times_outside_contract,
    _warn_installed_demand_over_capacity,
)
from taipower_tou.errors import (
    PartialPeriodWarning,
)
from taipower_tou.factory import (
    BasicFeeFormula,
    PlanRules,
    PlanStore,
    PowerFactorEligibility,
    _build_tariff_plan_from_data,
)
from taipower_tou.models import BillingCycleType
from taipower_tou.tariff import (
    _validate_usage_series,
    check_price_dates,
    season_day_shares,
    tiered_energy_cost,
)


def calculate_bill(
    usage: pd.Series,
    plan_id: str,
    inputs: BillingInputs | None = None,
    calendar_instance: TaiwanCalendar | CustomCalendar | None = None,
    *,
    strict: bool = False,
) -> pd.DataFrame:
    """Each bill's energy_cost, basic_cost, surcharge (加計), adjustment and
    total in TWD, indexed by the bill's first month.

    usage is kWh per interval, labelled by the interval's start, in Taiwan
    time if timezone-aware. Time-of-use plans need hourly or finer readings.
    A bill is billing_cycle_months calendar months counted from the first
    month of usage, so usage that starts or ends mid-month warns
    PartialPeriodWarning. Amounts round as Taipower's bills do unless
    inputs.taipower_rounding is False. strict raises instead of warning for
    an input the plan does not bill, or a contract or meter it needs.
    calculate_bill_breakdown itemizes adjustment.
    """
    summary = _bill(usage, plan_id, inputs, calendar_instance, strict)["summary"]
    return summary.drop(columns="min_fee_adjustment")


def calculate_bill_breakdown(
    usage: pd.Series,
    plan_id: str,
    inputs: BillingInputs | None = None,
    calendar_instance: TaiwanCalendar | CustomCalendar | None = None,
    *,
    strict: bool = False,
) -> dict[str, pd.DataFrame]:
    """calculate_bill's bills with their details, as a dict of frames.

    - "summary": calculate_bill's columns and min_fee_adjustment, the part of
      total that brings a bill up to its minimum fee.
    - "details": kWh and unrounded energy cost per bill, season and
      period_type.
    - "basic_details": each basic fee per bill, label and season, with the
      season's share of the bill's days.
    - "adjustment_details": each over_contract, outside_contract_energy,
      power_factor or bill_ratio amount per bill.
    """
    return _bill(
        usage,
        plan_id,
        inputs,
        calendar_instance,
        strict,
        detailed=True,
    )


def _bill(
    usage: pd.Series,
    plan_id: str,
    inputs: BillingInputs | None,
    calendar_instance: TaiwanCalendar | CustomCalendar | None,
    strict: bool,
    detailed: bool = False,
) -> dict[str, pd.DataFrame]:
    """Each bill's items and total, with the breakdown's details if detailed."""
    _validate_usage_series(usage)
    # float32 kWh would carry its rounding into every price.
    usage = usage.astype("float64")

    store = PlanStore()
    plan_data = store.resolve_plan(plan_id)
    rules = store.rules(plan_data)
    inputs, cycle_months = _parse_inputs(rules, inputs or BillingInputs(), strict)
    _check_usage_resolution(rules, usage)

    calendar = calendar_instance or taiwan_calendar()

    local = taiwan_wall_time(usage.index)
    first_month = local.min().to_period("M")
    billing_periods = _bill_months(local, first_month, cycle_months)
    _check_whole_months(local, billing_periods, cycle_months)

    billing_cycle_type = (
        BillingCycleType.ODD_MONTH if cycle_months > 1 else BillingCycleType.MONTHLY
    )

    tariff_plan = _build_tariff_plan_from_data(
        plan_data,
        store,
        calendar,
        billing_cycle_type=billing_cycle_type,
    )
    check_price_dates(usage.index, tariff_plan.rates.price_dates)
    lookup = tariff_plan.profile.engine.lookup(usage.index)
    context = lookup.labels()
    unit_cost = lookup.unit_costs(tariff_plan.rates)
    times = _times(context)
    metered = _read_registers(usage, billing_periods, times, inputs)
    usage_for_billing = _apply_minimum_usage(
        rules, metered, inputs, billing_periods, cycle_months
    )
    demand = _read_demand(
        inputs,
        tariff_plan.profile,
        lambda index: _bill_months(index, first_month, cycle_months),
        local,
        context,
        times,
        billing_periods,
    )

    energy_costs = _to_jiao(
        inputs,
        _calculate_energy_costs(
            usage_for_billing,
            unit_cost,
            billing_periods,
            tariff_plan,
            cycle_months,
        ),
    )
    month_index = energy_costs.index
    parts = _season_parts(
        month_index, cycle_months, tariff_plan.profile.season_strategy
    )

    monthly_usage = usage_for_billing.groupby(billing_periods).sum()
    monthly_usage.index = monthly_usage.index.to_timestamp()

    basic_costs, basic_details = _calculate_basic_fees(
        rules,
        inputs,
        month_index,
        parts,
        _idle_months(metered, inputs, billing_periods, times, demand),
        cycle_months,
    )
    basic_costs = _to_jiao(inputs, basic_costs)
    surcharge = _to_jiao(
        inputs, _calculate_surcharges(rules, cycle_months, monthly_usage)
    )
    adjustment, adjustment_details = _calculate_adjustments(
        rules,
        inputs,
        basic_costs,
        basic_details,
        month_index,
        parts,
        context,
        unit_cost,
        billing_periods,
        energy_costs,
        surcharge,
        usage_for_billing,
        demand,
        _metered_bills(metered, billing_periods),
    )

    total = _to_yuan(inputs, energy_costs + basic_costs + surcharge + adjustment)
    min_fee = _minimum_fee(rules, cycle_months)
    if min_fee is not None:
        min_adjustment = (min_fee - total).clip(lower=0.0)
        total = total.clip(lower=min_fee)
    else:
        min_adjustment = pd.Series(0.0, index=total.index)

    summary = pd.DataFrame(
        {
            "energy_cost": energy_costs,
            "basic_cost": basic_costs,
            "surcharge": surcharge,
            "adjustment": adjustment,
            "min_fee_adjustment": min_adjustment,
            "total": total,
        }
    )
    if not detailed:
        return {"summary": summary}

    details = _calculate_period_costs(
        usage_for_billing,
        context,
        unit_cost,
        billing_periods,
        tariff_plan,
        cycle_months,
    )

    return {
        "summary": summary,
        "details": details,
        "basic_details": basic_details,
        "adjustment_details": adjustment_details,
    }


def _season_parts(
    month_index: pd.Index, cycle_months: int, season_strategy: Any
) -> dict[pd.Timestamp, dict[str, float]]:
    """Each bill's share of its days in each season. 高壓 夏月 starts on 5/16
    and ends on 10/15, so May and October bills hold both seasons."""
    return {
        ts: season_day_shares(ts.to_period("M"), cycle_months, season_strategy)
        for ts in month_index
    }


def _idle_months(
    usage: pd.Series,
    inputs: BillingInputs,
    billing_periods: pd.PeriodIndex,
    times: np.ndarray,
    demand: pd.DataFrame | None,
) -> pd.Series:
    """Bills whose 抄見度數與最高需量均為0 (第四章 五(五)). A given 超約 is a
    最高需量 over the contract. A bill 按裝置契約容量計費 reads its kWh alone,
    and a 時間電價 one only its 尖峰時間 kWh, whatever its demand."""
    if _installed_only(inputs):
        return ~_metered_bills(usage.where(times == "peak", 0.0), billing_periods)
    used = _metered_bills(usage, billing_periods)
    if inputs.over_contract_kw:
        used[:] = True
    if demand is not None:
        peaks = demand.groupby("bill")["kw"].max() > 0
        peaks.index = peaks.index.to_timestamp()
        used |= peaks.reindex(used.index, fill_value=False)
    return ~used


def _read_registers(
    usage: pd.Series,
    billing_periods: pd.PeriodIndex,
    times: np.ndarray,
    inputs: BillingInputs,
) -> pd.Series:
    """Each interval's kWh as Taipower reads the meter. 施行細則 第二十八條
    rounds a bill's 有效電度 half up to the kWh. A 時間電價 meter reads each
    time (尖峰, 半尖峰, 週六半尖峰, 離峰) on its own register, so each is rounded
    alone, and its whole kWh are spread over its intervals in proportion to
    their kWh."""
    if not inputs.taipower_rounding:
        return usage
    register = usage.groupby([billing_periods, times]).transform("sum").to_numpy()
    whole = np.floor(np.round(register, 6) + 0.5)
    scale = np.divide(whole, register, out=np.zeros_like(register), where=register > 0)
    return usage * scale


def _metered_bills(usage: pd.Series, billing_periods: pd.PeriodIndex) -> pd.Series:
    """Bills with kWh on the meter, before any 底度."""
    used = usage.groupby(billing_periods).sum() > 0
    used.index = used.index.to_timestamp()
    return used


def _installed_only(inputs: BillingInputs) -> bool:
    """A bill 按裝置契約容量計費, with no 需量契約."""
    return "裝置契約" in inputs.basic_fee_inputs and not inputs.contract_capacities


def _calculate_basic_fees(
    rules: PlanRules,
    inputs: BillingInputs,
    month_index: pd.Index,
    parts: dict[pd.Timestamp, dict[str, float]],
    idle_months: pd.Series,
    months: int,
) -> tuple[pd.Series, pd.DataFrame]:
    """Each bill's 基本電費. A month of each season's fees is weighted by the
    season's share of the bill's days, as for a mid-month price change
    (營業規章 第二十七條一), and multiplied by the bill's months."""
    idle_ratio = rules.idle_basic_fee_ratio
    details = []
    for ts in month_index:
        scale = float(months)
        if idle_ratio is not None and idle_months[ts]:
            scale *= float(idle_ratio)
        for season, share in parts[ts].items():
            for label, quantity, rate in _basic_fee_rows(rules, inputs, season):
                details.append(
                    {
                        "period": ts,
                        "label": label,
                        "season": season,
                        "share": share,
                        "quantity": quantity,
                        "rate": rate,
                        "cost": rate * quantity * share * scale,
                    }
                )
    columns = ["period", "label", "season", "share", "quantity", "rate", "cost"]
    frame = pd.DataFrame(details, columns=columns)
    monthly = frame.groupby("period")["cost"].sum().astype(float)
    return monthly.reindex(month_index, fill_value=0.0), frame


def _basic_fee_rows(
    rules: PlanRules, inputs: BillingInputs, season: str
) -> list[tuple[str, float, float]]:
    """A month of 基本電費 in a season, as (label, quantity, rate) rows."""
    if rules.formula and inputs.contract_capacities:
        return _formula_rows(rules, inputs, rules.formula, season)
    rows = []
    if rules.basic_fee is not None:
        count = inputs.basic_fee_inputs.get("basic_fee", 1.0)
        rows.append(("basic_fee", count, rules.basic_fee))
    household = rules.household_fee("installed", _phase(inputs))
    for fee in rules.basic_fees:
        if fee.per_household:
            if fee is not household:
                continue
            quantity = inputs.basic_fee_inputs.get(fee.label, 1.0)
        else:
            quantity = inputs.basic_fee_inputs.get(fee.label, 0.0)
        rate = fee.rate(season)
        if quantity != 0 and rate is not None:
            rows.append((fee.label, quantity, rate))
    return rows


def _phase(inputs: BillingInputs) -> str:
    """The meter phase a 按戶計收 fee is picked by."""
    return "three" if inputs.meter_phase == "three" else "single"


def _formula_rows(
    rules: PlanRules,
    inputs: BillingInputs,
    formula: BasicFeeFormula,
    season: str,
) -> list[tuple[str, float, float]]:
    """A month of a 需量契約's 基本電費: 按戶計收, 經常契約, 非夏月 (非夏月 only)
    or 半尖峰契約, and the 週六半尖峰 and 離峰 contracts beyond half of the
    others (電價表 lines 374-403, 651-709 and 1025-1060)."""

    def row(label: str | None, quantity: float) -> tuple[str, float, float]:
        fee = rules.fee(label) if label else None
        return label or "", quantity, (fee.rate(season) if fee else None) or 0.0

    rows = []
    household = rules.household_fee("demand", _phase(inputs))
    if household and household.cost is not None:
        count = inputs.basic_fee_inputs.get(household.label, 1.0)
        rows.append((household.label, count, float(household.cost)))
    capacities = inputs.contract_capacities
    regular = capacities.get("regular", 0.0)
    rows.append(row(formula.regular_label, regular))
    if formula.type == "regular_only":
        return rows
    if formula.type == "three_stage":
        second = capacities.get("semi_peak", 0.0)
        rows.append(row(formula.semi_peak_label, second))
    else:
        second = capacities.get("non_summer", 0.0)
        if season != "summer":
            rows.append(row(formula.non_summer_label, second))
    weekend = capacities.get("saturday_semi_peak", 0.0) + capacities.get(
        "off_peak", 0.0
    )
    rows.append(
        row(
            formula.saturday_label,
            max(0.0, weekend - (regular + second) * float(formula.weekend_ratio)),
        )
    )
    return rows


def _to_jiao(inputs: BillingInputs, amount: Any) -> Any:
    """營業規章施行細則 第二十九條: 應計電費各項均計至角位，分位以下捨棄."""
    if not inputs.taipower_rounding:
        return amount
    return np.trunc(np.round(amount * 10, 6)) / 10


def _to_yuan(inputs: BillingInputs, amount: Any) -> Any:
    """營業規章施行細則 第二十九條: 電費總金額...均以元為單位，角位四捨五入進整."""
    if not inputs.taipower_rounding:
        return amount
    return np.sign(amount) * np.floor(np.abs(np.round(amount, 6)) + 0.5)


def _calculate_surcharges(
    rules: PlanRules,
    months: int,
    monthly_usage: pd.Series,
) -> pd.Series:
    surcharge = pd.Series(0.0, index=monthly_usage.index)
    rule = rules.surcharge
    if rule:
        # 每月總度數超過2000度之部分. A two-month bill's threshold is 4000 kWh,
        # as 第三章 五(一)2 doubles 分段度數 for 隔月抄表.
        over = (monthly_usage - rule.threshold_kwh * months).clip(lower=0.0)
        surcharge += over * rule.cost_per_kwh
    return surcharge


def _power_factor_applies(
    eligible: PowerFactorEligibility, inputs: BillingInputs
) -> bool:
    """Whether the bill is one the 電價表 adjusts for power factor.

    An unknown meter_phase counts as eligible, since the caller gave a power
    factor. 用電設備容量 (20 kVA for 非時間 and 簡易型) is not an input.
    """
    if eligible.phase and inputs.meter_phase not in (None, eligible.phase):
        return False
    demand_kw = sum(inputs.contract_capacities.values())
    installed_kw = inputs.basic_fee_inputs.get("裝置契約", 0.0)
    if eligible.min_contract_kw is not None:
        return demand_kw >= eligible.min_contract_kw
    if eligible.min_installed_kw is not None or eligible.min_demand_kw is not None:
        return installed_kw >= _or_inf(eligible.min_installed_kw) or (
            demand_kw >= _or_inf(eligible.min_demand_kw)
        )
    return True


def _or_inf(bound: float | None) -> float:
    return math.inf if bound is None else bound


def _household_costs(
    rules: PlanRules, basic_details: pd.DataFrame, month_index: pd.Index
) -> pd.Series:
    """The 按戶計收 part of each bill's basic fee."""
    labels = {"basic_fee"} | {f.label for f in rules.basic_fees if f.per_household}
    if basic_details.empty:
        return pd.Series(0.0, index=month_index)
    household = basic_details[basic_details["label"].isin(labels)]
    return (
        household.groupby("period")["cost"].sum().reindex(month_index, fill_value=0.0)
    )


def _calculate_adjustments(
    rules: PlanRules,
    inputs: BillingInputs,
    basic_costs: pd.Series,
    basic_details: pd.DataFrame,
    month_index: pd.Index,
    parts: dict[pd.Timestamp, dict[str, float]],
    context_df: pd.DataFrame,
    unit_cost: np.ndarray,
    billing_periods: pd.PeriodIndex,
    energy_costs: pd.Series,
    surcharge: pd.Series,
    usage: pd.Series,
    demand: pd.DataFrame | None,
    used: pd.Series,
) -> tuple[pd.Series, pd.DataFrame]:
    details: list[dict[str, Any]] = []
    over_costs = pd.Series(0.0, index=month_index)
    outside_energy = pd.Series(0.0, index=month_index)

    oc_rule = rules.over_contract
    if oc_rule and _installed_only(inputs):
        _warn_installed_demand_over_capacity(inputs, demand)
    elif oc_rule:
        outside = (
            _times_outside_contract(inputs.contract_capacities)
            if oc_rule.outside_contract_basic_ratio
            else set()
        )
        over_by_bill = _compute_over_contract_kw(
            inputs, demand, parts, oc_rule, outside
        )
        for idx, by_season in (over_by_bill or {}).items():
            # 營業規章 第二十七條二: 超約 before and after a change in price is
            # billed on each part's own excess, by its share of the days.
            amount = sum(
                parts[idx][season]
                * _over_contract_fee(rules, oc_rule, over, season, outside)
                for season, over in by_season.items()
            )
            over_costs.loc[idx] = _to_jiao(inputs, amount)
            details.append(
                {"period": idx, "type": "over_contract", "amount": float(amount)}
            )
        if outside:
            # 1.6倍計收流動電費 for the kWh outside the contract's times
            # (第三章 七(六), 第四章 八(六), 第五章 八(六)).
            in_outside = np.isin(_times(context_df), list(outside))
            extra = pd.Series(
                usage.to_numpy() * unit_cost * in_outside,
                index=usage.index,
            ).groupby(billing_periods).sum() * (
                _ratio(oc_rule.outside_contract_energy_ratio) - 1
            )
            extra.index = extra.index.to_timestamp()
            outside_energy = _to_jiao(
                inputs, extra.reindex(month_index, fill_value=0.0)
            )
            details.extend(
                {"period": idx, "type": "outside_contract_energy", "amount": float(v)}
                for idx, v in outside_energy.items()
            )

    pf_rule = rules.power_factor
    pf_cost = pd.Series(0.0, index=month_index)
    if (
        pf_rule
        and inputs.power_factor is not None
        and _power_factor_applies(pf_rule.eligible, inputs)
    ):
        base = pf_rule.base_percent
        step = pf_rule.step_percent
        pf = min(float(inputs.power_factor), pf_rule.max_discount_percent)
        # 功率因數 adjusts 該月份電費, but 按戶計收之基本電費，不列計功率因數調整費.
        target = (
            basic_costs
            - _household_costs(rules, basic_details, month_index)
            + energy_costs
            + outside_energy
            + surcharge
        )
        # 營業規章施行細則 第三十條: the 非約定基本電費 is adjusted too, except for 80%
        # and above, where 超約 gets no 功率因數扣減.
        if pf < base:
            target = target + over_costs
        pf_cost = _to_jiao(inputs, target * ((base - pf) * step / 100.0))
        # 營業規章施行細則 第三十八條: 全月均無用電之用戶，當月功率因數按80％計算.
        # 底度 is a minimum charge, not use.
        pf_cost = pf_cost.where(used.reindex(month_index, fill_value=False), 0.0)
        if pf != base:
            details.extend(
                {"period": idx, "type": "power_factor", "amount": float(value)}
                for idx, value in pf_cost.items()
            )

    adjustment = over_costs + outside_energy + pf_cost
    ratio = rules.bill_ratio
    if ratio is not None:
        # 各類電價表及計算範例 page 16 rounds the whole bill to the 元 before
        # taking its share, 89,729元×95%=85,243元. The items are within half
        # a 元 of bill, so the caller's rounded total is bill + discount.
        bill = _to_yuan(inputs, basic_costs + energy_costs + surcharge + adjustment)
        discount = _to_yuan(inputs, bill * ratio) - bill
        details.extend(
            {"period": idx, "type": "bill_ratio", "amount": float(value)}
            for idx, value in discount.items()
        )
        adjustment = adjustment + discount
    return adjustment, pd.DataFrame(details)


def _minimum_fee(rules: PlanRules, cycle_months: int) -> float | None:
    """The least a bill covering cycle_months months is charged."""
    if rules.min_monthly_fee is None:
        return None
    return float(rules.min_monthly_fee) * cycle_months


def _apply_minimum_usage(
    rules: PlanRules,
    usage: pd.Series,
    inputs: BillingInputs,
    billing_periods: pd.PeriodIndex,
    cycle_months: int,
) -> pd.Series:
    if not rules.has_minimum_usage:
        return usage
    if (
        inputs.meter_phase is None
        or inputs.meter_voltage_v is None
        or inputs.meter_ampere is None
    ):
        return usage

    ruleset = rules.minimum_usage
    if not ruleset:
        return usage

    # A 低壓電表 is one under 1000 V. 表燈 is supplied at 110, 220 or 380 V
    # (電價表 第三章 二, 營業規章 第三條).
    voltage = inputs.meter_voltage_v
    target = next(
        (
            item
            for item in ruleset
            if item.phase == inputs.meter_phase
            and (voltage == item.voltage_v or voltage < item.voltage_v_below)
        ),
        None,
    )
    if not target:
        _warnings.warn(
            f"No 底度 rule (第三章 五(一)1) for a {inputs.meter_phase}-phase "
            f"{voltage} V meter, so the bill has no minimum usage.",
            UserWarning,
        )
        return usage

    # A low-voltage meter over its ampere_threshold counts as the threshold.
    ampere = min(float(inputs.meter_ampere), target.ampere_threshold)
    min_kwh = ampere * target.kwh_per_ampere

    if min_kwh <= 0:
        return usage

    adjusted = usage.copy()
    for period, group in usage.groupby(billing_periods):
        total = group.sum()
        required = min_kwh * cycle_months
        if total >= required:
            continue
        if total > 0:
            factor = float(required / total)
            adjusted.loc[group.index] = group * factor
        else:
            adjusted.loc[group.index[0]] = required
    return adjusted


def _bill_months(
    local: pd.DatetimeIndex, first: pd.Period, cycle_months: int
) -> pd.PeriodIndex:
    """Each Taiwan wall time's bill, named by its first month. Bills are runs
    of cycle_months calendar months counted from first."""
    months = local.to_period("M")
    if cycle_months <= 1:
        return months
    starts = {
        month: first + (month - first).n // cycle_months * cycle_months
        for month in months.unique()
    }
    return pd.PeriodIndex(months.map(starts), freq="M")


def _check_whole_months(
    index: pd.DatetimeIndex, billing_periods: pd.PeriodIndex, cycle_months: int
) -> None:
    """Warn when the first or last bill covers only part of its months."""
    local = taiwan_wall_time(index)
    first_day = local.min().normalize()
    last_day = local.max().normalize()
    bills_start = billing_periods.min().start_time
    bills_end = (billing_periods.max() + (cycle_months - 1)).end_time.normalize()
    if first_day > bills_start or last_day < bills_end:
        _warnings.warn(
            f"Bills cover {cycle_months} calendar month(s) each, counted from the "
            f"first month of usage. Usage from {first_day.date()} to "
            f"{last_day.date()} leaves part of the first or last bill's months "
            "empty, so that bill is not one Taipower bill. Taipower bills from "
            "one meter reading to the next.",
            PartialPeriodWarning,
        )


def _calculate_energy_costs(
    usage: pd.Series,
    unit_cost: np.ndarray,
    billing_periods: pd.PeriodIndex,
    tariff_plan: Any,
    cycle_months: int,
) -> pd.Series:
    rates = tariff_plan.rates
    if rates.tiered_rates:
        totals = {
            period.to_timestamp(): tiered_energy_cost(
                group.sum(),
                rates.tiered_rates,
                season_day_shares(
                    period, cycle_months, tariff_plan.profile.season_strategy
                ),
                cycle_months,
            )
            for period, group in usage.groupby(billing_periods)
        }
        return pd.Series(totals).sort_index()

    interval_costs = usage * unit_cost
    totals = interval_costs.groupby(billing_periods).sum()
    if hasattr(totals, "index") and hasattr(totals.index, "to_timestamp"):
        totals.index = totals.index.to_timestamp()
    return totals


def _calculate_period_costs(
    usage: pd.Series,
    context_df: pd.DataFrame,
    unit_cost: np.ndarray,
    billing_periods: pd.PeriodIndex,
    tariff_plan: Any,
    cycle_months: int,
) -> pd.DataFrame:
    """Usage and energy cost per billing period, season and period type."""
    rates = tariff_plan.rates
    columns = ["period", "season", "period_type", "usage_kwh", "energy_cost"]
    if rates.tiered_rates:
        records: list[dict[str, Any]] = []
        for period, group in usage.groupby(billing_periods):
            shares = season_day_shares(
                period, cycle_months, tariff_plan.profile.season_strategy
            )
            records.extend(
                {
                    "period": period.to_timestamp(),
                    "season": season,
                    "period_type": "tiered",
                    "usage_kwh": group.sum() * share,
                    "energy_cost": tiered_energy_cost(
                        group.sum(), rates.tiered_rates, {season: share}, cycle_months
                    ),
                }
                for season, share in shares.items()
            )
        return pd.DataFrame(records, columns=columns)

    rows = pd.DataFrame(
        {
            "period": billing_periods.to_timestamp(),
            "season": context_df["season"].to_numpy(),
            "period_type": context_df["period"].to_numpy(),
            "usage_kwh": usage.to_numpy(),
            "energy_cost": usage.to_numpy() * unit_cost,
        }
    )
    return rows.groupby(columns[:3], sort=False, as_index=False)[columns[3:]].sum()
