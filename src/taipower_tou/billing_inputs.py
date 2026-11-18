"""What a bill takes besides usage, and the checks that refuse or warn of
an input before any amount is computed."""

from __future__ import annotations

import math
import numbers
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np
import pandas as pd

from taipower_tou import _warnings
from taipower_tou.errors import (
    InvalidBasicFeeInput,
    InvalidBillingInput,
    InvalidUsageInput,
    MissingRequiredInput,
)
from taipower_tou.factory import (
    PlanRequirements,
    PlanRules,
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
    rules: PlanRules, inputs: BillingInputs, strict: bool
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
    cycle_months = int(inputs.billing_cycle_months or rules.cycle_months or 1)
    parsed = replace(
        inputs,
        contract_capacities=contracts,
        contract_capacity_kw=None,
        meter_phase=inputs.meter_phase and inputs.meter_phase.lower(),
        billing_cycle_months=cycle_months,
    )
    for message in _validate_billing_inputs(rules, parsed, cycle_months, strict):
        _warnings.warn(message, UserWarning)
    return parsed, cycle_months


def _validate_billing_inputs(
    rules: PlanRules,
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
    requirements = PlanRequirements.from_rules(rules)
    warnings = []
    contracts = inputs.contract_capacities
    contract_keys = requirements.contract_keys

    if requirements.requires_contract_capacity and not contracts:
        raise MissingRequiredInput(
            f"Plan '{rules.plan_id}' requires contract capacity. "
            f"Provide either contract_capacity_kw or contract_capacities. "
            f"Use BillingInputs.for_high_voltage() or "
            f"BillingInputs.for_extra_high_voltage() for convenient setup."
        )

    valid_basic_fee_labels = set(requirements.valid_basic_fee_labels)
    if rules.basic_fee is not None:
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
            f"Plan '{rules.plan_id}' bills no {sorted(unknown_contracts)} "
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
            f"Plan '{rules.plan_id}' bills its basic fee per kW of "
            "contract_capacities, or of a 裝置契約 in basic_fee_inputs where the "
            "plan has one. With neither, it bills no kW."
        )
        if strict:
            raise MissingRequiredInput(message)
        warnings.append(message)
    if cycle_months > 1 and contract_keys & set(contracts):
        warnings.append(
            f"Taipower bills a 契約容量 every month, since 超約 is on 當月最高需量. "
            f"This bill of plan '{rules.plan_id}' covers {cycle_months} "
            "months and does not match Taipower's."
        )

    if requirements.requires_meter_spec:
        if not all([inputs.meter_phase, inputs.meter_voltage_v, inputs.meter_ampere]):
            if strict:
                raise MissingRequiredInput(
                    f"Plan '{rules.plan_id}' has minimum usage rules. "
                    f"Providing meter_phase, meter_voltage_v, and meter_ampere "
                    f"is required for accurate billing. "
                    f"Use BillingInputs.for_residential() for convenient setup."
                )
            warnings.append(
                f"Plan '{rules.plan_id}' has minimum usage rules. "
                f"Providing meter specifications is recommended."
            )

    return warnings


def _check_usage_resolution(rules: PlanRules, usage: pd.Series) -> None:
    """Warn for time-of-use usage that steps by more than an hour. A reading
    is priced at the period of its timestamp, so a day's kWh would all be
    priced at 00:00. Irregular readings warn only when every gap between
    them is a multiple of one step over an hour."""
    if not rules.time_of_use or len(usage) < 2:
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
