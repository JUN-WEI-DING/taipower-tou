"""Taipower bills from usage, by the 電價表 rules in plans.json."""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from taipower_tou import _warnings
from taipower_tou.calendar import TaiwanCalendar, taiwan_calendar, taiwan_wall_time
from taipower_tou.errors import (
    InvalidBasicFeeInput,
    InvalidBillingInput,
    InvalidUsageInput,
    MissingRequiredInput,
    PartialPeriodWarning,
)
from taipower_tou.factory import (
    PlanRequirements,
    PlanStore,
    _build_tariff_plan_from_data,
)
from taipower_tou.models import BillingCycleType, _label_value
from taipower_tou.tariff import (
    TariffRate,
    _validate_usage_series,
    check_price_dates,
    season_day_shares,
    tiered_energy_cost,
    unit_costs,
)


@dataclass
class BillingInputs:
    """What a bill needs besides usage.

    Attributes:
        basic_fee_inputs: Quantity per basic fee label that
            get_plan_requirements lists, such as {"裝置契約": 10} in kW or
            {"按戶計收-單相": 2} households. 簡易型 plans take
            {"basic_fee": households}.
        power_factor: 功率因數 in percent, 95 and not 0.95.
        contract_capacity_kw: The 經常契約 kW, contract_capacities["regular"].
        over_contract_kw: 超約 kW at 尖峰 for every bill, in place of demand_kw.
        contract_capacities: kW of each contract, keyed "regular",
            "non_summer" or "semi_peak", "saturday_semi_peak" and "off_peak".
        demand_kw: 需量 readings in kW. Readings finer than 15 minutes are
            averaged over each quarter hour, and 最高需量 counts whole kW.
        meter_phase, meter_voltage_v, meter_ampere: The meter, for the 底度.
            meter_phase, "single" or "three", also picks the 按戶計收 fee
            and whether 功率因數 applies.
        billing_cycle_months: 1 or 2 months per bill. None takes the plan's,
            2 for 表燈非時間 and 1 otherwise.
        demand_adjustment_factor: Multiplies each 需量 after the quarter-hour
            average.
        taipower_rounding: False keeps kWh and amounts unrounded.
    """

    basic_fee_inputs: dict[str, float] = field(default_factory=dict)
    power_factor: float | None = None
    contract_capacity_kw: float | None = None
    over_contract_kw: float | None = None
    contract_capacities: dict[str, float] = field(default_factory=dict)
    demand_kw: pd.Series | None = None
    meter_phase: str | None = None
    meter_voltage_v: int | None = None
    meter_ampere: float | None = None
    billing_cycle_months: int | None = None
    demand_adjustment_factor: float = 1.0
    # 營業規章施行細則 第二十八、二十九條 rounding of kWh and amounts. False is for
    # callers that compare or optimize bills. 最高需量 is whole kW either way.
    taipower_rounding: bool = True

    @classmethod
    def for_high_voltage(
        cls,
        regular: float,
        non_summer: float,
        saturday_semi_peak: float,
        off_peak: float,
        power_factor: float | None = None,
        demand_kw: pd.Series | None = None,
        demand_adjustment_factor: float = 1.0,
    ) -> BillingInputs:
        """Inputs for a 高壓 二段式 or 批次生產 bill.

        Args:
            regular: 經常契約 kW.
            non_summer: 非夏月契約 kW.
            saturday_semi_peak: 週六半尖峰契約 kW.
            off_peak: 離峰契約 kW.
            power_factor: 功率因數 in percent.
            demand_kw: 需量 readings in kW, for 超約.
            demand_adjustment_factor: Multiplies each 需量.
        """
        return cls(
            contract_capacities={
                "regular": regular,
                "non_summer": non_summer,
                "saturday_semi_peak": saturday_semi_peak,
                "off_peak": off_peak,
            },
            power_factor=power_factor,
            demand_kw=demand_kw,
            demand_adjustment_factor=demand_adjustment_factor,
        )

    @classmethod
    def for_high_voltage_three_stage(
        cls,
        regular: float,
        semi_peak: float,
        saturday_semi_peak: float,
        off_peak: float,
        power_factor: float | None = None,
        demand_kw: pd.Series | None = None,
        demand_adjustment_factor: float = 1.0,
    ) -> BillingInputs:
        """Inputs for a 高壓 三段式 bill.

        Args:
            regular: 經常契約 kW.
            semi_peak: 半尖峰契約 kW.
            saturday_semi_peak: 週六半尖峰契約 kW.
            off_peak: 離峰契約 kW.
            power_factor: 功率因數 in percent.
            demand_kw: 需量 readings in kW, for 超約.
            demand_adjustment_factor: Multiplies each 需量.
        """
        return cls(
            contract_capacities={
                "regular": regular,
                "semi_peak": semi_peak,
                "saturday_semi_peak": saturday_semi_peak,
                "off_peak": off_peak,
            },
            power_factor=power_factor,
            demand_kw=demand_kw,
            demand_adjustment_factor=demand_adjustment_factor,
        )

    @classmethod
    def for_extra_high_voltage(
        cls,
        regular: float,
        non_summer: float,
        saturday_semi_peak: float,
        off_peak: float,
        power_factor: float | None = None,
        demand_kw: pd.Series | None = None,
        demand_adjustment_factor: float = 1.0,
    ) -> BillingInputs:
        """Inputs for a 特高壓 二段式 or 批次生產 bill, as for_high_voltage."""
        return cls(
            contract_capacities={
                "regular": regular,
                "non_summer": non_summer,
                "saturday_semi_peak": saturday_semi_peak,
                "off_peak": off_peak,
            },
            power_factor=power_factor,
            demand_kw=demand_kw,
            demand_adjustment_factor=demand_adjustment_factor,
        )

    @classmethod
    def for_extra_high_voltage_three_stage(
        cls,
        regular: float,
        semi_peak: float,
        saturday_semi_peak: float,
        off_peak: float,
        power_factor: float | None = None,
        demand_kw: pd.Series | None = None,
        demand_adjustment_factor: float = 1.0,
    ) -> BillingInputs:
        """Inputs for a 特高壓 三段式 bill, as for_high_voltage_three_stage."""
        return cls(
            contract_capacities={
                "regular": regular,
                "semi_peak": semi_peak,
                "saturday_semi_peak": saturday_semi_peak,
                "off_peak": off_peak,
            },
            power_factor=power_factor,
            demand_kw=demand_kw,
            demand_adjustment_factor=demand_adjustment_factor,
        )

    @classmethod
    def for_residential(
        cls,
        phase: str,
        voltage: int,
        ampere: float,
        basic_fee_multiplier: float = 1.0,
    ) -> BillingInputs:
        """Inputs for a 表燈 bill on one meter.

        Args:
            phase: "single" or "three".
            voltage: Meter volts. Any voltage under 1000 V is a 低壓 meter.
                The 高壓 meters with a 底度 are 3300 and 6600 V single-phase
                and 3300, 5700 and 11400 V three-phase. On a plan with a 底度,
                other voltages warn.
            ampere: Meter amperes, for the 底度.
            basic_fee_multiplier: Households a 簡易型 plan bills its
                basic_fee for. Other plans warn when it is not 1.
        """
        # Only 簡易型 plans bill "basic_fee", so a single household leaves it
        # out and the inputs fit every residential plan, strict mode too.
        return cls(
            meter_phase=phase,
            meter_voltage_v=voltage,
            meter_ampere=ampere,
            basic_fee_inputs=(
                {}
                if basic_fee_multiplier == 1.0
                else {"basic_fee": basic_fee_multiplier}
            ),
        )

    @classmethod
    def for_lighting_standard(
        cls,
        phase: str,
        contract_kw: float,
        household_count: float = 1.0,
    ) -> BillingInputs:
        """Inputs for a 標準型 bill.

        Args:
            phase: "single" or "three", which picks the 按戶計收 fee.
            contract_kw: 經常契約 kW.
            household_count: Households billed 按戶計收.
        """
        label = "按戶計收-三相" if phase.lower() == "three" else "按戶計收-單相"
        return cls(
            meter_phase=phase,
            contract_capacities={"regular": contract_kw},
            basic_fee_inputs={label: household_count},
        )


