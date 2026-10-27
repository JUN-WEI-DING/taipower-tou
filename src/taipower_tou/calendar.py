"""Taipower off-peak day (離峰日) calendar computed from the tariff rule."""

from __future__ import annotations

import csv
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import cache, singledispatchmethod
from importlib.resources import files
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError:
    pd = None

from taipower_tou.errors import CalendarError


@dataclass(frozen=True)
class _Festivals:
    spring_festival: date
    dragon_boat: date
    mid_autumn: date
    qingming: date


@dataclass(frozen=True)
class _OffPeakRule:
    """One version of the 離峰日 list in Taipower's 電價表."""

    effective_from: date
    fixed_days: tuple[tuple[int, int], ...]
    spring_festival_offsets: range

    def listed_days(self, year: int, festivals: _Festivals) -> set[date]:
        days = {date(year, month, day) for month, day in self.fixed_days}
        days.update(
            festivals.spring_festival + timedelta(days=offset)
            for offset in self.spring_festival_offsets
        )
        days.update((festivals.qingming, festivals.dragon_boat, festivals.mid_autumn))
        return days


# The 電價表 off-peak list is unchanged from the 102/10/1 table through mid-2025.
# The 114/9/1 revision added 除夕前1日, 9/28, 10/25 and 12/25 without
# backdating: the revised 114年 calendar (114/8/26修) marks 2025-10-25 and
# 2025-12-25 off-peak but keeps 2025-01-27 a weekday.
_RULES = (
    _OffPeakRule(
        effective_from=date(2014, 1, 1),
        fixed_days=((1, 1), (2, 28), (4, 4), (5, 1), (10, 10)),
        spring_festival_offsets=range(-1, 5),
    ),
    _OffPeakRule(
        effective_from=date(2025, 9, 1),
        fixed_days=(
            (1, 1),
            (2, 28),
            (4, 4),
            (5, 1),
            (9, 28),
            (10, 10),
            (10, 25),
            (12, 25),
        ),
        spring_festival_offsets=range(-2, 5),
    ),
)


@cache
def _festival_table() -> dict[int, _Festivals]:
    text = files("taipower_tou.data").joinpath("festival_dates.csv").read_text("utf-8")
    return {
        int(row["year"]): _Festivals(
            spring_festival=date.fromisoformat(row["spring_festival"]),
            dragon_boat=date.fromisoformat(row["dragon_boat"]),
            mid_autumn=date.fromisoformat(row["mid_autumn"]),
            qingming=date.fromisoformat(row["qingming"]),
        )
        for row in csv.DictReader(text.splitlines())
    }


def _rule_for(day: date) -> _OffPeakRule:
    return next(rule for rule in reversed(_RULES) if rule.effective_from <= day)


@cache
def _listed_offpeak_days(year: int) -> frozenset[date]:
    first_year = _RULES[0].effective_from.year
    last_year = max(_festival_table())
    if not first_year <= year <= last_year:
        raise CalendarError(
            f"Taipower off-peak days are defined for {first_year}-{last_year}, "
            f"not {year}. Pass calendar_instance=custom_calendar(...) for other "
            "years."
        )
    festivals = _festival_table()[year]
    return frozenset(
        day
        for rule in _RULES
        for day in rule.listed_days(year, festivals)
        if _rule_for(day) is rule
    )


class TaiwanCalendar:
    """Taipower 離峰日: Sundays plus the days listed in the 電價表.

    補假 and other office-calendar adjustments are not 離峰日, and a listed day
    that falls on a Saturday is still one.
    """

    def __init__(
        self, cache_dir: Path | None = None, api_timeout: int | None = None
    ) -> None:
        if cache_dir is not None or api_timeout is not None:
            warnings.warn(
                "cache_dir and api_timeout have no effect: off-peak days are "
                "computed from Taipower's rule without network access. They will "
                "be removed in a future release.",
                DeprecationWarning,
                stacklevel=2,
            )

    def preload_years(self, years: set[int]) -> None:
        """Validate and compute off-peak days for several years up front."""
        for year in years:
            _listed_offpeak_days(year)

    @singledispatchmethod
    def is_holiday(self, target: object) -> Any:
        raise CalendarError(f"Unsupported type: {type(target)}")

    @is_holiday.register
    def _(self, target: date) -> bool:
        listed = _listed_offpeak_days(target.year)
        return target.weekday() == 6 or target in listed

    @is_holiday.register
    def _(self, target: datetime) -> bool:
        return self.is_holiday(target.date())

    if pd is not None:

        @is_holiday.register
        def _(self, target: pd.DatetimeIndex) -> pd.Series:
            listed: set[date] = set()
            for year in target.year.unique():
                listed.update(_listed_offpeak_days(int(year)))
            is_listed = target.normalize().isin(pd.DatetimeIndex(sorted(listed)))
            is_sunday = target.dayofweek == 6
            return pd.Series(is_sunday | is_listed, index=target, name="is_holiday")


def taiwan_calendar(
    cache_dir: Path | None = None, api_timeout: int | None = None
) -> TaiwanCalendar:
    return TaiwanCalendar(cache_dir=cache_dir, api_timeout=api_timeout)
