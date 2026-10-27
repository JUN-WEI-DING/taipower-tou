"""Billing utilities based on plans.json rules."""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from taipower_tou.calendar import TaiwanCalendar, taiwan_calendar, taiwan_wall_time
from taipower_tou.errors import (
    InvalidBasicFeeInput,
    InvalidUsageInput,
    MissingRequiredInput,
    PartialPeriodWarning,
)
from taipower_tou.factory import (
    PlanRequirements,
    PlanStore,
    _build_tariff_plan_from_data,
    _season_strategy,
)
from taipower_tou.models import BillingCycleType, _label_value
from taipower_tou.tariff import (
    TariffRate,
    check_price_dates,
    season_day_shares,
    tiered_energy_cost,
    unit_costs,
)


@dataclass
class BillingInputs:
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
    # 營業規章施行細則 第二十九條 rounding. False keeps every amount unrounded, for
    # callers that compare or optimize bills.
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
        """Create inputs for high voltage two-stage TOU plans.

        Args:
            regular: Regular contract capacity (kW)
            non_summer: Non-summer contract capacity (kW)
            saturday_semi_peak: Saturday semi-peak contract capacity (kW)
            off_peak: Off-peak contract capacity (kW)
            power_factor: Optional power factor percentage
            demand_kw: Optional demand series for penalty calculation
            demand_adjustment_factor: Adjustment factor for demand data

        Example:
            inputs = BillingInputs.for_high_voltage(
                regular=100,
                non_summer=50,
                saturday_semi_peak=30,
                off_peak=20,
            )
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
        """Create inputs for high voltage three-stage TOU plans.

        Args:
            regular: Regular contract capacity (kW)
            semi_peak: Semi-peak contract capacity (kW)
            saturday_semi_peak: Saturday semi-peak contract capacity (kW)
            off_peak: Off-peak contract capacity (kW)
            power_factor: Optional power factor percentage
            demand_kw: Optional demand series for penalty calculation
            demand_adjustment_factor: Adjustment factor for demand data
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
        """Create inputs for extra high voltage two-stage TOU plans.

        Args:
            regular: Regular contract capacity (kW)
            non_summer: Non-summer contract capacity (kW)
            saturday_semi_peak: Saturday semi-peak contract capacity (kW)
            off_peak: Off-peak contract capacity (kW)
            power_factor: Optional power factor percentage
            demand_kw: Optional demand series for penalty calculation
            demand_adjustment_factor: Adjustment factor for demand data
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
        """Create inputs for extra high voltage three-stage TOU plans.

        Args:
            regular: Regular contract capacity (kW)
            semi_peak: Semi-peak contract capacity (kW)
            saturday_semi_peak: Saturday semi-peak contract capacity (kW)
            off_peak: Off-peak contract capacity (kW)
            power_factor: Optional power factor percentage
            demand_kw: Optional demand series for penalty calculation
            demand_adjustment_factor: Adjustment factor for demand data
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
    def for_residential(
        cls,
        phase: str,
        voltage: int,
        ampere: float,
        basic_fee_multiplier: float = 1.0,
    ) -> BillingInputs:
        """Create inputs for residential plans with meter specification.

        Args:
            phase: Meter phase ("single" or "three")
            voltage: Voltage level (110, 220, or other valid voltage)
            ampere: Amperage rating
            basic_fee_multiplier: Multiplier for per-household fees (default 1.0)

        Example:
            inputs = BillingInputs.for_residential(
                phase="single",
                voltage=110,
                ampere=10,
            )
        """
        return cls(
            meter_phase=phase,
            meter_voltage_v=voltage,
            meter_ampere=ampere,
            basic_fee_inputs={"basic_fee": basic_fee_multiplier},
        )

    @classmethod
    def for_lighting_standard(
        cls,
        phase: str,
        contract_kw: float,
        household_count: float = 1.0,
    ) -> BillingInputs:
        """Create inputs for standard lighting TOU plans with contract capacity.

        Args:
            phase: Meter phase for per-household fee ("single" or "three")
            contract_kw: Contract capacity in kW
            household_count: Number of households (default 1.0)
        """
        label = "按戶計收-單相" if phase == "single" else "按戶計收-三相"
        return cls(
            contract_capacity_kw=contract_kw,
            basic_fee_inputs={label: household_count, "經常契約": contract_kw},
        )


def _get_required_capacities_for_formula(formula_type: str) -> set[str]:
    """Return required contract_capacities keys for each formula type."""
    if formula_type == "two_stage":
        return {"regular", "non_summer", "saturday_semi_peak", "off_peak"}
    if formula_type == "three_stage":
        return {"regular", "semi_peak", "saturday_semi_peak", "off_peak"}
    if formula_type == "regular_only":
        return {"regular"}
    return set()


