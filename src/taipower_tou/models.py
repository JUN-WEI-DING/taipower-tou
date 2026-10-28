"""Shared data structures for the TOU calculator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum
from typing import Any


class SeasonType(Enum):
    SUMMER = "summer"
    NON_SUMMER = "non_summer"


class PeriodType(Enum):
    PEAK = "peak"
    SEMI_PEAK = "semi_peak"
    OFF_PEAK = "off_peak"


class BillingCycleType(Enum):
    """累進費率方案的抄表週期，決定 TariffPlan.calculate_costs 與
    monthly_breakdown 把哪兩個月算成一期。臺電對一般住宅及小商店隔月抄表收費。

    - MONTHLY: 每月一期（預設）
    - ODD_MONTH: 奇數月抄表，(12,1)->1, (2,3)->3, (4,5)->5, (6,7)->7,
      (8,9)->9, (10,11)->11
    - EVEN_MONTH: 偶數月抄表，(1,2)->2, (3,4)->4, (5,6)->6, (7,8)->8,
      (9,10)->10, (11,12)->12

    每期以抄表月命名。calculate_bill 不用這個設定，它從用電資料的第一個月起，
    每 BillingInputs.billing_cycle_months 個月切一張帳單。
    """

    MONTHLY = "monthly"
    ODD_MONTH = "odd_month"
    EVEN_MONTH = "even_month"


@dataclass(frozen=True)
class TimeSlot:
    start: time
    end: time
    period_type: PeriodType | str


@dataclass(frozen=True)
class ConsumptionTier:
    start_kwh: float
    end_kwh: float
    summer_cost: float
    non_summer_cost: float


@dataclass(frozen=True)
class DaySchedule:
    slots: list[TimeSlot]


@dataclass
class TariffRate:
    period_costs: dict[tuple[SeasonType | str, PeriodType | str], float] = field(
        default_factory=dict
    )
    tiered_rates: list[ConsumptionTier] = field(default_factory=list)
    # Prices listed per day type, keyed by season, period and day type labels.
    # A three-stage plan's weekday and Saturday 半尖峰 differ, so these take
    # precedence over period_costs.
    day_type_costs: dict[tuple[str, str, str], float] = field(default_factory=dict)
    # The first and last day Taipower's bundled prices cover, or None for
    # prices the caller supplies.
    price_dates: tuple[date, date] | None = None

    def rate_structure(self) -> str:
        has_periods = bool(self.period_costs)
        has_tiers = bool(self.tiered_rates)
        if has_periods and has_tiers:
            return "mixed"
        if has_tiers:
            return "tiered"
        if has_periods:
            return "tou"
        return "unknown"

    def get_cost(
        self,
        season: SeasonType | str,
        period: PeriodType | str,
        day_type: Any = None,
    ) -> float:
        if day_type is not None:
            key = (_label_value(season), _label_value(period), _label_value(day_type))
            if key in self.day_type_costs:
                return self.day_type_costs[key]
        if (season, period) in self.period_costs:
            return self.period_costs[(season, period)]
        season_key = _label_value(season)
        period_key = _label_value(period)
        return self.period_costs.get((season_key, period_key), 0.0)

    def describe(self) -> dict[str, Any]:
        period_costs = [
            {
                "season": _label_value(season),
                "period": _label_value(period),
                "cost": cost,
            }
            for (season, period), cost in sorted(
                self.period_costs.items(),
                key=lambda item: (_label_value(item[0][0]), _label_value(item[0][1])),
            )
        ]
        tiered_rates = [
            {
                "start_kwh": tier.start_kwh,
                "end_kwh": tier.end_kwh,
                "summer_cost": tier.summer_cost,
                "non_summer_cost": tier.non_summer_cost,
            }
            for tier in self.tiered_rates
        ]
        return {
            "rate_structure": self.rate_structure(),
            "period_costs": period_costs,
            "tiered_rates": tiered_rates,
        }


def _label_value(value: Any) -> str:
    if isinstance(value, Enum):
        return value.value
    return str(value)
