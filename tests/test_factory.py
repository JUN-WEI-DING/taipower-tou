"""Parameterized tests for all tariff plans in plans.json."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

import taipower_tou as tou
from taipower_tou.factory import TariffFactory


class TestAllPlans:
    """Parameterized tests to verify all plans can be loaded and evaluated."""

    @pytest.fixture
    def sample_usage(self) -> pd.Series:
        """Create sample usage data for testing."""
        return pd.Series(
            [1.0] * 48,
            index=pd.date_range("2024-07-15", periods=48, freq="30min"),
        )

    def test_available_plans_not_empty(self) -> None:
        """Verify that plans are available."""
        plans = list(tou.available_plans().keys())
        assert len(plans) > 0
        assert isinstance(plans, (list, tuple))

    @pytest.mark.parametrize("plan_id", list(tou.available_plans().keys()))
    def test_plan_can_be_loaded(self, plan_id: str) -> None:
        """Test that each plan can be loaded without errors."""

        plan = tou.plan(plan_id)
        assert plan is not None
        assert plan.profile is not None
        assert plan.rates is not None

    @pytest.mark.parametrize("plan_id", list(tou.available_plans().keys()))
    def test_plan_has_valid_profile(self, plan_id: str) -> None:
        """Test that each plan has a valid profile structure."""

        plan = tou.plan(plan_id)
        profile = plan.profile

        assert profile.name is not None
        assert len(profile.name) > 0

        # Check that profile can describe itself
        description = profile.describe()
        assert "name" in description
        assert "seasons" in description
        assert "day_types" in description
        assert "schedules" in description

    @pytest.mark.parametrize("plan_id", list(tou.available_plans().keys()))
    def test_plan_evaluate_context(self, plan_id: str) -> None:
        """Test that each plan can evaluate context for a datetime index."""

        plan = tou.plan(plan_id)
        index = pd.date_range("2024-07-15", periods=24, freq="1h")

        context = plan.profile.evaluate(index)
        assert isinstance(context, pd.DataFrame)
        assert "season" in context.columns
        assert "day_type" in context.columns
        assert "period" in context.columns
        assert len(context) == 24

    @pytest.mark.parametrize("plan_id", list(tou.available_plans().keys()))
    def test_plan_calculate_costs(self, plan_id: str, sample_usage: pd.Series) -> None:
        """Test that each plan can calculate costs for sample usage."""

        plan = tou.plan(plan_id)
        costs = plan.calculate_costs(sample_usage)

        assert isinstance(costs, pd.Series)
        assert (costs >= 0).all()  # All costs should be non-negative

    @pytest.mark.parametrize("plan_id", list(tou.available_plans().keys()))
    def test_plan_monthly_breakdown(
        self, plan_id: str, sample_usage: pd.Series
    ) -> None:
        """Test that each plan can provide monthly breakdown."""

        plan = tou.plan(plan_id)
        breakdown = plan.monthly_breakdown(sample_usage)

        assert isinstance(breakdown, pd.DataFrame)
        assert "month" in breakdown.columns
        assert "season" in breakdown.columns
        assert "usage_kwh" in breakdown.columns
        assert "cost" in breakdown.columns

    @pytest.mark.parametrize("plan_id", list(tou.available_plans().keys()))
    def test_plan_pricing_context(self, plan_id: str) -> None:
        """Test that each plan can provide pricing context."""
        from datetime import datetime

        plan = tou.plan(plan_id)

        # Test with datetime
        context = plan.pricing_context(datetime(2024, 7, 15, 10, 0))
        assert "season" in context
        assert "period" in context

    @pytest.mark.parametrize("plan_id", list(tou.available_plans().keys()))
    def test_plan_describe(self, plan_id: str) -> None:
        """Test that each plan can describe itself."""

        plan = tou.plan(plan_id)
        description = plan.describe()

        assert isinstance(description, dict)
        assert "profile" in description
        assert "rates" in description


class TestTariffFactory:
    """Tests for the TariffFactory class."""

    def test_factory_list_plans(self) -> None:
        """Test that factory can list all plans."""
        factory = TariffFactory()
        plans = factory.list_plans()

        assert len(plans) > 0
        assert isinstance(plans, tuple)

    def test_factory_create_plan(self) -> None:
        """Test that factory can create a plan."""

        factory = TariffFactory()
        plan = factory.create_plan("residential_simple_2_tier")

        assert plan is not None
        assert plan.profile is not None
        assert plan.rates is not None

    def test_factory_create_invalid_plan(self) -> None:
        """Test that factory raises KeyError for invalid plan."""

        factory = TariffFactory()
        with pytest.raises(KeyError, match="Plan not found"):
            factory.create_plan("nonexistent_plan")

    def test_factory_create_classmethod(self) -> None:
        """Test TariffFactory.create() class method."""

        plan = TariffFactory.create("residential_simple_2_tier")
        assert plan is not None


README_PLAN_ROWS = re.findall(
    r"^\|(?: \*\*[^|]+\*\* \|)? `(\w+)` \| ([^|]+?) \|",
    (Path(__file__).resolve().parents[1] / "README.md").read_text("utf-8"),
    re.MULTILINE,
)
JULY_USAGE = pd.Series(
    0.25, index=pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min")
)


def test_readme_plan_tables_name_plans_as_available_plans_does() -> None:
    """README's plan tables give each plan the name available_plans() gives."""
    names = tou.available_plans()
    rows = [(plan_id, name) for plan_id, name in README_PLAN_ROWS if plan_id in names]
    assert {plan_id for plan_id, _ in rows} == set(names)
    assert rows == [(plan_id, names[plan_id]) for plan_id, _ in rows]