def _validate_billing_inputs(
    plan_data: dict[str, Any],
    inputs: BillingInputs,
    strict: bool = False,
) -> list[str]:
    """Validate billing inputs and return warnings.

    Args:
        plan_data: The plan's JSON data
        inputs: User-provided billing inputs
        strict: If True, raise errors on unknown keys and missing optional fields

    Returns:
        A list of warning messages for non-strict validation issues

    Raises:
        MissingRequiredInput: If required inputs are missing
        InvalidBasicFeeInput: If basic_fee_inputs has invalid keys (strict mode)
    """
    requirements = PlanRequirements.from_plan_data(plan_data)
    warnings = []

    # 1. Check contract capacity requirement (critical - always enforced)
    if requirements.requires_contract_capacity:
        has_capacity = (
            inputs.contract_capacity_kw is not None or inputs.contract_capacities
        )
        if not has_capacity:
            raise MissingRequiredInput(
                f"Plan '{plan_data.get('id')}' requires contract capacity. "
                f"Provide either contract_capacity_kw or contract_capacities. "
                f"Use BillingInputs.for_high_voltage() or "
                f"BillingInputs.for_extra_high_voltage() for convenient setup."
            )

    # 2. Validate basic_fee_inputs keys
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

    # 3. For formula-based plans, validate required capacities
    if requirements.uses_basic_fee_formula and requirements.formula_type:
        required_caps = _get_required_capacities_for_formula(requirements.formula_type)
        provided_caps = set(inputs.contract_capacities.keys())
        missing_caps = required_caps - provided_caps

        if missing_caps:
            # In strict mode, this is an error
            if strict:
                raise MissingRequiredInput(
                    f"Formula type '{requirements.formula_type}' requires "
                    f"contract_capacities with keys: {required_caps}. "
                    f"Missing: {missing_caps}. "
                    f"Use BillingInputs.for_high_voltage() or similar factory method."
                )
            # In non-strict mode, warn
            warnings.append(
                f"Formula may require contract_capacities keys: {missing_caps}"
            )

    # 4. Check meter spec requirement for minimum usage rules
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


def _validate_usage_series(usage: pd.Series) -> None:
    """Validate usage series for billing entrypoints."""
    numeric_usage = pd.to_numeric(usage, errors="coerce")
    if numeric_usage.isna().any():
        raise InvalidUsageInput("usage series contains NaN or non-numeric values")
    if not np.isfinite(numeric_usage.to_numpy()).all():
        raise InvalidUsageInput("usage values must be finite")
    if (numeric_usage < 0).any():
        raise InvalidUsageInput("usage values must be non-negative")
    if not usage.index.is_monotonic_increasing:
        raise InvalidUsageInput("usage timestamps must be ordered")


def calculate_bill(
    usage: pd.Series,
    plan_id: str,
    inputs: BillingInputs | None = None,
    calendar_instance: TaiwanCalendar | None = None,
    cache_dir: Path | None = None,
    api_timeout: int | None = None,
    strict: bool = False,
) -> pd.DataFrame:
    if not isinstance(usage, pd.Series):
        raise InvalidUsageInput("usage must be a pandas.Series")
    if not isinstance(usage.index, pd.DatetimeIndex):
        raise InvalidUsageInput("usage index must be a pandas.DatetimeIndex")
    _validate_usage_series(usage)

    inputs = inputs or BillingInputs()
    store = PlanStore()
    plan_data = store.resolve_plan(plan_id)

    # Validate inputs against plan requirements
    validation_warnings = _validate_billing_inputs(plan_data, inputs, strict=strict)
    for warning in validation_warnings:
        warnings.warn(warning, UserWarning, stacklevel=2)

    calendar = calendar_instance or taiwan_calendar(
        cache_dir=cache_dir, api_timeout=api_timeout
    )

    if inputs.billing_cycle_months is None:
        inputs.billing_cycle_months = plan_data.get("billing_rules", {}).get(
            "billing_cycle_months"
        )

    usage_for_billing = _apply_minimum_usage(plan_data, store, usage, inputs)
    billing_periods = _billing_period_index(
        usage_for_billing.index, inputs.billing_cycle_months
    )
    _check_whole_months(usage.index, billing_periods, inputs.billing_cycle_months or 1)

    # Convert billing_cycle_months to BillingCycleType
    billing_cycle_type = BillingCycleType.MONTHLY
    if inputs.billing_cycle_months and inputs.billing_cycle_months > 1:
        # For bimonthly billing, default to odd-month cycle
        # (can be overridden by adding logic to determine odd vs even)
        billing_cycle_type = BillingCycleType.ODD_MONTH

    tariff_plan = _build_tariff_plan_from_data(
        plan_data,
        store,
        calendar,
        billing_cycle_type=billing_cycle_type,
    )
    check_price_dates(usage.index, tariff_plan.rates.price_dates)
    context = tariff_plan.profile.evaluate(usage_for_billing.index)
    energy_costs = _to_jiao(
        inputs,
        _calculate_energy_costs(
            usage_for_billing,
            context,
            billing_periods,
            tariff_plan,
            inputs.billing_cycle_months or 1,
        ),
    )

    month_index = energy_costs.index
    monthly_usage = usage_for_billing.groupby(billing_periods).sum()
    monthly_usage.index = monthly_usage.index.to_timestamp()

    basic_costs, basic_details = _calculate_basic_fees(
        plan_data,
        inputs,
        month_index,
        store,
        _idle_months(usage_for_billing, inputs, billing_periods, context),
    )
    basic_costs = _to_jiao(inputs, basic_costs)
    surcharge = _to_jiao(
        inputs, _calculate_surcharges(plan_data, inputs, monthly_usage)
    )
    adjustment, _ = _calculate_adjustments(
        plan_data,
        inputs,
        basic_costs,
        basic_details,
        month_index,
        store,
        context,
        billing_periods,
        energy_costs,
        surcharge,
        usage_for_billing,
        tariff_plan.rates,
    )

    total = _to_yuan(inputs, energy_costs + basic_costs + surcharge + adjustment)
    min_fee = _minimum_fee(plan_data, inputs.billing_cycle_months or 1)
    if min_fee is not None:
        total = total.clip(lower=min_fee)

    return pd.DataFrame(
        {
            "energy_cost": energy_costs,
            "basic_cost": basic_costs,
            "surcharge": surcharge,
            "adjustment": adjustment,
            "total": total,
        }
    )