def _contract_keys(formula_type: str | None) -> set[str]:
    """The contract_capacities keys a basic fee formula bills."""
    if formula_type == "two_stage":
        return {"regular", "non_summer", "saturday_semi_peak", "off_peak"}
    if formula_type == "three_stage":
        return {"regular", "semi_peak", "saturday_semi_peak", "off_peak"}
    if formula_type == "regular_only":
        return {"regular"}
    return set()


def _number(value: Any) -> float:
    """A real number as a float, and anything else as NaN, which every range
    check refuses."""
    return float(value) if isinstance(value, numbers.Real) else math.nan


def _check_amount(
    name: str, value: Any, error: type[InvalidBillingInput] = InvalidBillingInput
) -> None:
    """A kW, household count or ampere is a finite number, 0 or more."""
    if not 0 <= _number(value) < math.inf:
        raise error(f"{name} must be a finite number of 0 or more, got {value!r}.")


def _check_values(inputs: BillingInputs) -> None:
    """Refuse a value no bill can have, whatever the plan."""
    for key, value in inputs.contract_capacities.items():
        _check_amount(f"contract_capacities[{key!r}]", value)
    for key, value in inputs.basic_fee_inputs.items():
        _check_amount(f"basic_fee_inputs[{key!r}]", value, InvalidBasicFeeInput)
    for name in ("contract_capacity_kw", "over_contract_kw", "meter_ampere"):
        if getattr(inputs, name) is not None:
            _check_amount(name, getattr(inputs, name))
    factor = inputs.demand_adjustment_factor
    if not 0 < _number(factor) < math.inf:
        raise InvalidBillingInput(
            f"demand_adjustment_factor must be a finite number above 0, got {factor!r}."
        )
    pf = inputs.power_factor
    if pf is not None:
        if not 0 < _number(pf) <= 100:
            raise InvalidBillingInput(
                f"power_factor must be a percentage above 0 and up to 100, got {pf!r}."
            )
        if pf <= 1:
            raise InvalidBillingInput(
                f"power_factor is a percentage, 95 for 95%, not 0.95. Got {pf!r}."
            )
    if inputs.billing_cycle_months not in (None, 1, 2):
        raise InvalidBillingInput(
            "billing_cycle_months must be 1, 2 or None (the plan's default), "
            f"got {inputs.billing_cycle_months!r}."
        )
    phase = inputs.meter_phase
    if phase is not None and (
        not isinstance(phase, str) or phase.lower() not in ("single", "three")
    ):
        raise InvalidBillingInput(
            f"meter_phase must be 'single', 'three' or None, got {phase!r}."
        )


