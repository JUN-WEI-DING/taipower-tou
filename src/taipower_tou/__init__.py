"""Public package entry point for the Taiwan TOU calculator."""

from __future__ import annotations

from typing import Any

from taipower_tou.billing import calculate_bill, calculate_bill_breakdown
from taipower_tou.billing_inputs import BillingInputs
from taipower_tou.calendar import TaiwanCalendar, taiwan_calendar
from taipower_tou.custom import (
    CustomCalendar,
    WeekdayDayTypeStrategy,
    build_day_schedule,
    build_tariff_plan,
    build_tariff_profile,
    build_tariff_rate,
    custom_calendar,
)
from taipower_tou.errors import (
    CalendarError,
    InvalidBasicFeeInput,
    InvalidBillingInput,
    InvalidUsageInput,
    MissingRequiredInput,
    PartialPeriodWarning,
    PowerKitError,
    TariffError,
    UncheckedPriceWarning,
    UncheckedYearWarning,
    UnknownPlanError,
)
from taipower_tou.factory import PlanRequirements, PlanStore, TariffFactory
from taipower_tou.models import BillingCycleType
from taipower_tou.tariff import (
    PeriodType,
    SeasonType,
    TaiwanDayTypeStrategy,
    TaiwanSeasonStrategy,
    TariffPlan,
    TariffProfile,
)

__version__ = "0.4.0"


def is_holiday(
    target: object,
    calendar: TaiwanCalendar | CustomCalendar | None = None,
) -> bool:
    """Whether target is a 離峰日 on calendar, taiwan_calendar() by default.

    See TaiwanCalendar.is_holiday.
    """
    calendar_instance = calendar or taiwan_calendar()
    return calendar_instance.is_holiday(target)


def available_plans() -> dict[str, str]:
    """Every plan ID with its Chinese name."""
    from taipower_tou.factory import _PLAN_NAME_MAP

    return dict(_PLAN_NAME_MAP)


def plan(
    name: str,
    calendar_instance: TaiwanCalendar | CustomCalendar | None = None,
    *,
    billing_cycle_type: BillingCycleType = BillingCycleType.MONTHLY,
) -> TariffPlan:
    """The tariff plan that name names.

    Use a plan ID or name from `available_plans()`.
    使用 `available_plans()` 的 plan ID 或中文名稱。

    Args:
        name: A plan ID or name, ignoring case and surrounding spaces, or
            part of exactly one plan's ID or name.
        calendar_instance: Decides 離峰日. Defaults to taiwan_calendar(),
            which covers 2014-2100.
        billing_cycle_type: How calculate_costs and monthly_breakdown pair
            months on a tiered plan. Time-of-use plans ignore it.

    Raises:
        UnknownPlanError: No plan or more than one matches name, or the plan
            was removed. It is also a KeyError and a ValueError.

    Example:
        >>> plan = tou.plan("residential_simple_2_tier")
        >>> # For odd-month billing cycle (bimonthly)
        >>> plan = tou.plan("residential_non_tou",
        ...                 billing_cycle_type=BillingCycleType.ODD_MONTH)
    """
    calendar = calendar_instance or taiwan_calendar()
    return TariffFactory.create(
        name, calendar=calendar, billing_cycle_type=billing_cycle_type
    )


def period_at(
    target: object,
    plan_name: str,
    calendar_instance: TaiwanCalendar | CustomCalendar | None = None,
) -> Any:
    selected_plan = plan(plan_name, calendar_instance)
    return selected_plan.period_at(target)


def period_context(
    target: object,
    plan_name: str,
    calendar_instance: TaiwanCalendar | CustomCalendar | None = None,
) -> Any:
    selected_plan = plan(plan_name, calendar_instance)
    return selected_plan.period_context(target)


def period_codes(
    index: Any,
    plan_name: str,
    calendar_instance: TaiwanCalendar | CustomCalendar | None = None,
) -> Any:
    """period_context for a DatetimeIndex, with categorical columns.

    Each column's `.cat.codes` are integers and its `.cat.categories` their
    names as strings, such as "summer", "saturday" and "semi_peak".

    Example:
        >>> idx = pd.date_range("2026-07-18 08:00", periods=2, freq="2h")
        >>> codes = tou.period_codes(idx, "high_voltage_three_stage")
        >>> list(codes["period"].astype(str))
        ['off_peak', 'semi_peak']
    """
    selected_plan = plan(plan_name, calendar_instance)
    return selected_plan.period_codes(index)