def calculate_bill_simple(
    usage: pd.Series,
    plan_id: str,
    calendar_instance: TaiwanCalendar | None = None,
    cache_dir: Path | None = None,
    api_timeout: int | None = None,
    strict: bool = False,
) -> pd.DataFrame:
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
    if not isinstance(usage, pd.Series):
        raise InvalidUsageInput("usage must be a pandas.Series")
    if not isinstance(usage.index, pd.DatetimeIndex):
        raise InvalidUsageInput("usage index must be a pandas.DatetimeIndex")
    _validate_usage_series(usage)

    inputs = inputs or BillingInputs()
    store = PlanStore()
    plan_data = store.resolve_plan(plan_id)

    # Validate inputs against plan requirements
    validation_warnings = _validate_billing_inputs(plan_data, inputs, strict=strict)
    for warning in validation_warnings:
        warnings.warn(warning, UserWarning, stacklevel=2)

    calendar = calendar_instance or taiwan_calendar(
        cache_dir=cache_dir, api_timeout=api_timeout
    )

    if inputs.billing_cycle_months is None:
        inputs.billing_cycle_months = plan_data.get("billing_rules", {}).get(
            "billing_cycle_months"
        )

    usage_for_billing = _apply_minimum_usage(plan_data, store, usage, inputs)
    billing_periods = _billing_period_index(
        usage_for_billing.index, inputs.billing_cycle_months
    )
    _check_whole_months(usage.index, billing_periods, inputs.billing_cycle_months or 1)

    # Convert billing_cycle_months to BillingCycleType
    billing_cycle_type = BillingCycleType.MONTHLY
    if inputs.billing_cycle_months and inputs.billing_cycle_months > 1:
        # For bimonthly billing, default to odd-month cycle
        # (can be overridden by adding logic to determine odd vs even)
        billing_cycle_type = BillingCycleType.ODD_MONTH

    tariff_plan = _build_tariff_plan_from_data(
        plan_data,
        store,
        calendar,
        billing_cycle_type=billing_cycle_type,
    )
    check_price_dates(usage.index, tariff_plan.rates.price_dates)
    context = tariff_plan.profile.evaluate(usage_for_billing.index)

    energy_costs = _to_jiao(
        inputs,
        _calculate_energy_costs(
            usage_for_billing,
            context,
            billing_periods,
            tariff_plan,
            inputs.billing_cycle_months or 1,
        ),
    )
    month_index = energy_costs.index

    monthly_usage = usage_for_billing.groupby(billing_periods).sum()
    monthly_usage.index = monthly_usage.index.to_timestamp()

    basic_costs, basic_details = _calculate_basic_fees(
        plan_data,
        inputs,
        month_index,
        store,
        _idle_months(usage_for_billing, inputs, billing_periods, context),
    )
    basic_costs = _to_jiao(inputs, basic_costs)
    surcharge = _to_jiao(
        inputs, _calculate_surcharges(plan_data, inputs, monthly_usage)
    )
    adjustment, adjustment_details = _calculate_adjustments(
        plan_data,
        inputs,
        basic_costs,
        basic_details,
        month_index,
        store,
        context,
        billing_periods,
        energy_costs,
        surcharge,
        usage_for_billing,
        tariff_plan.rates,
    )

    total = _to_yuan(inputs, energy_costs + basic_costs + surcharge + adjustment)
    min_fee = _minimum_fee(plan_data, inputs.billing_cycle_months or 1)
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

    details = _calculate_period_costs(
        usage_for_billing,
        context,
        billing_periods,
        tariff_plan,
        inputs.billing_cycle_months or 1,
    )

    return {
        "summary": summary,
        "details": details,
        "basic_details": basic_details,
        "adjustment_details": adjustment_details,
    }


