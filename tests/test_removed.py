"""What 0.4.0 removed is gone, so old code fails where it calls it instead of
running with a changed meaning. CHANGELOG 0.4.0 says what to write instead."""

from typing import Any

import pandas as pd
import pytest

import taipower_tou as tou

REMOVED = [
    "get_period",
    "get_context",
    "calculate_costs",
    "residential_simple_2_tier_plan",
    "high_voltage_2_tier_plan",
    "residential_non_tou_plan",
    "calculate_bill_simple",
    "calculate_bill_from_list",
    "calculate_bill_from_dict",
]
USAGE = pd.Series(1.0, index=pd.date_range("2026-07-01", "2026-07-31 23:00", freq="h"))
PLAN = "residential_simple_2_tier"


@pytest.mark.parametrize("name", REMOVED)
def test_removed_name_is_gone(name: str) -> None:
    assert not hasattr(tou, name)
    assert name not in tou.__all__


@pytest.mark.parametrize("module", ["tariff", "billing"])
def test_removed_names_are_gone_from_modules(module: str) -> None:
    import importlib

    mod = importlib.import_module(f"taipower_tou.{module}")
    assert not [name for name in REMOVED if hasattr(mod, name)]


@pytest.mark.parametrize("arg", ["cache_dir", "api_timeout"])
@pytest.mark.parametrize(
    "call",
    [
        lambda kw: tou.plan(PLAN, **kw),
        lambda kw: tou.period_context(pd.Timestamp("2026-07-01"), PLAN, **kw),
        lambda kw: tou.costs(USAGE, PLAN, **kw),
        lambda kw: tou.calculate_bill(USAGE, PLAN, **kw),
        lambda kw: tou.is_holiday(pd.Timestamp("2026-07-12"), **kw),
        lambda kw: tou.taiwan_calendar(**kw),
        lambda kw: tou.TaiwanCalendar(**kw),
    ],
    ids=[
        "plan",
        "period_context",
        "costs",
        "calculate_bill",
        "is_holiday",
        "taiwan_calendar",
        "TaiwanCalendar",
    ],
)
def test_calendar_download_args_are_gone(call, arg: str) -> None:
    with pytest.raises(TypeError):
        call({arg: None})


def test_old_positional_args_do_not_shift_into_new_ones() -> None:
    """0.3.0's calculate_bill(usage, plan, inputs, calendar, cache_dir) must
    not pass cache_dir as strict, nor plan(name, calendar, cache_dir) pass it
    as billing_cycle_type."""
    calculate_bill: Any = tou.calculate_bill
    plan: Any = tou.plan
    monthly_breakdown: Any = tou.monthly_breakdown
    with pytest.raises(TypeError):
        calculate_bill(USAGE, PLAN, None, None, "cache")
    with pytest.raises(TypeError):
        plan(PLAN, None, "cache")
    with pytest.raises(TypeError):
        monthly_breakdown(USAGE, PLAN, False, None, "cache")