def _check_demand(demand: Any) -> None:
    if demand is None:
        return
    if not isinstance(demand, pd.Series) or not isinstance(
        demand.index, pd.DatetimeIndex
    ):
        raise InvalidUsageInput("demand_kw must be a pandas.Series with DatetimeIndex")
    if demand.index.has_duplicates:
        raise InvalidUsageInput("demand_kw has more than one reading at a timestamp")


def _parse_inputs(
    plan_data: dict[str, Any], inputs: BillingInputs, strict: bool
) -> tuple[BillingInputs, int]:
    """The caller's inputs as this plan's bill reads them, and the bill's
    months. They are checked here once, and the bill trusts them. The
    caller's BillingInputs is left as given, so it can bill another plan."""
    _check_values(inputs)
    _check_demand(inputs.demand_kw)
    contracts = dict(inputs.contract_capacities)
    if inputs.contract_capacity_kw is not None:
        regular = contracts.setdefault("regular", inputs.contract_capacity_kw)
        if regular != inputs.contract_capacity_kw:
            raise InvalidBillingInput(
                f"contract_capacity_kw {inputs.contract_capacity_kw:g} is the "
                f"經常契約, and contract_capacities gives another, {regular:g}."
            )
    cycle_months = int(
        inputs.billing_cycle_months
        or plan_data.get("billing_rules", {}).get("billing_cycle_months")
        or 1
    )
    parsed = replace(
        inputs,
        contract_capacities=contracts,
        contract_capacity_kw=None,
        meter_phase=inputs.meter_phase and inputs.meter_phase.lower(),
        billing_cycle_months=cycle_months,
    )
    for message in _validate_billing_inputs(plan_data, parsed, cycle_months, strict):
        _warnings.warn(message, UserWarning)
    return parsed, cycle_months


def _validate_billing_inputs(
    plan_data: dict[str, Any],
    inputs: BillingInputs,
    cycle_months: int,
    strict: bool,
) -> list[str]:
    """Warnings for inputs this plan does not bill as given, which strict
    mode raises instead.

    Raises:
        MissingRequiredInput: If required inputs are missing
        InvalidBasicFeeInput: If basic_fee_inputs has invalid keys (strict mode)
        InvalidBillingInput: If contract_capacities has a key the plan does
            not bill (strict mode)
    """
    requirements = PlanRequirements.from_plan_data(plan_data)
    warnings = []
    contracts = inputs.contract_capacities
    contract_keys = _contract_keys(requirements.formula_type)

    if requirements.requires_contract_capacity and not contracts:
        raise MissingRequiredInput(
            f"Plan '{plan_data.get('id')}' requires contract capacity. "
            f"Provide either contract_capacity_kw or contract_capacities. "
            f"Use BillingInputs.for_high_voltage() or "
            f"BillingInputs.for_extra_high_voltage() for convenient setup."
        )

    valid_basic_fee_labels = set(requirements.valid_basic_fee_labels)
    if plan_data.get("basic_fee") is not None:
        valid_basic_fee_labels.add("basic_fee")

    if inputs.basic_fee_inputs:
        unknown_keys = set(inputs.basic_fee_inputs.keys()) - valid_basic_fee_labels
        if unknown_keys:
            if strict:
                raise InvalidBasicFeeInput(
                    f"Unknown keys in basic_fee_inputs: {unknown_keys}. "
                    f"Valid keys for this plan: {valid_basic_fee_labels}"
                )
            warnings.append(
                f"Unknown keys in basic_fee_inputs (ignored): {unknown_keys}"
            )

    unknown_contracts = set(contracts) - contract_keys
    if unknown_contracts:
        message = (
            f"Plan '{plan_data.get('id')}' bills no {sorted(unknown_contracts)} "
            "contract, so the bill leaves them out. "
            + (
                f"Its contracts are {sorted(contract_keys)}."
                if contract_keys
                else "It bills no 契約容量."
            )
        )
        if strict:
            raise InvalidBillingInput(message)
        warnings.append(message)
    if contract_keys and not contracts and "裝置契約" not in inputs.basic_fee_inputs:
        message = (
            f"Plan '{plan_data.get('id')}' bills its basic fee per kW of "
            "contract_capacities, or of a 裝置契約 in basic_fee_inputs where the "
            "plan has one. With neither, it bills no kW."
        )
        if strict:
            raise MissingRequiredInput(message)
        warnings.append(message)
    if cycle_months > 1 and contract_keys & set(contracts):
        warnings.append(
            f"Taipower bills a 契約容量 every month, since 超約 is on 當月最高需量. "
            f"This bill of plan '{plan_data.get('id')}' covers {cycle_months} "
            "months and does not match Taipower's."
        )

    if requirements.requires_meter_spec:
        if not all([inputs.meter_phase, inputs.meter_voltage_v, inputs.meter_ampere]):
            if strict:
                raise MissingRequiredInput(
                    f"Plan '{plan_data.get('id')}' has minimum usage rules. "
                    f"Providing meter_phase, meter_voltage_v, and meter_ampere "
                    f"is required for accurate billing. "
                    f"Use BillingInputs.for_residential() for convenient setup."
                )
            warnings.append(
                f"Plan '{plan_data.get('id')}' has minimum usage rules. "
                f"Providing meter specifications is recommended."
            )

    return warnings