def _month_season_label(
    month_index: pd.Index,
    plan_data: dict[str, Any],
    store: PlanStore,
) -> list[str]:
    season_strategy = _season_strategy(plan_data, store)
    labels = []
    for ts in month_index:
        day = date(ts.year, ts.month, 1)
        season = season_strategy.get_season(day)
        labels.append(season.value if hasattr(season, "value") else str(season))
    return labels


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
    context: pd.DataFrame,
) -> pd.Series:
    """Bills with no kWh and no demand (抄見度數與最高需量均為0).

    An 裝置契約 time-of-use bill counts only peak kWh (第四章 五(五)).
    """
    peak = context["period"].map(_label_value) == "peak"
    if "裝置契約" in inputs.basic_fee_inputs and peak.any():
        usage = usage.where(peak, 0.0)
    used = usage.groupby(billing_periods).sum() > 0
    if inputs.demand_kw is not None:
        demand = inputs.demand_kw.reindex(usage.index).fillna(0.0)
        used |= demand.groupby(billing_periods).max() > 0
    used.index = used.index.to_timestamp()
    return ~used


def _calculate_basic_fees(
    plan_data: dict[str, Any],
    inputs: BillingInputs,
    month_index: pd.Index,
    store: PlanStore,
    idle_months: pd.Series,
) -> tuple[pd.Series, pd.DataFrame]:
    rules = plan_data.get("billing_rules", {})
    formula = rules.get("basic_fee_formula")
    season_labels = _month_season_label(month_index, plan_data, store)
    monthly = pd.Series(0.0, index=month_index)
    details: list[dict[str, Any]] = []

    if formula and inputs.contract_capacities:
        base_series, base_details = _basic_fee_from_formula(
            plan_data,
            inputs,
            month_index,
            store,
            formula,
            detailed=True,
        )
        monthly += base_series
        details.extend(base_details)
    else:
        basic_fee = plan_data.get("basic_fee")
        if basic_fee is not None:
            count = inputs.basic_fee_inputs.get("basic_fee", 1.0)
            value = float(basic_fee) * count
            monthly += value
            for ts in month_index:
                details.append(
                    {
                        "period": ts,
                        "label": "basic_fee",
                        "quantity": count,
                        "rate": float(basic_fee),
                        "cost": value,
                    }
                )

        household = _household_fee(plan_data, inputs, "installed")
        for entry in plan_data.get("basic_fees", []):
            label = entry.get("label", "")
            if entry.get("unit") == "per_household_month":
                if entry is not household:
                    continue
                quantity = inputs.basic_fee_inputs.get(label, 1.0)
            else:
                quantity = inputs.basic_fee_inputs.get(label, 0.0)
            if quantity == 0:
                continue
            for idx, season_label in enumerate(season_labels):
                if "summer" in entry or "non_summer" in entry:
                    rate = (
                        entry.get("summer")
                        if season_label == "summer"
                        else entry.get("non_summer")
                    )
                else:
                    rate = entry.get("cost")
                if rate is None:
                    continue
                cost = float(rate) * quantity
                monthly.iloc[idx] += cost
                details.append(
                    {
                        "period": month_index[idx],
                        "label": label,
                        "quantity": quantity,
                        "rate": float(rate),
                        "cost": cost,
                    }
                )

    idle_ratio = rules.get("zero_usage_basic_fee_ratio")
    if idle_ratio is not None:
        scale = idle_months.map({True: float(idle_ratio), False: 1.0})
        monthly = monthly * scale
        for item in details:
            item["cost"] = float(item["cost"]) * scale[item["period"]]

    if inputs.billing_cycle_months and inputs.billing_cycle_months > 1:
        monthly = monthly * inputs.billing_cycle_months
        for item in details:
            item["cost"] = float(item["cost"]) * inputs.billing_cycle_months

    return monthly, pd.DataFrame(details)


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
    inputs: BillingInputs,
    monthly_usage: pd.Series,
) -> pd.Series:
    rules = plan_data.get("billing_rules", {})
    rule = rules.get("over_2000_kwh_surcharge") or plan_data.get(
        "over_2000_kwh_surcharge"
    )
    surcharge = pd.Series(0.0, index=monthly_usage.index)
    if rule:
        threshold = rule.get("threshold_kwh", 2000)
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
    demand_kw = sum(inputs.contract_capacities.values()) or (
        inputs.contract_capacity_kw or 0.0
    )
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
    store: PlanStore,
    context_df: pd.DataFrame,
    billing_periods: pd.PeriodIndex,
    energy_costs: pd.Series,
    surcharge: pd.Series,
    usage: pd.Series,
    rates: TariffRate,
) -> tuple[pd.Series, pd.DataFrame]:
    rules = plan_data.get("billing_rules", {})
    details: list[dict[str, Any]] = []
    over_costs = pd.Series(0.0, index=month_index)
    outside_energy = pd.Series(0.0, index=month_index)

    oc_rule = rules.get("over_contract_penalty")
    installed_only = "裝置契約" in inputs.basic_fee_inputs and not (
        inputs.contract_capacities or inputs.contract_capacity_kw
    )
    if oc_rule and installed_only:
        _warn_installed_demand_over_capacity(inputs, context_df, billing_periods)
    elif oc_rule:
        base_label = oc_rule.get("base_fee_label", "經常契約")
        formula = rules.get("basic_fee_formula", {})
        seasons = dict(
            zip(month_index, _month_season_label(month_index, plan_data, store))
        )
        outside_ratio = oc_rule.get("outside_contract_basic_ratio")
        outside = (
            _times_outside_contract(inputs.contract_capacities)
            if outside_ratio
            else set()
        )
        over_by_bill = _compute_over_contract_kw(
            inputs, context_df, billing_periods, oc_rule, seasons, outside
        )
        ratio = oc_rule.get("threshold_ratio", 0.10)
        rate_low = oc_rule.get("rate_low", 2)
        rate_high = oc_rule.get("rate_high", 3)
        for idx, over in (over_by_bill or {}).items():
            amount = 0.0
            counted = 0.0
            for segment, (kw, base) in over.items():
                # 超出部分依適用電價: each time's excess at its own 契約電價.
                label = formula.get(_SEGMENT_FEE_LABELS[segment], base_label)
                rate = _basic_fee_rate_for_label(plan_data, label, month_index, store)
                if rate is None:
                    rate = _basic_fee_rate_for_label(
                        plan_data, base_label, month_index, store
                    )
                if rate is None:
                    continue
                if segment in outside:
                    amount += rate.loc[idx] * kw * outside_ratio
                    continue
                # 在契約容量10%以下部分: the contract this time's excess is over.
                low = min(kw, max(0.0, base * ratio - counted))
                counted += kw
                amount += rate.loc[idx] * (low * rate_low + (kw - low) * rate_high)
            over_costs.loc[idx] = _to_jiao(inputs, amount)
            details.append(
                {"period": idx, "type": "over_contract", "amount": float(amount)}
            )
        if outside:
            # 八(六): 1.6倍計收流動電費 for the kWh outside the contract's times.
            in_outside = _demand_categories(context_df).isin(outside).to_numpy()
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
        used = usage.groupby(billing_periods).sum() > 0
        used.index = used.index.to_timestamp()
        pf_cost = pf_cost.where(used.reindex(month_index, fill_value=False), 0.0)
        if pf != base:
            details.extend(
                {"period": idx, "type": "power_factor", "amount": float(value)}
                for idx, value in pf_cost.items()
            )

    adjustment = over_costs + outside_energy + pf_cost
    return adjustment, pd.DataFrame(details)


