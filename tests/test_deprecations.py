"""Every entry removed in 0.4.0 warns, names what to write instead, and gives
the same answer as that."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

import taipower_tou as tou

PLAN = "residential_simple_2_tier"
DT = datetime(2026, 7, 15, 14, 0)
IDX = pd.date_range("2026-07-13", periods=96, freq="h")
USAGE = pd.Series(1.0, index=pd.date_range("2026-07-01", "2026-07-31 23:00", freq="h"))
READINGS = [1.5, 2.3, 1.8, 2.0, 1.6]
READINGS_BY_TIME: dict[str | date, float] = {
    "2026-07-15 09:00": 1.5,
    "2026-07-15 10:00": 2.0,
}


def _profile():
    return tou.plan(PLAN).profile


CASES = {
    "get_period": (
        lambda: tou.get_period(DT, _profile()),
        lambda: _profile().period_at(DT),
        "profile.period_at",
    ),
    "get_period index": (
        lambda: tou.get_period(IDX, _profile()),
        lambda: _profile().period_at(IDX),
        "profile.period_at",
    ),
    "get_context": (
        lambda: tou.get_context(DT, _profile()),
        lambda: _profile().period_context(DT),
        "profile.period_context",
    ),
    "get_context index": (
        lambda: tou.get_context(IDX, _profile()),
        lambda: _profile().period_context(IDX),
        "profile.period_context",
    ),
    "calculate_costs": (
        lambda: tou.calculate_costs(USAGE, tou.plan(PLAN)),
        lambda: tou.plan(PLAN).calculate_costs(USAGE),
        "plan.calculate_costs",
    ),
    "residential_simple_2_tier_plan": (
        lambda: tou.residential_simple_2_tier_plan().describe(),
        lambda: tou.plan("residential_simple_2_tier").describe(),
        'plan("residential_simple_2_tier")',
    ),
    "high_voltage_2_tier_plan": (
        lambda: tou.high_voltage_2_tier_plan().describe(),
        lambda: tou.plan("high_voltage_2_tier").describe(),
        'plan("high_voltage_2_tier")',
    ),
    "residential_non_tou_plan": (
        lambda: tou.residential_non_tou_plan().describe(),
        lambda: tou.plan("residential_non_tou").describe(),
        'plan("residential_non_tou")',
    ),
    "calculate_bill_simple": (
        lambda: tou.calculate_bill_simple(USAGE, PLAN),
        lambda: tou.calculate_bill(USAGE, PLAN),
        "calculate_bill(usage, plan_id)",
    ),
    "calculate_bill_from_list": (
        lambda: tou.calculate_bill_from_list(
            READINGS, PLAN, start="2026-07-15 09:00", freq="1h"
        ),
        lambda: tou.calculate_bill(
            pd.Series(
                READINGS,
                index=pd.date_range("2026-07-15 09:00", periods=5, freq="1h"),
            ),
            PLAN,
        ),
        "calculate_bill(pd.Series(usage",
    ),
    "calculate_bill_from_dict": (
        lambda: tou.calculate_bill_from_dict(READINGS_BY_TIME, PLAN),
        lambda: tou.calculate_bill(
            pd.Series(
                list(READINGS_BY_TIME.values()),
                index=pd.to_datetime(list(READINGS_BY_TIME)),
            ),
            PLAN,
        ),
        "calculate_bill(pd.Series(list(usage.values())",
    ),
}


def _same(a, b) -> None:
    if isinstance(a, pd.DataFrame):
        pd.testing.assert_frame_equal(a, b)
    elif isinstance(a, pd.Series):
        pd.testing.assert_series_equal(a, b)
    else:
        assert a == b


@pytest.mark.filterwarnings("ignore::taipower_tou.PartialPeriodWarning")
@pytest.mark.parametrize("name", sorted(CASES))
def test_old_entry_warns_and_matches_the_new_one(name: str) -> None:
    old, new, replacement = CASES[name]
    with pytest.warns(DeprecationWarning, match="removed in 0.4.0") as record:
        got = old()
    assert any(replacement in str(w.message) for w in record), [
        str(w.message) for w in record
    ]
    _same(got, new())


UNUSED_ARGS = {
    "plan": lambda kw: tou.plan(PLAN, **kw),
    "plan with a calendar": lambda kw: tou.plan(
        PLAN, calendar_instance=tou.taiwan_calendar(), **kw
    ),
    "period_context": lambda kw: tou.period_context(DT, PLAN, **kw),
    "costs": lambda kw: tou.costs(USAGE, PLAN, **kw),
    "calculate_bill": lambda kw: tou.calculate_bill(USAGE, PLAN, **kw),
    "calculate_bill with a calendar": lambda kw: tou.calculate_bill(
        USAGE, PLAN, calendar_instance=tou.taiwan_calendar(), **kw
    ),
    "is_holiday": lambda kw: tou.is_holiday(date(2026, 7, 12), **kw),
    "taiwan_calendar": lambda kw: tou.taiwan_calendar(**kw),
    "TaiwanCalendar": lambda kw: tou.TaiwanCalendar(**kw),
}


@pytest.mark.parametrize("arg", [{"cache_dir": "unused"}, {"api_timeout": 5}])
@pytest.mark.parametrize("name", sorted(UNUSED_ARGS))
def test_unused_calendar_args_warn(name: str, arg: dict) -> None:
    with pytest.warns(DeprecationWarning, match="cache_dir and api_timeout"):
        UNUSED_ARGS[name](arg)


@pytest.mark.parametrize("name", sorted(UNUSED_ARGS))
def test_kept_entries_do_not_warn(name: str) -> None:
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        UNUSED_ARGS[name]({})
