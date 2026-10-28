"""Factory for creating tariff plans from JSON data."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from functools import lru_cache
from typing import Any

from taipower_tou.calendar import TaiwanCalendar, taiwan_calendar
from taipower_tou.custom import (
    CustomCalendar,
    build_tariff_plan,
    build_tariff_profile,
    build_tariff_rate,
)
from taipower_tou.errors import UnknownPlanError
from taipower_tou.models import BillingCycleType
from taipower_tou.rates import TariffJSONLoader
from taipower_tou.tariff import TaiwanDayTypeStrategy, TaiwanSeasonStrategy

# The short names available_plans() gives. plans.json has the 電價表's full
# names, and resolve_plan matches both.
_PLAN_NAME_MAP: dict[str, str] = {
    "residential_non_tou": "表燈非時間電價",
    "lighting_non_business_tiered": "表燈非時間-住宅非營業",
    "lighting_business_tiered": "表燈非時間-營業用",
    "residential_simple_2_tier": "簡易型二段式",
    "residential_simple_3_tier": "簡易型三段式",
    "lighting_standard_2_tier": "標準型二段式",
    "lighting_standard_3_tier": "標準型三段式",
    "low_voltage_power": "低壓電力非時間",
    "low_voltage_2_tier": "低壓電力二段式",
    "low_voltage_three_stage": "低壓電力三段式",
    "low_voltage_ev": "低壓電動車",
    "high_voltage_2_tier": "高壓電力二段式",
    "high_voltage_three_stage": "高壓電力三段式",
    "high_voltage_batch": "高壓批次生產",
    "high_voltage_ev": "高壓電動車",
    "extra_high_voltage_2_tier": "特高壓電力二段式",
    "extra_high_voltage_three_stage": "特高壓電力三段式",
    "extra_high_voltage_batch": "特高壓批次生產",
}

# Names earlier READMEs gave these plans.
_PLAN_ALIASES: dict[str, str] = {
    "表燈非營業（累進）": "lighting_non_business_tiered",
    "表燈營業（累進）": "lighting_business_tiered",
    "表燈標準二段式": "lighting_standard_2_tier",
    "表燈標準三段式": "lighting_standard_3_tier",
    "低壓電動車充電": "low_voltage_ev",
    "高壓電動車充電": "high_voltage_ev",
}

# 0.1.0 copied the 二段式 plans under these names. The 電價表 has no 高壓 or
# 特高壓 非時間電價.
_REMOVED_PLANS: dict[str, str] = {
    "high_voltage_power": "high_voltage_2_tier",
    "高壓電力": "high_voltage_2_tier",
    "extra_high_voltage_power": "extra_high_voltage_2_tier",
    "特高壓電力": "extra_high_voltage_2_tier",
}


@dataclass
class PlanRequirements:
    """The inputs a plan's bill reads. get_plan_requirements describes each
    field."""

    requires_contract_capacity: bool
    requires_meter_spec: bool
    valid_basic_fee_labels: set[str]
    uses_basic_fee_formula: bool
    formula_type: str | None

    @classmethod
    def from_plan_data(cls, plan_data: dict[str, Any]) -> PlanRequirements:
        category = plan_data.get("category", "")
        basic_fees = plan_data.get("basic_fees", [])
        rules = plan_data.get("billing_rules", {})
        requires_contract_capacity = category in (
            "high_voltage",
            "extra_high_voltage",
        )
        requires_meter_spec = "minimum_usage_rules_ref" in rules
        valid_basic_fee_labels = {
            fee.get("label", "") for fee in basic_fees if fee.get("label")
        }
        uses_basic_fee_formula = "basic_fee_formula" in rules
        formula_type = rules.get("basic_fee_formula", {}).get("type")

        return cls(
            requires_contract_capacity=requires_contract_capacity,
            requires_meter_spec=requires_meter_spec,
            valid_basic_fee_labels=valid_basic_fee_labels,
            uses_basic_fee_formula=uses_basic_fee_formula,
            formula_type=formula_type,
        )


class PlanStore:
    """The plans in the bundled plans.json, loaded once per store."""

    def __init__(self, filename: str = "plans.json") -> None:
        self._loader = TariffJSONLoader(filename=filename)
        self._data: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._data is None:
            self._data = self._loader.load()
        return self._data

    def definitions(self) -> dict[str, Any]:
        return self._load().get("definitions", {})

    def price_dates(self) -> tuple[date, date]:
        """First and last day the bundled prices cover.

        The last day is how far Taipower's 電價費率審議會 has decided prices.
        """
        dates = self._load()["price_dates"]
        return (
            date.fromisoformat(dates["effective_from"]),
            date.fromisoformat(dates["decided_through"]),
        )

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        for plan in self._load().get("plans", []):
            if plan.get("id") == plan_id:
                return plan
        raise UnknownPlanError(f"Plan not found: {plan_id}")

    def resolve_plan(self, plan_id: str) -> dict[str, Any]:
        """Return a copy of the data of the plan that plan_id names.

        An ID, a name from available_plans() or plans.json, or a name earlier
        READMEs used matches exactly, ignoring case and surrounding spaces.
        Otherwise a plan matches when its ID or name is the only one that
        contains plan_id. "批次" is in two plans' names and matches neither.

        Raises:
            UnknownPlanError: No plan or more than one matches, the plan was
                removed, or plan_id is not a string.
        """
        if not isinstance(plan_id, str):
            raise UnknownPlanError(
                f"A plan is named by a string, not {plan_id!r}. "
                "Use available_plans() to list all valid plan IDs."
            )
        query = plan_id.strip()
        key = query.lower()
        plans = {plan["id"]: plan for plan in self._load().get("plans", [])}
        exact = {pid.lower(): pid for pid in plans}
        exact.update({plan["name"].lower(): pid for pid, plan in plans.items()})
        exact.update({name.lower(): pid for pid, name in _PLAN_NAME_MAP.items()})
        exact.update({name.lower(): pid for name, pid in _PLAN_ALIASES.items()})
        if key in exact:
            return dict(plans[exact[key]])

        replacement = _REMOVED_PLANS.get(key)
        if replacement:
            raise UnknownPlanError(
                f"Plan {query} was removed in 0.2.0: the 電價表 has no 高壓 or "
                f"特高壓 非時間電價. It billed exactly as {replacement}; use that."
            )

        matches = [
            pid
            for pid, plan in plans.items()
            if key and (key in pid or key in plan["name"].lower())
        ]
        if len(matches) == 1:
            return dict(plans[matches[0]])
        if matches:
            raise UnknownPlanError(
                f"Ambiguous plan name '{query}'. "
                f"Multiple matches: {', '.join(matches)}. "
                f"Please use the exact plan ID."
            )
        raise UnknownPlanError(
            f"Plan not found: {query}. "
            f"Use available_plans() to list all valid plan IDs."
        )

    @lru_cache(maxsize=1)
    def list_plan_ids(self) -> tuple[str, ...]:
        """Return tuple of all available plan IDs."""
        plans = self._load().get("plans", [])
        return tuple(p.get("id", "") for p in plans if p.get("id"))


class TariffFactory:
    """Factory for creating TariffPlan instances from JSON data."""

    def __init__(
        self,
        calendar: TaiwanCalendar | CustomCalendar | None = None,
        store: PlanStore | None = None,
    ) -> None:
        self._calendar = calendar or taiwan_calendar()
        self._store = store or PlanStore()

    def create_plan(
        self,
        plan_id: str,
        billing_cycle_type: BillingCycleType = BillingCycleType.MONTHLY,
    ) -> Any:
        """Create a TariffPlan from the given plan_id.

        Args:
            plan_id: An ID or name, matched as PlanStore.resolve_plan matches.
            billing_cycle_type: How a tiered plan pairs months.

        Raises:
            UnknownPlanError: No plan or more than one matches plan_id, or the
                plan was removed.
        """
        plan_data = self._store.resolve_plan(plan_id)
        # 高壓電動車 pays bill_ratio of the 低壓 bill. calculate_bill takes the
        # ratio off the rounded bill. A plan from here prices each kWh at that
        # share of its 低壓 price.
        ratio = plan_data.get("billing_rules", {}).get("bill_ratio")
        if ratio is not None:
            plan_data["rates"] = [
                {**rate, "cost": rate["cost"] * ratio} for rate in plan_data["rates"]
            ]
        return _build_tariff_plan_from_data(
            plan_data,
            self._store,
            self._calendar,
            billing_cycle_type=billing_cycle_type,
        )

    @classmethod
    def create(
        cls,
        plan_id: str,
        calendar: TaiwanCalendar | CustomCalendar | None = None,
        billing_cycle_type: BillingCycleType = BillingCycleType.MONTHLY,
    ) -> Any:
        """Convenience method to create a plan without instantiating factory."""
        return cls(calendar).create_plan(plan_id, billing_cycle_type)

    def list_plans(self) -> tuple[str, ...]:
        """Return all available plan IDs."""
        return self._store.list_plan_ids()


def _season_strategy(
    plan_data: dict[str, Any], store: PlanStore
) -> TaiwanSeasonStrategy:
    strategy_name = plan_data.get("season_strategy", "seasons")
    definitions = store.definitions()
    seasons = definitions.get(strategy_name, [])
    if not seasons:
        return TaiwanSeasonStrategy((6, 1), (9, 30))
    summer = next((s for s in seasons if s.get("name") == "summer"), seasons[0])
    start_month, start_day = map(int, summer["start"].split("-"))
    end_month, end_day = map(int, summer["end"].split("-"))
    return TaiwanSeasonStrategy((start_month, start_day), (end_month, end_day))


def _normalize_schedules(schedules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """plans.json's slots grouped by season and day type."""
    if not schedules:
        return []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in schedules:
        season = item["season"]
        day_type = item["day_type"]
        grouped.setdefault((season, day_type), []).append(
            {"start": item["start"], "end": item["end"], "period": item["period"]}
        )
    normalized = []
    for (season, day_type), slots in grouped.items():
        normalized.append({"season": season, "day_type": day_type, "slots": slots})
    return normalized