def _warn_installed_demand_over_capacity(
    inputs: BillingInputs,
    context_df: pd.DataFrame,
    billing_periods: pd.PeriodIndex,
) -> None:
    """第四章 七(一)2: a metered 裝置契約 user stays on 裝置契約電價 and pays no
    超約, until 最高需量 passes the 裝置契約容量. From that month the bill moves
    to 需量契約電價, at a 契約容量 the 電價表 does not give."""
    if inputs.demand_kw is None:
        return
    installed = inputs.basic_fee_inputs["裝置契約"]
    demand = inputs.demand_kw.reindex(context_df.index).fillna(0.0)
    peaks = demand.groupby(billing_periods).max()
    over = peaks[peaks > installed]
    if not over.empty:
        warnings.warn(
            f"最高需量 {over.iloc[0]:g} kW in {over.index[0]} passes the 裝置契約 "
            f"{installed:g} kW. From that month Taipower bills 需量契約電價; pass "
            "contract_capacities with the new 契約容量 to bill it.",
            UserWarning,
            stacklevel=4,
        )


def _basic_fee_rate_for_label(
    plan_data: dict[str, Any],
    label: str,
    month_index: pd.Index,
    store: PlanStore,
) -> pd.Series | None:
    entries = plan_data.get("basic_fees", [])
    entry = next((e for e in entries if e.get("label") == label), None)
    if not entry:
        return None
    season_labels = _month_season_label(month_index, plan_data, store)
    rates = []
    for season_label in season_labels:
        if "summer" in entry or "non_summer" in entry:
            rate = (
                entry.get("summer")
                if season_label == "summer"
                else entry.get("non_summer")
            )
        else:
            rate = entry.get("cost")
        rates.append(float(rate) if rate is not None else 0.0)
    return pd.Series(rates, index=month_index)