def costs(
    usage: Any,
    plan_name: str,
    calendar_instance: TaiwanCalendar | CustomCalendar | None = None,
) -> Any:
    selected_plan = plan(plan_name, calendar_instance)
    return selected_plan.calculate_costs(usage)


def monthly_breakdown(
    usage: Any,
    plan_name: str,
    include_shares: bool = False,
    calendar_instance: TaiwanCalendar | CustomCalendar | None = None,
    *,
    billing_cycle_type: BillingCycleType = BillingCycleType.MONTHLY,
) -> Any:
    selected_plan = plan(
        plan_name, calendar_instance, billing_cycle_type=billing_cycle_type
    )
    return selected_plan.monthly_breakdown(usage, include_shares=include_shares)


def plan_details(
    plan_name: str,
    calendar_instance: TaiwanCalendar | CustomCalendar | None = None,
) -> dict[str, Any]:
    selected_plan = plan(plan_name, calendar_instance)
    return selected_plan.describe()


def pricing_context(
    target: object,
    plan_name: str,
    usage: Any = None,
    include_details: bool = False,
    calendar_instance: TaiwanCalendar | CustomCalendar | None = None,
) -> Any:
    selected_plan = plan(plan_name, calendar_instance)
    return selected_plan.pricing_context(
        target,
        usage_kwh=usage,
        include_details=include_details,
    )


def get_plan_requirements(plan_name: str) -> dict[str, Any]:
    """The inputs a plan's bill reads, with plan_name matched as plan() does.

    Returns:
        A dict with:
            - requires_contract_capacity: True for 高壓 and 特高壓 plans.
              calculate_bill raises MissingRequiredInput for them without a
              contract.
            - requires_meter_spec: True for plans with a 底度, which needs
              meter_phase, meter_voltage_v and meter_ampere.
            - valid_basic_fee_labels: The plan's basic fee labels, in no
              fixed order. 簡易型 plans also take "basic_fee".
            - uses_basic_fee_formula: True if the basic fee is per kW of
              contract_capacities.
            - formula_type: "two_stage", "three_stage", "regular_only", or
              None without a formula.
            - contract_keys: The contract_capacities keys the plan bills,
              sorted. A key outside them warns and is left out.

    Example:
        >>> reqs = get_plan_requirements("high_voltage_2_tier")
        >>> reqs["requires_contract_capacity"]
        True
        >>> sorted(reqs["valid_basic_fee_labels"])
        ['經常契約', '週六半尖峰契約', '離峰契約', '非夏月契約']
        >>> reqs["contract_keys"]
        ['non_summer', 'off_peak', 'regular', 'saturday_semi_peak']
    """
    store = PlanStore()
    plan_data = store.resolve_plan(plan_name)
    requirements = PlanRequirements.from_plan_data(plan_data)

    return {
        "requires_contract_capacity": requirements.requires_contract_capacity,
        "requires_meter_spec": requirements.requires_meter_spec,
        "valid_basic_fee_labels": list(requirements.valid_basic_fee_labels),
        "uses_basic_fee_formula": requirements.uses_basic_fee_formula,
        "formula_type": requirements.formula_type,
        "contract_keys": sorted(requirements.contract_keys),
    }


__all__ = [
    "TaiwanCalendar",
    "CustomCalendar",
    "BillingCycleType",
    "TariffPlan",
    "TariffProfile",
    "PeriodType",
    "SeasonType",
    "TaiwanDayTypeStrategy",
    "TaiwanSeasonStrategy",
    "taiwan_calendar",
    "custom_calendar",
    "available_plans",
    "is_holiday",
    "period_at",
    "period_context",
    "period_codes",
    "pricing_context",
    "plan",
    "plan_details",
    "costs",
    "monthly_breakdown",
    "get_plan_requirements",
    "CalendarError",
    "InvalidUsageInput",
    "InvalidBasicFeeInput",
    "InvalidBillingInput",
    "MissingRequiredInput",
    "PartialPeriodWarning",
    "PowerKitError",
    "TariffError",
    "UncheckedPriceWarning",
    "UncheckedYearWarning",
    "UnknownPlanError",
    "WeekdayDayTypeStrategy",
    "build_day_schedule",
    "build_tariff_plan",
    "build_tariff_profile",
    "build_tariff_rate",
    "BillingInputs",
    "calculate_bill",
    "calculate_bill_breakdown",
    "PlanRequirements",
    "__version__",
]