def _check_usage_resolution(plan_data: dict[str, Any], usage: pd.Series) -> None:
    """Warn for time-of-use usage that steps by more than an hour. A reading
    is priced at the period of its timestamp, so a day's kWh would all be
    priced at 00:00. Irregular readings warn only when every gap between
    them is a multiple of one step over an hour."""
    if plan_data.get("type") != "TOU" or len(usage) < 2:
        return
    steps = np.unique(np.diff(usage.index.as_unit("ns").asi8))
    step = pd.Timedelta(math.gcd(*steps.tolist()))
    if step > pd.Timedelta("1h"):
        _warnings.warn(
            f"Usage timestamps are {step / pd.Timedelta('1h'):g} hours apart, or "
            "a multiple of that. A time-of-use plan prices each reading at the "
            "period its timestamp falls in, so pass hourly or finer usage.",
            UserWarning,
        )


def calculate_bill(
    usage: pd.Series,
    plan_id: str,
    inputs: BillingInputs | None = None,
    calendar_instance: TaiwanCalendar | None = None,
    cache_dir: Path | None = None,
    api_timeout: int | None = None,
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
    summary = _bill(
        usage, plan_id, inputs, calendar_instance, cache_dir, api_timeout, strict
    )["summary"]
    return summary.drop(columns="min_fee_adjustment")


def calculate_bill_simple(
    usage: pd.Series,
    plan_id: str,
    calendar_instance: TaiwanCalendar | None = None,
    cache_dir: Path | None = None,
    api_timeout: int | None = None,
    strict: bool = False,
) -> pd.DataFrame:
    """calculate_bill without BillingInputs."""
    return calculate_bill(
        usage,
        plan_id,
        inputs=None,
        calendar_instance=calendar_instance,
        cache_dir=cache_dir,
        api_timeout=api_timeout,
        strict=strict,
    )


def calculate_bill_breakdown(
    usage: pd.Series,
    plan_id: str,
    inputs: BillingInputs | None = None,
    calendar_instance: TaiwanCalendar | None = None,
    cache_dir: Path | None = None,
    api_timeout: int | None = None,
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
        cache_dir,
        api_timeout,
        strict,
        detailed=True,
    )


def _bill(
    usage: pd.Series,
    plan_id: str,
    inputs: BillingInputs | None,
    calendar_instance: TaiwanCalendar | None,
    cache_dir: Path | None,
    api_timeout: int | None,
    strict: bool,
    detailed: bool = False,
) -> dict[str, pd.DataFrame]:
    """Each bill's items and total, with the breakdown's details if detailed."""
    _validate_usage_series(usage)
    # float32 kWh would carry its rounding into every price.
    usage = usage.astype("float64")

    store = PlanStore()
    plan_data = store.resolve_plan(plan_id)
    inputs, cycle_months = _parse_inputs(plan_data, inputs or BillingInputs(), strict)
    _check_usage_resolution(plan_data, usage)

    calendar = calendar_instance or taiwan_calendar(
        cache_dir=cache_dir, api_timeout=api_timeout
    )

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
    context = tariff_plan.profile.evaluate(usage.index)
    times = _times(context)
    metered = _read_registers(usage, billing_periods, times, inputs)
    usage_for_billing = _apply_minimum_usage(
        plan_data, store, metered, inputs, billing_periods, cycle_months
    )
    demand = _read_demand(
        inputs,
        tariff_plan.profile,
        first_month,
        cycle_months,
        local,
        context,
        times,
        billing_periods,
    )

    energy_costs = _to_jiao(
        inputs,
        _calculate_energy_costs(
            usage_for_billing,
            context,
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
        plan_data,
        inputs,
        month_index,
        parts,
        _idle_months(metered, inputs, billing_periods, times, demand),
        cycle_months,
    )
    basic_costs = _to_jiao(inputs, basic_costs)
    surcharge = _to_jiao(
        inputs, _calculate_surcharges(plan_data, cycle_months, monthly_usage)
    )
    adjustment, adjustment_details = _calculate_adjustments(
        plan_data,
        inputs,
        basic_costs,
        basic_details,
        month_index,
        parts,
        context,
        billing_periods,
        energy_costs,
        surcharge,
        usage_for_billing,
        tariff_plan.rates,
        demand,
        _metered_bills(metered, billing_periods),
    )

    total = _to_yuan(inputs, energy_costs + basic_costs + surcharge + adjustment)
    min_fee = _minimum_fee(plan_data, cycle_months)
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


def _household_fee(
    plan_data: dict[str, Any], inputs: BillingInputs, contract: str
) -> dict[str, Any] | None:
    """The one 按戶計收 fee of a bill, by contract type and meter phase."""
    phase = "three" if inputs.meter_phase == "three" else "single"
    for entry in plan_data.get("basic_fees", []):
        if (
            entry.get("unit") == "per_household_month"
            and entry.get("contract", contract) == contract
            and entry.get("phase", phase) == phase
        ):
            return entry
    return None


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
    plan_data: dict[str, Any],
    inputs: BillingInputs,
    month_index: pd.Index,
    parts: dict[pd.Timestamp, dict[str, float]],
    idle_months: pd.Series,
    months: int,
) -> tuple[pd.Series, pd.DataFrame]:
    """Each bill's 基本電費. A month of each season's fees is weighted by the
    season's share of the bill's days, as for a mid-month price change
    (營業規章 第二十七條一), and multiplied by the bill's months."""
    idle_ratio = plan_data.get("billing_rules", {}).get("zero_usage_basic_fee_ratio")
    details = []
    for ts in month_index:
        scale = float(months)
        if idle_ratio is not None and idle_months[ts]:
            scale *= float(idle_ratio)
        for season, share in parts[ts].items():
            for label, quantity, rate in _basic_fee_rows(plan_data, inputs, season):
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


def _season_rate(entry: dict[str, Any], season: str) -> float | None:
    """A basic fee's price in a season."""
    if "summer" in entry or "non_summer" in entry:
        rate = entry.get("summer") if season == "summer" else entry.get("non_summer")
    else:
        rate = entry.get("cost")
    return None if rate is None else float(rate)


def _label_rate(plan_data: dict[str, Any], label: str, season: str) -> float | None:
    """The price of the basic fee with this label, or None if the plan has none."""
    entries = plan_data.get("basic_fees", [])
    entry = next((e for e in entries if e.get("label") == label), None)
    if entry is None:
        return None
    return _season_rate(entry, season) or 0.0


def _basic_fee_rows(
    plan_data: dict[str, Any], inputs: BillingInputs, season: str
) -> list[tuple[str, float, float]]:
    """A month of 基本電費 in a season, as (label, quantity, rate) rows."""
    formula = plan_data.get("billing_rules", {}).get("basic_fee_formula")
    if formula and inputs.contract_capacities:
        return _formula_rows(plan_data, inputs, formula, season)
    rows = []
    basic_fee = plan_data.get("basic_fee")
    if basic_fee is not None:
        count = inputs.basic_fee_inputs.get("basic_fee", 1.0)
        rows.append(("basic_fee", count, float(basic_fee)))
    household = _household_fee(plan_data, inputs, "installed")
    for entry in plan_data.get("basic_fees", []):
        label = entry.get("label", "")
        if entry.get("unit") == "per_household_month":
            if entry is not household:
                continue
            quantity = inputs.basic_fee_inputs.get(label, 1.0)
        else:
            quantity = inputs.basic_fee_inputs.get(label, 0.0)
        rate = _season_rate(entry, season)
        if quantity != 0 and rate is not None:
            rows.append((label, quantity, rate))
    return rows


def _formula_rows(
    plan_data: dict[str, Any],
    inputs: BillingInputs,
    formula: dict[str, Any],
    season: str,
) -> list[tuple[str, float, float]]:
    """A month of a 需量契約's 基本電費: 按戶計收, 經常契約, 非夏月 (非夏月 only)
    or 半尖峰契約, and the 週六半尖峰 and 離峰 contracts beyond half of the
    others (電價表 lines 374-403, 651-709 and 1025-1060)."""
    entries = {entry["label"]: entry for entry in plan_data.get("basic_fees", [])}

    def row(label: str, quantity: float) -> tuple[str, float, float]:
        return label, quantity, _season_rate(entries.get(label, {}), season) or 0.0

    rows = []
    household = _household_fee(plan_data, inputs, "demand")
    if household and household.get("cost") is not None:
        label = household["label"]
        count = inputs.basic_fee_inputs.get(label, 1.0)
        rows.append((label, count, float(household["cost"])))
    capacities = inputs.contract_capacities
    regular = capacities.get("regular", 0.0)
    rows.append(row(formula["regular_label"], regular))
    if formula["type"] == "regular_only":
        return rows
    if formula["type"] == "three_stage":
        second = capacities.get("semi_peak", 0.0)
        rows.append(row(formula["semi_peak_label"], second))
    else:
        second = capacities.get("non_summer", 0.0)
        if season != "summer":
            rows.append(row(formula["non_summer_label"], second))
    weekend = capacities.get("saturday_semi_peak", 0.0) + capacities.get(
        "off_peak", 0.0
    )
    weekend_ratio = float(formula.get("weekend_ratio", 0.5))
    rows.append(
        row(
            formula.get("saturday_label", ""),
            max(0.0, weekend - (regular + second) * weekend_ratio),
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
    plan_data: dict[str, Any],
    months: int,
    monthly_usage: pd.Series,
) -> pd.Series:
    rules = plan_data.get("billing_rules", {})
    rule = rules.get("over_2000_kwh_surcharge") or plan_data.get(
        "over_2000_kwh_surcharge"
    )
    surcharge = pd.Series(0.0, index=monthly_usage.index)
    if rule:
        # 每月總度數超過2000度之部分. A two-month bill's threshold is 4000 kWh,
        # as 第三章 五(一)2 doubles 分段度數 for 隔月抄表.
        threshold = rule.get("threshold_kwh", 2000) * months
        cost = rule.get("cost_per_kwh", 0.0)
        over = (monthly_usage - threshold).clip(lower=0.0)
        surcharge += over * cost
    return surcharge


def _power_factor_applies(eligible: dict[str, Any], inputs: BillingInputs) -> bool:
    """Whether the bill is one the 電價表 adjusts for power factor.

    An unknown meter_phase counts as eligible, since the caller gave a power
    factor. 用電設備容量 (20 kVA for 非時間 and 簡易型) is not an input.
    """
    phase = eligible.get("phase")
    if phase and inputs.meter_phase not in (None, phase):
        return False
    demand_kw = sum(inputs.contract_capacities.values())
    installed_kw = inputs.basic_fee_inputs.get("裝置契約", 0.0)
    if "min_contract_kw" in eligible:
        return demand_kw >= eligible["min_contract_kw"]
    if "min_installed_kw" in eligible or "min_demand_kw" in eligible:
        return installed_kw >= eligible.get(
            "min_installed_kw", math.inf
        ) or demand_kw >= eligible.get("min_demand_kw", math.inf)
    return True


def _household_costs(
    plan_data: dict[str, Any], basic_details: pd.DataFrame, month_index: pd.Index
) -> pd.Series:
    """The 按戶計收 part of each bill's basic fee."""
    labels = {"basic_fee"} | {
        entry["label"]
        for entry in plan_data.get("basic_fees", [])
        if entry.get("unit") == "per_household_month"
    }
    if basic_details.empty:
        return pd.Series(0.0, index=month_index)
    household = basic_details[basic_details["label"].isin(labels)]
    return (
        household.groupby("period")["cost"].sum().reindex(month_index, fill_value=0.0)
    )


def _calculate_adjustments(
    plan_data: dict[str, Any],
    inputs: BillingInputs,
    basic_costs: pd.Series,
    basic_details: pd.DataFrame,
    month_index: pd.Index,
    parts: dict[pd.Timestamp, dict[str, float]],
    context_df: pd.DataFrame,
    billing_periods: pd.PeriodIndex,
    energy_costs: pd.Series,
    surcharge: pd.Series,
    usage: pd.Series,
    rates: TariffRate,
    demand: pd.DataFrame | None,
    used: pd.Series,
) -> tuple[pd.Series, pd.DataFrame]:
    rules = plan_data.get("billing_rules", {})
    details: list[dict[str, Any]] = []
    over_costs = pd.Series(0.0, index=month_index)
    outside_energy = pd.Series(0.0, index=month_index)

    oc_rule = rules.get("over_contract_penalty")
    if oc_rule and _installed_only(inputs):
        _warn_installed_demand_over_capacity(inputs, demand)
    elif oc_rule:
        outside = (
            _times_outside_contract(inputs.contract_capacities)
            if oc_rule.get("outside_contract_basic_ratio")
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
                * _over_contract_fee(plan_data, oc_rule, over, season, outside)
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
                usage.to_numpy() * unit_costs(rates, context_df) * in_outside,
                index=usage.index,
            ).groupby(billing_periods).sum() * (
                oc_rule["outside_contract_energy_ratio"] - 1
            )
            extra.index = extra.index.to_timestamp()
            outside_energy = _to_jiao(
                inputs, extra.reindex(month_index, fill_value=0.0)
            )
            details.extend(
                {"period": idx, "type": "outside_contract_energy", "amount": float(v)}
                for idx, v in outside_energy.items()
            )

    pf_rule = rules.get("power_factor_adjustment")
    pf_cost = pd.Series(0.0, index=month_index)
    if (
        pf_rule
        and inputs.power_factor is not None
        and _power_factor_applies(pf_rule.get("eligible", {}), inputs)
    ):
        base = pf_rule.get("base_percent", 80)
        step = pf_rule.get("step_percent", 0.1)
        pf = min(float(inputs.power_factor), pf_rule.get("max_discount_percent", 95))
        # 功率因數 adjusts 該月份電費, but 按戶計收之基本電費，不列計功率因數調整費.
        target = (
            basic_costs
            - _household_costs(plan_data, basic_details, month_index)
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
    ratio = rules.get("bill_ratio")
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


def _minimum_fee(plan_data: dict[str, Any], cycle_months: int) -> float | None:
    """The least a bill covering cycle_months months is charged."""
    rules = plan_data.get("billing_rules", {})
    value = rules.get("min_monthly_fee")
    if value is None:
        return None
    return float(value) * cycle_months


def _apply_minimum_usage(
    plan_data: dict[str, Any],
    store: PlanStore,
    usage: pd.Series,
    inputs: BillingInputs,
    billing_periods: pd.PeriodIndex,
    cycle_months: int,
) -> pd.Series:
    rules = plan_data.get("billing_rules", {})
    ref = rules.get("minimum_usage_rules_ref")
    if not ref:
        return usage
    if (
        inputs.meter_phase is None
        or inputs.meter_voltage_v is None
        or inputs.meter_ampere is None
    ):
        return usage

    definitions = store.definitions()
    ruleset = definitions.get("minimum_usage_rules", {}).get(ref, [])
    if not ruleset:
        return usage

    # A 低壓電表 is one under 1000 V. 表燈 is supplied at 110, 220 or 380 V
    # (電價表 第三章 二, 營業規章 第三條).
    voltage = inputs.meter_voltage_v
    target = next(
        (
            item
            for item in ruleset
            if item["phase"] == inputs.meter_phase
            and (
                voltage == item.get("voltage_v")
                or voltage < item.get("voltage_v_below", 0)
            )
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
    ampere = min(float(inputs.meter_ampere), target.get("ampere_threshold", math.inf))
    min_kwh = ampere * target["kwh_per_ampere"]

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


_SEGMENT_FEE_LABELS = {
    "peak": "regular_label",
    "semi_peak": "semi_peak_label",
    "saturday_semi_peak": "saturday_label",
    "off_peak": "off_peak_label",
}


def _compute_over_contract_kw(
    inputs: BillingInputs,
    demand: pd.DataFrame | None,
    parts: dict[pd.Timestamp, dict[str, float]],
    oc_rule: dict[str, Any],
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


def _over_contract_fee(
    plan_data: dict[str, Any],
    oc_rule: dict[str, Any],
    over: dict[str, tuple[float, float]],
    season: str,
    outside: set[str],
) -> float:
    """A month's 超約 fee at a season's prices. 超出部分依適用電價，在契約容量10%
    以下部分按2倍、超過部分按3倍 (第三章 五(三)5, 第四章 七(二), 第五章 七(二)).
    Use outside the times a 週六半尖峰 or 離峰 contract alone covers pays 4.8倍
    (第三章 七(六), 第四章 八(六), 第五章 八(六))."""
    formula = plan_data.get("billing_rules", {}).get("basic_fee_formula", {})
    base_label = oc_rule.get("base_fee_label", "經常契約")
    ratio = oc_rule.get("threshold_ratio", 0.10)
    amount = 0.0
    counted = 0.0
    for segment, (kw, base) in over.items():
        label = formula.get(_SEGMENT_FEE_LABELS[segment], base_label)
        rate = _label_rate(plan_data, label, season)
        if rate is None:
            rate = _label_rate(plan_data, base_label, season)
        if rate is None:
            continue
        if segment in outside:
            amount += rate * kw * oc_rule["outside_contract_basic_ratio"]
            continue
        # 在契約容量10%以下部分: the contract this time's excess is over.
        low = min(kw, max(0.0, base * ratio - counted))
        counted += kw
        amount += rate * (
            low * oc_rule.get("rate_low", 2) + (kw - low) * oc_rule.get("rate_high", 3)
        )
    return amount


def _read_demand(
    inputs: BillingInputs,
    profile: Any,
    first: pd.Period,
    cycle_months: int,
    local: pd.DatetimeIndex,
    context: pd.DataFrame,
    times: np.ndarray,
    billing_periods: pd.PeriodIndex,
) -> pd.DataFrame | None:
    """Each 需量 as Taipower reads it, in Taiwan wall time, with the bill,
    season and time it falls in. 需量 is the 十五分鐘平均瓩數 (營業規章 第三條),
    times demand_adjustment_factor, cut to whole kW (施行細則 第二十八條).
    Demand on the usage's own timestamps reuses the usage's context."""
    demand = inputs.demand_kw
    if demand is None:
        return None
    demand = pd.Series(
        demand.to_numpy(dtype="float64"), index=taiwan_wall_time(demand.index)
    )
    _check_demand_resolution(demand)
    demand = _quarter_hour_demand(demand) * inputs.demand_adjustment_factor
    if not demand.index.equals(local):
        context = profile.evaluate(demand.index)
        times = _times(context)
        billing_periods = _bill_months(demand.index, first, cycle_months)
    return pd.DataFrame(
        {
            "kw": np.floor(np.round(demand.to_numpy(), 6)),
            "bill": billing_periods,
            "season": _labels(context["season"]),
            "time": times,
        },
        index=demand.index,
    )


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


def _labels(values: pd.Series) -> np.ndarray:
    """The string value of each season, day type or period."""
    return values.map({v: _label_value(v) for v in values.unique()}).to_numpy()


def _times(context: pd.DataFrame) -> np.ndarray:
    """Each row's time of day: 尖峰, 半尖峰, 週六半尖峰 or 離峰, the register
    its kWh is read on and the time its 最高需量 counts in. A 非時間電價 meter
    has one register, and one 最高需量 against 經常 (+ 非夏月)."""
    period = _labels(context["period"])
    saturday = _labels(context["day_type"]) == "saturday"
    period = np.where(period == "flat", "peak", period)
    return np.where(
        saturday & (period == "semi_peak"), "saturday_semi_peak", period
    ).astype(object)


def _calculate_over_contract_from_categories(
    max_demand: dict[str, float],
    capacities: dict[str, float],
    oc_rule: dict[str, Any],
    season: str,
    outside: set[str],
) -> dict[str, tuple[float, float]]:
    """超約瓩數 per time from each time's highest demand (第五章 七(一)).

    Each time's excess leaves out the largest excess of the times before it,
    so no kW is counted twice.
    """
    regular = capacities.get("regular", 0.0)
    if oc_rule.get("tier") == "three_stage":
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


def _calculate_energy_costs(
    usage: pd.Series,
    context_df: pd.DataFrame,
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

    interval_costs = usage * unit_costs(rates, context_df)
    totals = interval_costs.groupby(billing_periods).sum()
    if hasattr(totals, "index") and hasattr(totals.index, "to_timestamp"):
        totals.index = totals.index.to_timestamp()
    return totals


def _calculate_period_costs(
    usage: pd.Series,
    context_df: pd.DataFrame,
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

    unit_cost = unit_costs(rates, context_df)
    rows = pd.DataFrame(
        {
            "period": billing_periods.to_timestamp(),
            "season": context_df["season"].map(_label_value).to_numpy(),
            "period_type": context_df["period"].map(_label_value).to_numpy(),
            "usage_kwh": usage.to_numpy(),
            "energy_cost": usage.to_numpy() * unit_cost,
        }
    )
    return rows.groupby(columns[:3], sort=False, as_index=False)[columns[3:]].sum()


def _normalize_usage_to_series(
    usage: Any,
    start: Any = None,
    freq: str | None = None,
) -> pd.Series:
    """usage as a Series on a DatetimeIndex. A list needs start and freq, and
    a dict maps timestamps to kWh."""
    if isinstance(usage, pd.Series):
        if not isinstance(usage.index, pd.DatetimeIndex):
            raise InvalidUsageInput("usage index must be a pandas.DatetimeIndex")
        return usage

    if isinstance(usage, list):
        if start is None:
            raise InvalidUsageInput(
                "start parameter is required when usage is a list. "
                "Example: start='2024-01-01'"
            )
        if freq is None:
            raise InvalidUsageInput(
                "freq parameter is required when usage is a list. "
                "Example: freq='1h' or freq='15min'"
            )
        index = pd.date_range(start=start, periods=len(usage), freq=freq)
        return pd.Series(usage, index=index)

    if isinstance(usage, dict):
        try:
            index = pd.to_datetime(list(usage.keys()))
        except Exception as e:
            raise InvalidUsageInput(f"Cannot convert dict keys to datetime: {e}")
        return pd.Series(list(usage.values()), index=index)

    raise InvalidUsageInput(
        f"usage must be pd.Series, list, or dict, got {type(usage).__name__}"
    )


def calculate_bill_from_list(
    usage: list[float],
    plan_id: str,
    start: str | date,
    freq: str = "1h",
    inputs: BillingInputs | None = None,
    calendar_instance: TaiwanCalendar | None = None,
    cache_dir: Path | None = None,
    api_timeout: int | None = None,
    strict: bool = False,
) -> pd.DataFrame:
    """calculate_bill for kWh readings that start at start, one every freq.

    freq is a pandas frequency such as "15min" or "1h". Time-of-use plans
    need "1h" or finer.

    Example:
        result = calculate_bill_from_list(
            usage=[1.0, 1.5, 2.0, 1.8, ...],
            plan_id="residential_simple_2_tier",
            start="2026-07-01",
            freq="1h",
        )
    """
    series = _normalize_usage_to_series(usage, start=start, freq=freq)
    return calculate_bill(
        series,
        plan_id,
        inputs=inputs,
        calendar_instance=calendar_instance,
        cache_dir=cache_dir,
        api_timeout=api_timeout,
        strict=strict,
    )


def calculate_bill_from_dict(
    usage: dict[str | date, float],
    plan_id: str,
    inputs: BillingInputs | None = None,
    calendar_instance: TaiwanCalendar | None = None,
    cache_dir: Path | None = None,
    api_timeout: int | None = None,
    strict: bool = False,
) -> pd.DataFrame:
    """calculate_bill for a dict of timestamp, as a string or datetime, to kWh.

    Example:
        result = calculate_bill_from_dict(
            usage={
                "2026-07-01 00:00": 1.0,
                "2026-07-01 01:00": 1.5,
                "2026-07-01 02:00": 2.0,
            },
            plan_id="residential_simple_2_tier",
        )
    """
    series = _normalize_usage_to_series(usage)
    return calculate_bill(
        series,
        plan_id,
        inputs=inputs,
        calendar_instance=calendar_instance,
        cache_dir=cache_dir,
        api_timeout=api_timeout,
        strict=strict,
    )