def _basic_fee_from_formula(
    plan_data: dict[str, Any],
    inputs: BillingInputs,
    month_index: pd.Index,
    store: PlanStore,
    formula: dict[str, Any],
    detailed: bool = False,
) -> tuple[pd.Series, list[dict[str, Any]]]:
    season_labels = _month_season_label(month_index, plan_data, store)
    rates = {entry["label"]: entry for entry in plan_data.get("basic_fees", [])}
    monthly = pd.Series(0.0, index=month_index)
    details: list[dict[str, Any]] = []
    capacities = inputs.contract_capacities
    weekend_ratio = float(formula.get("weekend_ratio", 0.5))

    entry = _household_fee(plan_data, inputs, "demand")
    # 三段式: 僅在週六半尖峰時間或離峰時間用電 users pay 按週六半尖峰契約容量與
    # 離峰契約容量 only, where 二段式 says 按戶及按 (第三章 五(三)2, 第四章 五(三)2).
    if entry and not (
        formula["type"] == "three_stage" and _times_outside_contract(capacities)
    ):
        household_label = entry["label"]
        count = inputs.basic_fee_inputs.get(household_label, 1.0)
        if entry.get("cost") is not None:
            monthly += float(entry["cost"]) * count
            if detailed:
                for ts in month_index:
                    details.append(
                        {
                            "period": ts,
                            "label": household_label,
                            "quantity": count,
                            "rate": float(entry["cost"]),
                            "cost": float(entry["cost"]) * count,
                        }
                    )

    def _season_rate(label: str, season_label: str) -> float:
        entry = rates.get(label, {})
        if "summer" in entry or "non_summer" in entry:
            rate = (
                entry.get("summer")
                if season_label == "summer"
                else entry.get("non_summer")
            )
            return float(rate) if rate is not None else 0.0
        rate = entry.get("cost")
        return float(rate) if rate is not None else 0.0

    for idx, season_label in enumerate(season_labels):
        if formula["type"] == "regular_only":
            rate = _season_rate(formula["regular_label"], season_label)
            quantity = capacities.get("regular", 0.0)
            cost = rate * quantity
            monthly.iloc[idx] += cost
            if detailed:
                details.append(
                    {
                        "period": month_index[idx],
                        "label": formula["regular_label"],
                        "quantity": quantity,
                        "rate": rate,
                        "cost": cost,
                    }
                )
            continue

        if formula["type"] == "two_stage":
            regular_rate = _season_rate(formula["regular_label"], season_label)
            non_summer_rate = _season_rate(formula["non_summer_label"], season_label)
            saturday_rate = _season_rate(
                formula.get("saturday_label", ""), season_label
            )
            regular = capacities.get("regular", 0.0)
            non_summer = capacities.get("non_summer", 0.0)
            saturday = capacities.get("saturday_semi_peak", 0.0)
            off_peak = capacities.get("off_peak", 0.0)

            weekend_base = (saturday + off_peak) - (
                regular + non_summer
            ) * weekend_ratio
            weekend_base = max(0.0, weekend_base)

            if season_label == "summer":
                cost_regular = regular_rate * regular
                cost_weekend = saturday_rate * weekend_base
                monthly.iloc[idx] += cost_regular + cost_weekend
                if detailed:
                    details.append(
                        {
                            "period": month_index[idx],
                            "label": formula["regular_label"],
                            "quantity": regular,
                            "rate": regular_rate,
                            "cost": cost_regular,
                        }
                    )
                    details.append(
                        {
                            "period": month_index[idx],
                            "label": formula.get("saturday_label", ""),
                            "quantity": weekend_base,
                            "rate": saturday_rate,
                            "cost": cost_weekend,
                        }
                    )
            else:
                cost_regular = regular_rate * regular
                cost_non_summer = non_summer_rate * non_summer
                cost_weekend = saturday_rate * weekend_base
                monthly.iloc[idx] += cost_regular + cost_non_summer + cost_weekend
                if detailed:
                    details.append(
                        {
                            "period": month_index[idx],
                            "label": formula["regular_label"],
                            "quantity": regular,
                            "rate": regular_rate,
                            "cost": cost_regular,
                        }
                    )
                    details.append(
                        {
                            "period": month_index[idx],
                            "label": formula["non_summer_label"],
                            "quantity": non_summer,
                            "rate": non_summer_rate,
                            "cost": cost_non_summer,
                        }
                    )
                    details.append(
                        {
                            "period": month_index[idx],
                            "label": formula.get("saturday_label", ""),
                            "quantity": weekend_base,
                            "rate": saturday_rate,
                            "cost": cost_weekend,
                        }
                    )
            continue

        if formula["type"] == "three_stage":
            regular_rate = _season_rate(formula["regular_label"], season_label)
            semi_rate = _season_rate(formula["semi_peak_label"], season_label)
            saturday_rate = _season_rate(
                formula.get("saturday_label", ""), season_label
            )
            regular = capacities.get("regular", 0.0)
            semi_peak = capacities.get("semi_peak", 0.0)
            saturday = capacities.get("saturday_semi_peak", 0.0)
            off_peak = capacities.get("off_peak", 0.0)

            weekend_base = (saturday + off_peak) - (regular + semi_peak) * weekend_ratio
            weekend_base = max(0.0, weekend_base)

            cost_regular = regular_rate * regular
            cost_semi = semi_rate * semi_peak
            cost_weekend = saturday_rate * weekend_base
            monthly.iloc[idx] += cost_regular + cost_semi + cost_weekend
            if detailed:
                details.append(
                    {
                        "period": month_index[idx],
                        "label": formula["regular_label"],
                        "quantity": regular,
                        "rate": regular_rate,
                        "cost": cost_regular,
                    }
                )
                details.append(
                    {
                        "period": month_index[idx],
                        "label": formula["semi_peak_label"],
                        "quantity": semi_peak,
                        "rate": semi_rate,
                        "cost": cost_semi,
                    }
                )
                details.append(
                    {
                        "period": month_index[idx],
                        "label": formula.get("saturday_label", ""),
                        "quantity": weekend_base,
                        "rate": saturday_rate,
                        "cost": cost_weekend,
                    }
                )

    return monthly, details


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

    target = None
    for item in ruleset:
        if item.get("phase") != inputs.meter_phase:
            continue
        if item.get("voltage_v") != inputs.meter_voltage_v:
            continue
        target = item
        break

    if not target:
        return usage

    # A low-voltage meter over its ampere_threshold counts as the threshold.
    ampere = min(float(inputs.meter_ampere), target.get("ampere_threshold", math.inf))
    min_kwh = ampere * target["kwh_per_ampere"]

    if min_kwh <= 0:
        return usage

    billing_periods = _billing_period_index(usage.index, inputs.billing_cycle_months)
    adjusted = usage.copy()
    cycle_months = inputs.billing_cycle_months or 1
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