def _normalize_tiers(tiers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """plans.json's tiers as ConsumptionTier fields. The open top tier ends at
    999999 kWh, which tiered_energy_cost reads as no limit."""
    if not tiers:
        return []

    normalized = []
    for item in tiers:
        start_kwh = float(item["min"])
        max_val = item.get("max")
        end_kwh = 999999.0 if max_val is None else float(max_val)

        normalized.append(
            {
                "start_kwh": start_kwh,
                "end_kwh": end_kwh,
                "summer_cost": item["summer"],
                "non_summer_cost": item["non_summer"],
            }
        )
    return normalized


def _build_tariff_plan_from_data(
    plan_data: dict[str, Any],
    store: PlanStore,
    calendar: TaiwanCalendar | CustomCalendar,
    billing_cycle_type: BillingCycleType = BillingCycleType.MONTHLY,
) -> Any:
    """The TariffPlan of a plans.json entry, at the prices it lists."""
    season_strategy = _season_strategy(plan_data, store)
    day_type_strategy = TaiwanDayTypeStrategy(calendar)

    # A plan without schedules has one period all day, such as the flat
    # period of low_voltage_power's 非時間電價.
    rate_periods = {item["period"] for item in plan_data.get("rates", [])}
    default_period = rate_periods.pop() if len(rate_periods) == 1 else "off_peak"
    schedules = _normalize_schedules(plan_data.get("schedules", []))
    if not schedules:
        schedules = [
            {
                "season": "summer",
                "day_type": "weekday",
                "slots": [{"start": "00:00", "end": "24:00", "period": default_period}],
            }
        ]

    profile = build_tariff_profile(
        name=plan_data.get("name", plan_data.get("id", "Plan")),
        season_strategy=season_strategy,
        day_type_strategy=day_type_strategy,
        schedules=schedules,
        default_period=default_period,
    )

    rates = plan_data.get("rates", [])
    tiered = _normalize_tiers(plan_data.get("tiers", []))

    rate = build_tariff_rate(
        period_costs=rates if rates else None,
        tiered_rates=tiered if tiered else None,
        season_strategy=season_strategy,
    )
    rate = replace(rate, price_dates=store.price_dates())
    return build_tariff_plan(profile, rate, billing_cycle_type)