@pytest.mark.parametrize(
    ("alias", "plan_id"),
    [
        ("表燈非營業（累進）", "lighting_non_business_tiered"),
        ("表燈營業（累進）", "lighting_business_tiered"),
        ("表燈標準二段式", "lighting_standard_2_tier"),
        ("表燈標準三段式", "lighting_standard_3_tier"),
        ("低壓電動車充電", "low_voltage_ev"),
        ("高壓電動車充電", "high_voltage_ev"),
    ],
)
def test_names_the_readme_used_to_give_still_resolve(alias, plan_id) -> None:
    assert tou.plan(alias).name == tou.plan(plan_id).name


@pytest.mark.parametrize("plan_id", list(tou.available_plans()))
def test_a_plans_own_name_resolves_to_it(plan_id) -> None:
    """An exact name wins over a part of a longer one, so 高壓電力-二段式時間電價
    is not also part of 特高壓電力-二段式時間電價."""
    name = tou.plan(plan_id).name
    assert tou.plan(name).name == name


@pytest.mark.parametrize(
    "query", [" High_Voltage_2_Tier ", "HIGH_VOLTAGE_2_TIER", " 高壓電力二段式 "]
)
def test_ids_and_names_ignore_case_and_surrounding_spaces(query) -> None:
    assert tou.plan(query).name == tou.plan("high_voltage_2_tier").name


def test_removed_plan_hint_ignores_case_and_surrounding_spaces() -> None:
    """CHANGELOG 0.2.0 Removed: the error names the 二段式 plan to use."""
    with pytest.raises(tou.UnknownPlanError, match="high_voltage_2_tier"):
        tou.plan(" HIGH_VOLTAGE_POWER ")


@pytest.mark.parametrize("query", ["unknown_plan", "二段式", "", None, 3])
@pytest.mark.parametrize(
    "entry",
    [
        tou.plan,
        lambda query: tou.calculate_bill(JULY_USAGE, query),
        tou.get_plan_requirements,
    ],
    ids=["plan", "calculate_bill", "get_plan_requirements"],
)
def test_a_plan_no_name_finds_raises_one_error_everywhere(entry, query) -> None:
    """README Errors catches PowerKitError from tou.plan("unknown_plan").
    tou.plan raised ValueError and calculate_bill KeyError, so the error is
    both as well."""
    with pytest.raises(tou.UnknownPlanError) as raised:
        entry(query)
    for kind in (tou.PowerKitError, KeyError, ValueError):
        assert isinstance(raised.value, kind)
    assert not str(raised.value).startswith("'")