def _billing_period_index(
    index: pd.DatetimeIndex, cycle_months: int | None
) -> pd.PeriodIndex:
    index = taiwan_wall_time(index)
    if not cycle_months or cycle_months <= 1:
        return index.to_period("M")
    first = index.min()
    if first is pd.NaT:
        return index.to_period("M")
    start_year = first.year
    start_month = first.month
    months_since = (index.year - start_year) * 12 + (index.month - start_month)
    group = months_since // cycle_months
    base = pd.PeriodIndex(index, freq="M")
    start = base.min()
    return pd.PeriodIndex([start + int(g) * cycle_months for g in group], freq="M")


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
        _warn_partial_period(first_day.date(), last_day.date(), cycle_months)


# pandas resets Python's per-location warning registry, so remember the usage
# spans already warned about.
@cache
def _warn_partial_period(first_day: date, last_day: date, cycle_months: int) -> None:
    warnings.warn(
        f"Bills cover {cycle_months} calendar month(s) each, counted from the "
        f"first month of usage. Usage from {first_day} to {last_day} leaves "
        "part of the first or last bill's months empty, so that bill is not "
        "one Taipower bill. Taipower bills from one meter reading to the next.",
        PartialPeriodWarning,
        stacklevel=4,
    )


def _check_demand_resolution(demand: pd.Series) -> None:
    """Check demand data resolution and warn if coarser than 15 minutes.

    Taiwan Power Company calculates demand penalties based on 15-minute
    interval data. Using hourly or coarser data may underestimate peak demand
    and result in inaccurate penalty calculations.

    Args:
        demand: pandas Series with DatetimeIndex containing demand values in kW
    """
    if len(demand) < 2:
        return

    minutes = demand.index.to_series().diff().median().total_seconds() / 60
    if minutes > 15:
        warnings.warn(
            f"Demand data resolution is approximately {int(minutes)} minutes, "
            f"which is coarser than the recommended 15-minute resolution. "
            f"Taiwan Power Company calculates demand penalties based on 15-minute "
            f"intervals. Using coarser data may underestimate peak demand and result "
            f"in inaccurate penalty calculations. "
            f"Consider using 'demand_adjustment_factor' parameter to apply a "
            f"conservative adjustment (e.g., 1.1-1.2 for hourly data).",
            UserWarning,
            stacklevel=3,
        )


_SEGMENT_FEE_LABELS = {
    "peak": "regular_label",
    "semi_peak": "semi_peak_label",
    "saturday_semi_peak": "saturday_label",
    "off_peak": "off_peak_label",
}


