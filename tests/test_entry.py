import warnings
from datetime import date, datetime, time

import pandas as pd
import pytest

import taipower_tou as tou
from taipower_tou.calendar import TaiwanCalendar
from taipower_tou.errors import InvalidUsageInput, PowerKitError, TariffError
from taipower_tou.tariff import (
    DaySchedule,
    PeriodType,
    SeasonType,
    TaiwanDayTypeStrategy,
    TaiwanSeasonStrategy,
    TariffPlan,
    TariffProfile,
    TariffRate,
    TimeSlot,
)


class FixedCalendar:
    def is_holiday(self, target: object) -> object:
        if isinstance(target, pd.DatetimeIndex):
            return pd.Series(False, index=target)
        return False


def _build_profile() -> TariffProfile:
    schedule = DaySchedule(
        slots=[
            TimeSlot(
                start=time(0, 0), end=time(12, 0), period_type=PeriodType.OFF_PEAK
            ),
            TimeSlot(start=time(12, 0), end=time(18, 0), period_type=PeriodType.PEAK),
            TimeSlot(
                start=time(18, 0), end=time(0, 0), period_type=PeriodType.OFF_PEAK
            ),
        ]
    )
    schedules = {
        (season, day_type): schedule
        for season in SeasonType
        for day_type in ("weekday", "saturday", "sunday_holiday")
    }
    return TariffProfile(
        name="Test",
        season_strategy=TaiwanSeasonStrategy((6, 1), (9, 30)),
        day_type_strategy=TaiwanDayTypeStrategy(FixedCalendar()),
        schedules=schedules,
    )


def test_entry_calendar_and_tariffs() -> None:
    calendar = TaiwanCalendar()
    assert calendar.is_holiday(date(2024, 1, 1))
    assert tou.is_holiday(date(2024, 1, 1), calendar=calendar)

    helper_calendar = tou.taiwan_calendar()
    assert helper_calendar.is_holiday(date(2024, 1, 1))

    named_plan = tou.plan("residential_simple_2_tier", calendar_instance=calendar)
    assert isinstance(named_plan, TariffPlan)


def test_entry_get_period_and_calculate_costs() -> None:
    profile = _build_profile()
    rate = TariffRate(
        period_costs={
            (SeasonType.SUMMER, PeriodType.OFF_PEAK): 1.0,
            (SeasonType.SUMMER, PeriodType.PEAK): 3.0,
        }
    )
    plan = TariffPlan(profile, rate)

    assert profile.period_at(datetime(2024, 7, 1, 13, 0)) == PeriodType.PEAK
    assert plan.period_at(datetime(2024, 7, 1, 13, 0)) == PeriodType.PEAK

    usage = pd.Series(
        [1.5, 2.0],
        index=pd.DatetimeIndex(["2024-07-01 11:00", "2024-07-01 13:00"]),
    )
    costs = plan.calculate_costs(usage)
    assert list(costs.values) == [7.5]


def test_calculate_costs_rejects_infinite_usage() -> None:
    profile = _build_profile()
    rate = TariffRate(
        period_costs={
            (SeasonType.SUMMER, PeriodType.OFF_PEAK): 1.0,
            (SeasonType.SUMMER, PeriodType.PEAK): 3.0,
        }
    )
    plan = TariffPlan(profile, rate)
    usage = pd.Series(
        [1.0, float("inf")],
        index=pd.DatetimeIndex(["2024-07-01 11:00", "2024-07-01 13:00"]),
    )
    with pytest.raises(InvalidUsageInput):
        plan.calculate_costs(usage)


def test_entry_named_helpers() -> None:
    assert "high_voltage_2_tier" in list(tou.available_plans().keys())
    assert len(list(tou.available_plans().keys())) > 0  # Bilingual names
    assert tou.period_at(
        datetime(2025, 7, 15, 10, 0),
        "residential_simple_2_tier",
    ) in {PeriodType.PEAK, PeriodType.OFF_PEAK, PeriodType.SEMI_PEAK}

    usage = pd.Series(
        [1.0, 2.0],
        index=pd.to_datetime(["2025-07-15 09:00", "2025-07-15 10:00"]),
    )
    costs = tou.costs(usage, "high_voltage_2_tier")
    assert (costs >= 0).all()


def test_errors_exports() -> None:
    assert issubclass(InvalidUsageInput, PowerKitError)
    assert issubclass(TariffError, PowerKitError)


def test_get_plan_requirements_supports_chinese_name() -> None:
    req = tou.get_plan_requirements("簡易型二段式")
    assert "requires_contract_capacity" in req
    assert "valid_basic_fee_labels" in req


@pytest.mark.parametrize("plan_id", sorted(tou.available_plans()))
def test_contract_keys_are_what_the_bill_takes(plan_id: str) -> None:
    """A bill takes each of contract_keys without a warning and warns of a
    key outside them."""
    keys = tou.get_plan_requirements(plan_id)["contract_keys"]
    usage = pd.Series(
        1.0, index=pd.date_range("2026-07-01", "2026-08-31 23:00", freq="h")
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        tou.calculate_bill(
            usage,
            plan_id,
            tou.BillingInputs(
                contract_capacities=dict.fromkeys(keys, 100.0),
                meter_phase="single",
                meter_voltage_v=110,
                meter_ampere=30,
            ),
        )
    with pytest.warns(UserWarning, match="bills no"):
        tou.calculate_bill(
            usage,
            plan_id,
            tou.BillingInputs(
                contract_capacities={**dict.fromkeys(keys, 100.0), "unknown": 1.0},
                meter_phase="single",
                meter_voltage_v=110,
                meter_ampere=30,
            ),
        )
