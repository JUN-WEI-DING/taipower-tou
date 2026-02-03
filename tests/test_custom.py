from datetime import date, datetime

import pandas as pd

from taipower_tou.custom import (
    CustomCalendar,
    WeekdayDayTypeStrategy,
    build_tariff_plan,
    build_tariff_profile,
    build_tariff_rate,
)
from taipower_tou.tariff import TaiwanSeasonStrategy, get_period


def test_custom_calendar_weekend_and_holiday() -> None:
    calendar = CustomCalendar(holidays=[date(2025, 1, 2)], weekend_days=[5, 6])

    assert calendar.is_holiday(date(2025, 1, 2))
    assert calendar.is_holiday(date(2025, 1, 4))

    index = pd.DatetimeIndex([datetime(2025, 1, 3), datetime(2025, 1, 4)])
    result = calendar.is_holiday(index)
    assert list(result) == [False, True]


def test_custom_plan_with_custom_period_label() -> None:
    calendar = CustomCalendar()
    day_type_strategy = WeekdayDayTypeStrategy(calendar)
    season_strategy = TaiwanSeasonStrategy((6, 1), (9, 30))

    schedules = [
        {
            "season": "summer",
            "day_type": "weekday",
            "slots": [
                {"start": "00:00", "end": "12:00", "period": "off_peak"},
                {"start": "12:00", "end": "18:00", "period": "super_peak"},
                {"start": "18:00", "end": "00:00", "period": "off_peak"},
            ],
        }
    ]

    profile = build_tariff_profile(
        name="Custom-Plan",
        season_strategy=season_strategy,
        day_type_strategy=day_type_strategy,
        schedules=schedules,
    )

    rate = build_tariff_rate(
        period_costs=[
            {"season": "summer", "period": "off_peak", "cost": 1.0},
            {"season": "summer", "period": "super_peak", "cost": 5.0},
        ],
        season_strategy=season_strategy,
    )
    plan = build_tariff_plan(profile, rate)

    dt = datetime(2025, 7, 1, 13, 0)
    assert get_period(dt, plan.profile) == "super_peak"

    context = plan.pricing_context(dt)
    assert context["period"] == "super_peak"