def _compute_over_contract_kw(
    inputs: BillingInputs,
    context_df: pd.DataFrame,
    billing_periods: pd.PeriodIndex,
    oc_rule: dict[str, Any],
    seasons: dict[pd.Timestamp, str],
    outside: set[str],
) -> dict[pd.Timestamp, dict[str, tuple[float, float]]] | None:
    """Each bill's 超約瓩數 and the contract it is over, by time, in the order
    the 電價表 deducts them."""
    if inputs.over_contract_kw is not None:
        contract_kw = inputs.contract_capacity_kw or inputs.contract_capacities.get(
            "regular", 0.0
        )
        return {
            ts: {"peak": (float(inputs.over_contract_kw), contract_kw)}
            for ts in billing_periods.unique().to_timestamp()
        }
    demand = inputs.demand_kw
    if demand is None:
        return None
    if not isinstance(demand, pd.Series) or not isinstance(
        demand.index, pd.DatetimeIndex
    ):
        raise InvalidUsageInput("demand_kw must be a pandas.Series with DatetimeIndex")

    # Detect data resolution and warn if coarser than 15 minutes
    _check_demand_resolution(demand)

    # Apply adjustment factor if specified (default is 1.0)
    if inputs.demand_adjustment_factor != 1.0:
        demand = demand * inputs.demand_adjustment_factor

    categories = _demand_categories(context_df)
    demand = demand.reindex(context_df.index)
    combined = pd.DataFrame(
        {
            "demand": demand.values,
            "category": categories,
            "period": billing_periods,
        },
        index=context_df.index,
    )
    # 營業規章施行細則 第二十八條: 用電最高需量以瓩為計量單位，小數以下捨棄.
    max_by_cat = np.floor(
        combined.groupby(["period", "category"], sort=False)["demand"].max().fillna(0.0)
    )
    results = {}
    for period, group in max_by_cat.groupby(level=0, sort=False):
        ts = period.to_timestamp()
        results[ts] = _calculate_over_contract_from_categories(
            group.droplevel(0).to_dict(),
            inputs.contract_capacities,
            oc_rule,
            seasons.get(ts, "non_summer"),
            outside,
        )
    return results


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


def _demand_categories(context_df: pd.DataFrame) -> pd.Series:
    categories = []
    for day_type, period in zip(context_df["day_type"], context_df["period"]):
        period = _label_value(period)
        if _label_value(day_type) == "saturday" and period == "semi_peak":
            categories.append("saturday_semi_peak")
        elif period == "flat":
            # 非時間電價: one 最高需量 for the month, against 經常 (+ 非夏月).
            categories.append("peak")
        else:
            categories.append(period)
    return pd.Series(categories, index=context_df.index)


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


# ============================================================================
# Flexible Input Support (Non-Pandas Entry Points)
# ============================================================================


def _normalize_usage_to_series(
    usage: Any,
    start: Any = None,
    freq: str | None = None,
) -> pd.Series:
    """Convert various input formats to pandas.Series with DatetimeIndex.

    Args:
        usage: Input data - pd.Series, list of floats, or dict of timestamp:value
        start: Start date (required if usage is list), e.g. "2024-01-01"
        freq: Frequency string (e.g., "15min", "1h", "1D")

    Returns:
        pandas.Series with DatetimeIndex

    Raises:
        InvalidUsageInput: If input format is invalid or missing required params
    """
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
        # Convert dict keys to timestamps
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
    """Calculate bill from a list of usage values.

    This is a convenience function that avoids the need to create pandas objects.

    Args:
        usage: List of usage values in kWh
        plan_id: The plan identifier (flexible matching supported)
        start: Start date for the usage data (e.g., "2024-01-01")
        freq: Frequency of the data (e.g., "15min", "1h", "1D")
        inputs: Optional billing inputs
        calendar_instance: Optional calendar instance
        cache_dir: Deprecated, has no effect
        api_timeout: Deprecated, has no effect
        strict: If True, raise errors on invalid/missing inputs

    Returns:
        DataFrame with billing breakdown

    Example:
        result = calculate_bill_from_list(
            usage=[1.0, 1.5, 2.0, 1.8, ...],
            plan_id="residential_simple_2_tier",
            start="2024-01-01",
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
    """Calculate bill from a dictionary of timestamp -> usage values.

    This is a convenience function for irregularly-spaced or
    pre-aggregated usage data.

    Args:
        usage: Dictionary mapping timestamps to usage values in kWh.
                Timestamps can be strings or datetime objects.
        plan_id: The plan identifier (flexible matching supported)
        inputs: Optional billing inputs
        calendar_instance: Optional calendar instance
        cache_dir: Deprecated, has no effect
        api_timeout: Deprecated, has no effect
        strict: If True, raise errors on invalid/missing inputs

    Returns:
        DataFrame with billing breakdown

    Example:
        result = calculate_bill_from_dict(
            usage={
                "2024-01-01 00:00": 1.0,
                "2024-01-01 01:00": 1.5,
                "2024-01-01 02:00": 2.0,
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
