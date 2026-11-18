"""period_codes and the DatetimeIndex path of period_context agree with the
per-datetime path, on every plan and on indexes of every shape."""

from datetime import date

import pandas as pd
import pytest

import taipower_tou as tou
from taipower_tou.custom import (
    CustomCalendar,
    WeekdayDayTypeStrategy,
    build_tariff_profile,
)
from taipower_tou.models import _label_value
from taipower_tou.tariff import SeasonType, TaiwanSeasonStrategy, get_context

INDEXES = {
    "15 minutes, 2025": pd.date_range(
        "2025-01-01", "2026-01-01", freq="15min", inclusive="left"
    ),
    "UTC, across new year": pd.date_range(
        "2025-12-31 12:00", "2026-01-01 20:00", freq="5min", tz="UTC"
    ),
    "unordered 7 minutes": pd.date_range("2026-05-29 03:01", periods=3000, freq="7min")[
        ::-1
    ],
}
SAMPLE = 300


def _scalar_context(index: pd.DatetimeIndex, profile) -> pd.DataFrame:
    rows = [get_context(ts.to_pydatetime(), profile) for ts in index]
    return pd.DataFrame(rows, index=index)


@pytest.mark.parametrize("plan_id", sorted(tou.available_plans()))
@pytest.mark.parametrize("name", sorted(INDEXES))
def test_index_paths_match_the_datetime_path(plan_id: str, name: str) -> None:
    index = INDEXES[name]
    profile = tou.plan(plan_id).profile
    context = tou.period_context(index, plan_id)
    codes = tou.period_codes(index, plan_id)

    assert list(context.columns) == ["season", "day_type", "period"]
    assert list(codes.columns) == ["season", "day_type", "period"]
    assert codes.index.equals(index)

    step = max(1, len(index) // SAMPLE)
    sample = index[::step]
    expected = _scalar_context(sample, profile)
    pd.testing.assert_frame_equal(context.loc[sample], expected)
    for column in expected:
        assert codes.loc[sample, column].cat.codes.min() >= 0
        named = codes.loc[sample, column].astype(str).tolist()
        assert named == [_label_value(v) for v in expected[column]]


def test_period_names_are_unique_per_plan() -> None:
    """A plan's default "off_peak" and PeriodType.OFF_PEAK are one category."""
    codes = tou.period_codes(INDEXES["15 minutes, 2025"], "high_voltage_three_stage")
    assert sorted(codes["period"].cat.categories) == ["off_peak", "peak", "semi_peak"]
    assert codes["day_type"].cat.categories.tolist() == [
        "weekday",
        "saturday",
        "sunday_holiday",
    ]


def test_day_type_strategy_without_a_batch_method() -> None:
    calendar = CustomCalendar(holidays=[date(2025, 7, 2)])
    profile = build_tariff_profile(
        name="custom",
        season_strategy=TaiwanSeasonStrategy((6, 1), (9, 30)),
        day_type_strategy=WeekdayDayTypeStrategy(calendar),
        schedules=[
            {
                "season": "summer",
                "day_type": "weekday",
                "slots": [
                    {"start": "00:00", "end": "12:00", "period": "off_peak"},
                    {"start": "12:00", "end": "00:00", "period": "super_peak"},
                ],
            }
        ],
    )
    assert not hasattr(profile.day_type_strategy, "get_day_types_batch")
    index = pd.date_range("2025-06-28", "2025-07-04", freq="h")
    pd.testing.assert_frame_equal(
        profile.evaluate(index), _scalar_context(index, profile)
    )
    codes = profile.engine.codes(index)
    assert "super_peak" in codes["period"].cat.categories


def test_empty_index_gives_empty_columns() -> None:
    """0.2.0 raised TypeError on an empty index."""
    empty = pd.DatetimeIndex([])
    context = tou.period_context(empty, "high_voltage_three_stage")
    codes = tou.period_codes(empty, "high_voltage_three_stage")
    assert (
        list(context.columns)
        == list(codes.columns)
        == [
            "season",
            "day_type",
            "period",
        ]
    )
    assert len(context) == len(codes) == 0


def test_nat_raises() -> None:
    index = pd.DatetimeIndex(["2025-07-01 10:00", None])
    with pytest.raises(ValueError, match="NaT"):
        tou.period_context(index, "high_voltage_three_stage")
    with pytest.raises(ValueError, match="NaT"):
        tou.period_codes(index, "high_voltage_three_stage")


def test_period_codes_takes_only_an_index() -> None:
    with pytest.raises(TypeError):
        tou.period_codes(
            pd.Timestamp("2025-07-01").to_pydatetime(), "high_voltage_three_stage"
        )


@pytest.mark.parametrize("plan_id", sorted(tou.available_plans()))
def test_one_object_per_period_name(plan_id: str) -> None:
    """0.2.0 gave a tiered plan's off_peak as PeriodType.OFF_PEAK on summer
    weekdays and as the string "off_peak" on other days."""
    context = tou.period_context(INDEXES["15 minutes, 2025"], plan_id)
    for column in context:
        objects = {(type(v), v) for v in context[column].unique()}
        names = [_label_value(v) for _, v in objects]
        assert len(names) == len(set(names)), (column, objects)


def test_index_paths_decide_by_day_not_by_timestamp(monkeypatch) -> None:
    """0.2.0 hashed a SeasonType once per timestamp, which made a year of
    15-minute timestamps take 11 ms. Deciding by day hashes it about once a
    day."""
    calls = 0
    enum_hash = SeasonType.__hash__

    def counting_hash(self: SeasonType) -> int:
        nonlocal calls
        calls += 1
        return enum_hash(self)

    index = INDEXES["15 minutes, 2025"]
    profile = tou.plan("high_voltage_three_stage").profile
    profile.evaluate(index[:96])  # build the engine outside the count
    monkeypatch.setattr(SeasonType, "__hash__", counting_hash)
    for read in (profile.evaluate, profile.engine.codes):
        calls = 0
        read(index)
        assert calls < len(index) // 20, (read.__name__, calls)
