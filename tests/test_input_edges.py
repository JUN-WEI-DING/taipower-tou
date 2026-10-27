"""What an integrator may pass to calculate_bill, BillingInputs and tou.plan,
and whether the package bills it as the rules say or refuses it.

Prices are from src/taipower_tou/data/詳細電價表.md (114/10/1): 底度 lines
334-339, 簡易型二段式 lines 189-192, 標準型二段式 lines 234-237, 低壓電力二段式
lines 535-540, 電動車 lines 627-629 and 983, 高壓電力二段式 line 856 and its
超約 lines 1089-1133. 營業規章 第三條 (docs/references/營業規章第一章.txt line
114) and 第十二條 (營業規章第二章.txt line 108) make a 需量 a 15-minute
average, and 營業規章施行細則 第二十八條 (營業規章施行細則第四章.txt line 5)
drops its fraction of a kW. July 2026 has no 離峰日 but its Sundays, and
2026-07-15 is a Wednesday, 尖峰 from 09:00 on 二段式.
"""

import copy
import json
import math
import os
import subprocess
import sys
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

import taipower_tou as tou

SRC = Path(__file__).resolve().parents[1] / "src"
JULY = pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min")
JULY_HOURS = pd.date_range("2026-07-01", "2026-07-31 23:00", freq="h")
JULY_AUGUST = pd.date_range("2026-07-01", "2026-08-31 23:45", freq="15min")
SPIKE = pd.Timestamp("2026-07-15 14:15")
REGULAR_SUMMER = 223.60
# 30 kW over a 200 kW 經常契約: 20 kW within 10% at 2x, 10 kW at 3x.
OVER_30_KW = (20 * 2 + 10 * 3) * REGULAR_SUMMER
HIGH_VOLTAGE_PLANS = [
    "high_voltage_2_tier",
    "high_voltage_three_stage",
    "high_voltage_batch",
    "high_voltage_ev",
    "extra_high_voltage_2_tier",
    "extra_high_voltage_three_stage",
    "extra_high_voltage_batch",
]


def _contract_200():
    return {"regular": 200, "non_summer": 0, "saturday_semi_peak": 0, "off_peak": 0}


def _spike(index):
    demand = pd.Series(100.0, index=index)
    demand[SPIKE] = 230.0
    return demand


def _high_voltage_bill(usage, **inputs):
    inputs.setdefault("contract_capacities", _contract_200())
    inputs = tou.BillingInputs(taipower_rounding=False, **inputs)
    return tou.calculate_bill(usage, "high_voltage_2_tier", inputs).iloc[0]


def _installed_bill(demand_peak):
    """low_voltage_2_tier for July 2026 on a 10 kW 裝置契約."""
    demand = pd.Series(5.0, index=JULY)
    demand[SPIKE] = demand_peak
    inputs = tou.BillingInputs(basic_fee_inputs={"裝置契約": 10}, demand_kw=demand)
    usage = pd.Series(0.25, index=JULY)
    return tou.calculate_bill(usage, "low_voltage_2_tier", inputs)


@pytest.mark.filterwarnings("ignore::UserWarning")
@pytest.mark.parametrize(("plan_id", "name"), tou.available_plans().items())
def test_every_plan_id_and_chinese_name_bill_the_same_plan(plan_id, name):
    """README Public API Index: available_plans() returns {plan_id:
    chinese_name}, and PlanStore.resolve_plan takes the Chinese name too
    (factory.py:155). tou.plan and calculate_bill accept both."""
    assert tou.plan(name).name == tou.plan(plan_id).name
    usage = pd.Series(0.25, index=JULY)

    def bill(plan):
        inputs = tou.BillingInputs(
            contract_capacities={"regular": 200}, billing_cycle_months=1
        )
        return tou.calculate_bill(usage, plan, inputs)

    pd.testing.assert_frame_equal(bill(name), bill(plan_id))


@pytest.mark.parametrize(
    ("removed", "replacement"),
    [
        ("high_voltage_power", "high_voltage_2_tier"),
        ("高壓電力", "high_voltage_2_tier"),
        ("extra_high_voltage_power", "extra_high_voltage_2_tier"),
        ("特高壓電力", "extra_high_voltage_2_tier"),
    ],
)
@pytest.mark.parametrize(
    "entry",
    [
        tou.plan,
        lambda name: tou.calculate_bill(pd.Series(0.25, index=JULY), name),
    ],
    ids=["plan", "calculate_bill"],
)
def test_removed_plans_name_the_plan_to_use(entry, removed, replacement):
    """CHANGELOG 0.2.0 Removed: asking for high_voltage_power (高壓電力) or
    extra_high_voltage_power (特高壓電力) raises an error that names the
    二段式 plan to use."""
    with pytest.raises((KeyError, ValueError), match=replacement):
        entry(removed)


def test_unknown_plan_name_raises_value_error():
    """tou.plan docstring: Raises ValueError if plan name is not found."""
    with pytest.raises(ValueError):
        tou.plan("unknown_plan")


@pytest.mark.parametrize("plan", HIGH_VOLTAGE_PLANS)
def test_high_voltage_bill_without_a_contract_is_refused(plan):
    """MissingRequiredInput docstring: raised when a plan requires contract
    capacity, as high voltage plans do, and BillingInputs gives none."""
    with pytest.raises(tou.MissingRequiredInput):
        tou.calculate_bill(pd.Series(0.25, index=JULY), plan, tou.BillingInputs())


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_contract_capacity_kw_is_billed_as_the_contract():
    """The MissingRequiredInput message (billing.py:290) says to provide either
    contract_capacity_kw or contract_capacities. A 200 kW contract pays
    200 x 223.60 = 44720.0 in July, and 150 kW of demand is within it."""
    bill = _high_voltage_bill(
        pd.Series(0.25, index=JULY),
        contract_capacities={},
        contract_capacity_kw=200,
        demand_kw=pd.Series(150.0, index=JULY),
    )
    assert bill["basic_cost"] == pytest.approx(200 * REGULAR_SUMMER)
    assert bill["adjustment"] == pytest.approx(0.0)


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_lighting_standard_inputs_pick_the_household_fee_by_phase():
    """BillingInputs.for_lighting_standard docstring: phase is the meter phase
    for the per-household fee. Three-phase 標準型二段式 pays 按戶計收 262.50
    and 30 kW x 236.20 of 經常契約 in July (lines 234-237)."""
    inputs = tou.BillingInputs.for_lighting_standard(phase="three", contract_kw=30)
    usage = pd.Series(0.01, index=JULY)
    bill = tou.calculate_bill(usage, "lighting_standard_2_tier", inputs).iloc[0]
    assert bill["basic_cost"] == pytest.approx(262.50 + 30 * 236.20)


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_lighting_standard_contract_is_the_one_demand_is_checked_against():
    """for_lighting_standard docstring: contract_kw is the contract capacity.
    20 kW of demand is within a 30 kW contract and pays no 超約 (第三章 五(三)5,
    lines 409-450)."""
    inputs = tou.BillingInputs.for_lighting_standard(phase="single", contract_kw=30)
    inputs.demand_kw = pd.Series(20.0, index=JULY)
    usage = pd.Series(0.01, index=JULY)
    bill = tou.calculate_bill(usage, "lighting_standard_2_tier", inputs).iloc[0]
    assert bill["adjustment"] == pytest.approx(0.0)


def test_installed_contract_bill_is_accepted_in_strict_mode():
    """第四章 五(三)1 (line 659): a 裝置契約 time-of-use bill pays 按戶 and per
    kW of 裝置契約, 105.00 + 10 x 137.50 (lines 535-537). Its inputs are
    complete, and strict mode raises only on invalid or missing inputs
    (calculate_bill_from_list docstring)."""
    inputs = tou.BillingInputs(basic_fee_inputs={"裝置契約": 10})
    usage = pd.Series(0.25, index=JULY)
    bill = tou.calculate_bill(usage, "low_voltage_2_tier", inputs, strict=True)
    assert bill["basic_cost"].iloc[0] == pytest.approx(1480.0)


def test_residential_inputs_are_accepted_by_the_non_time_plan_in_strict_mode():
    """BillingInputs.for_residential makes inputs for residential plans with a
    meter specification. An empty two-month bill on a 30 A three-phase meter
    pays 底度 of 10 A x 6 kWh a month (line 338), 120 kWh at 1.78, 213.6
    rounded to 214."""
    inputs = tou.BillingInputs.for_residential(phase="three", voltage=220, ampere=30)
    usage = pd.Series(0.0, index=JULY_AUGUST)
    bill = tou.calculate_bill(usage, "residential_non_tou", inputs, strict=True)
    assert bill["total"].tolist() == [214.0]


@pytest.mark.parametrize("households", [-1.0, math.nan], ids=["negative", "nan"])
def test_basic_fee_input_with_an_invalid_value_is_refused_in_strict_mode(
    households,
):
    """InvalidBasicFeeInput docstring: raised when basic_fee_inputs contains
    invalid keys or values, in strict mode."""
    inputs = tou.BillingInputs(basic_fee_inputs={"basic_fee": households})
    with pytest.raises(tou.InvalidBasicFeeInput):
        tou.calculate_bill(
            pd.Series(0.25, index=JULY),
            "residential_simple_2_tier",
            inputs,
            strict=True,
        )


def test_basic_fee_input_unknown_to_the_plan_is_refused_in_strict_mode():
    """InvalidBasicFeeInput docstring: in strict mode users may only give the
    fee labels of their plan. 簡易型 has no 裝置契約."""
    inputs = tou.BillingInputs(basic_fee_inputs={"裝置契約": 10})
    with pytest.raises(tou.InvalidBasicFeeInput):
        tou.calculate_bill(
            pd.Series(0.25, index=JULY),
            "residential_simple_2_tier",
            inputs,
            strict=True,
        )


def test_demand_given_as_a_list_is_refused_as_invalid_usage():
    """InvalidUsageInput docstring: raised when usage inputs are missing or
    invalid, and billing.py:1389 says demand_kw must be a pandas.Series with a
    DatetimeIndex."""
    with pytest.raises(tou.InvalidUsageInput):
        _high_voltage_bill(pd.Series(0.25, index=JULY), demand_kw=[100.0, 230.0])


@pytest.mark.parametrize("entry", [tou.calculate_bill, tou.calculate_bill_breakdown])
def test_empty_usage_is_refused(entry):
    """CHANGELOG 0.2.0 Fixed: an empty usage series raises InvalidUsageInput."""
    empty = pd.Series([], dtype=float, index=pd.DatetimeIndex([]))
    with pytest.raises(tou.InvalidUsageInput):
        entry(empty, "residential_simple_2_tier")


def test_quarter_hour_demand_counts_when_usage_is_hourly():
    """README 4. Advanced Bill Calculation recommends 15-minute demand_kw next
    to hourly usage. 第三條: 需量 is the 十五分鐘平均瓩數, so 230 kW from 14:15
    on a 200 kW contract is 30 kW over (lines 1093-1133)."""
    bill = _high_voltage_bill(pd.Series(1.0, index=JULY_HOURS), demand_kw=_spike(JULY))
    assert bill["adjustment"] == pytest.approx(OVER_30_KW)


@pytest.mark.parametrize(
    ("usage_tz", "demand_tz"),
    [(None, "Asia/Taipei"), (None, "UTC"), ("Asia/Taipei", None)],
    ids=["taipei-demand", "utc-demand", "taipei-usage"],
)
def test_timezone_aware_demand_is_read_in_taiwan_time(usage_tz, demand_tz):
    """README 2. Time & Rate Queries: timezone-aware timestamps are converted to
    Taiwan time and naive ones read as Taiwan time (CHANGELOG 0.2.0: timezone-
    aware input is evaluated in Taiwan local time). Each pair is the same
    230 kW quarter hour, 30 kW over."""
    usage_index = JULY.tz_localize(usage_tz) if usage_tz else JULY
    demand = _spike(JULY)
    if demand_tz:
        demand.index = JULY.tz_localize("Asia/Taipei").tz_convert(demand_tz)
    bill = _high_voltage_bill(pd.Series(0.25, index=usage_index), demand_kw=demand)
    assert bill["adjustment"] == pytest.approx(OVER_30_KW)


@pytest.mark.parametrize(
    ("demand_peak", "warns"), [(10.0, False), (10.9, False), (11.0, True)]
)
def test_installed_contract_warns_when_whole_kw_demand_passes_it(demand_peak, warns):
    """README 2. Demand Penalty: when demand passes the 裝置契約 kW the package
    warns (第四章 七(一)2, line 740). 第二十八條 counts 最高需量 in whole kW,
    so 10.9 kW is 10 kW and does not pass a 10 kW 裝置契約."""
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        _installed_bill(demand_peak)
    passed = [w for w in record if "裝置契約" in str(w.message)]
    assert bool(passed) == warns


@pytest.mark.parametrize(
    ("freq", "warns"),
    [("5min", False), ("15min", False), ("30min", True), ("h", True)],
)
def test_demand_coarser_than_15_minutes_warns(freq, warns):
    """README 4. Advanced Bill Calculation: the library warns if demand data is
    coarser than 15 minutes."""
    index = pd.date_range("2026-07-01", "2026-07-31 23:59", freq=freq)
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        _high_voltage_bill(
            pd.Series(0.25, index=JULY), demand_kw=pd.Series(100.0, index=index)
        )
    coarse = [w for w in record if "resolution" in str(w.message)]
    assert bool(coarse) == warns
    if not warns:
        assert not [w for w in record if issubclass(w.category, UserWarning)]


def _hourly_july():
    return pd.Series(0.25, index=JULY_HOURS)


IN_PROCESS_WARNINGS = {
    "unknown-basic-fee-key/calculate_bill": (
        UserWarning,
        lambda: tou.calculate_bill(
            _hourly_july(),
            "high_voltage_2_tier",
            tou.BillingInputs(
                contract_capacities=_contract_200(), basic_fee_inputs={"x": 1}
            ),
        ),
    ),
    "meter-spec/calculate_bill_simple": (
        UserWarning,
        lambda: tou.calculate_bill_simple(
            pd.Series(0.25, index=pd.date_range(JULY[0], periods=1488, freq="h")),
            "lighting_business_tiered",
        ),
    ),
    "meter-spec/calculate_bill_from_list": (
        UserWarning,
        lambda: tou.calculate_bill_from_list(
            [0.25] * len(JULY_HOURS),
            "lighting_business_tiered",
            start="2026-07-01",
            freq="1h",
            inputs=tou.BillingInputs(billing_cycle_months=1),
        ),
    ),
    "meter-spec/calculate_bill_from_dict": (
        UserWarning,
        lambda: tou.calculate_bill_from_dict(
            _hourly_july().to_dict(),
            "lighting_business_tiered",
            inputs=tou.BillingInputs(billing_cycle_months=1),
        ),
    ),
    "demand-resolution/calculate_bill": (
        UserWarning,
        lambda: tou.calculate_bill(
            _hourly_july(),
            "high_voltage_2_tier",
            tou.BillingInputs(
                contract_capacities=_contract_200(),
                demand_kw=pd.Series(100.0, index=JULY_HOURS),
            ),
        ),
    ),
    "demand-resolution/calculate_bill_breakdown": (
        UserWarning,
        lambda: tou.calculate_bill_breakdown(
            _hourly_july(),
            "high_voltage_2_tier",
            tou.BillingInputs(
                contract_capacities=_contract_200(),
                demand_kw=pd.Series(100.0, index=JULY_HOURS),
            ),
        ),
    ),
    "installed-contract-passed/calculate_bill": (
        UserWarning,
        lambda: _installed_bill(15.0),
    ),
    "cache-dir/calculate_bill": (
        DeprecationWarning,
        lambda: tou.calculate_bill(
            _hourly_july(), "residential_simple_2_tier", cache_dir=Path(".")
        ),
    ),
    "cache-dir/taiwan_calendar": (
        DeprecationWarning,
        lambda: tou.taiwan_calendar(cache_dir=Path(".")),
    ),
}


@pytest.mark.parametrize("case", IN_PROCESS_WARNINGS)
def test_warning_names_the_callers_line(case):
    """Each warnings.warn in the package passes a stacklevel (billing.py:387,
    992, 1353; calendar.py:163) so the warning names the caller's line.
    A DeprecationWarning that names a package line is hidden by Python's
    default filter."""
    category, call = IN_PROCESS_WARNINGS[case]
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        call()
    raised = [w for w in record if issubclass(w.category, category)]
    assert raised
    assert {Path(w.filename).name for w in raised} == {Path(__file__).name}


FRESH_PROCESS_WARNINGS = {
    "partial-period/calculate_bill": (
        "PartialPeriodWarning",
        "tou.calculate_bill(pd.Series(1.0, index=pd.date_range("
        "'2026-07-03', '2026-07-20', freq='h')), 'residential_simple_2_tier')",
    ),
    "partial-period/calculate_bill_from_list": (
        "PartialPeriodWarning",
        "tou.calculate_bill_from_list([1.0] * 24, 'residential_simple_2_tier', "
        "start='2026-07-03', freq='1h')",
    ),
    "unchecked-price/calculate_bill": (
        "UncheckedPriceWarning",
        "tou.calculate_bill(pd.Series(1.0, index=pd.date_range("
        "'2025-07-01', '2025-07-31 23:00', freq='h')), 'residential_simple_2_tier')",
    ),
    "unchecked-price/costs": (
        "UncheckedPriceWarning",
        "tou.costs(pd.Series(1.0, index=pd.date_range("
        "'2025-07-01', periods=3, freq='h')), 'residential_simple_2_tier')",
    ),
    "unchecked-year/calculate_bill": (
        "UncheckedYearWarning",
        "tou.calculate_bill(pd.Series(1.0, index=pd.date_range("
        "'2028-01-01', '2028-01-31 23:00', freq='h')), 'residential_simple_2_tier')",
    ),
    "unchecked-year/calculate_costs": (
        "UncheckedYearWarning",
        "tou.plan('residential_simple_2_tier').calculate_costs(pd.Series(1.0, "
        "index=pd.date_range('2028-01-01', periods=3, freq='h')))",
    ),
    "unchecked-year/is_holiday": (
        "UncheckedYearWarning",
        "tou.is_holiday(date(2028, 1, 1))",
    ),
}

_FRESH_PROCESS = """
import json, warnings
from datetime import date
import pandas as pd
import taipower_tou as tou
with warnings.catch_warnings(record=True) as record:
    warnings.simplefilter("always")
    {call}
print(json.dumps([[w.category.__name__, w.filename] for w in record]))
"""


@pytest.mark.parametrize("case", FRESH_PROCESS_WARNINGS)
def test_once_per_process_warning_names_the_callers_line(case):
    """UncheckedPriceWarning is raised once per process (README Prices and
    Their Dates), UncheckedYearWarning once per year (README 2. Time & Rate
    Queries) and PartialPeriodWarning once per usage span (billing.py:1305),
    so each case runs in a fresh interpreter, whose -c code is <string>. Their
    stacklevel (billing.py:1315, tariff.py:620, calendar.py:137) is meant to
    name the caller's line."""
    category, call = FRESH_PROCESS_WARNINGS[case]
    path = os.environ.get("PYTHONPATH")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(SRC), path]))}
    result = subprocess.run(
        [sys.executable, "-c", _FRESH_PROCESS.format(call=call)],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    files = {name for kind, name in json.loads(result.stdout) if kind == category}
    assert files == {"<string>"}


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_inputs_reused_for_another_plan_bill_that_plan_monthly():
    """One BillingInputs, first for a two-month 表燈非時間 bill, then for
    簡易型二段式, whose 每月電費為基本電費與流動電費之總和 (第三章 五(二)1, line
    350). July is one bill of 75.00 按戶計收 (line 189) and 1 kWh at the 夏月
    尖峰 5.16 (line 192), cut to 5.1, total 80."""
    inputs = tou.BillingInputs()
    tou.calculate_bill(
        pd.Series(0.25, index=JULY_AUGUST), "residential_non_tou", inputs
    )
    usage = pd.Series(0.0, index=JULY)
    usage[pd.Timestamp("2026-07-15 10:00")] = 1.0
    bill = tou.calculate_bill(usage, "residential_simple_2_tier", inputs)
    assert bill["basic_cost"].tolist() == [75.0]
    assert bill["total"].tolist() == [80.0]


@pytest.mark.filterwarnings("ignore::UserWarning")
@pytest.mark.parametrize(
    ("plan", "inputs"),
    [
        (
            "residential_non_tou",
            {"meter_phase": "three", "meter_voltage_v": 220, "meter_ampere": 30},
        ),
        (
            "high_voltage_2_tier",
            {
                "contract_capacities": {"regular": 200, "non_summer": 0},
                "basic_fee_inputs": {"經常契約": 200},
                "demand_kw": pd.Series(
                    210.0, index=pd.date_range(JULY[0], periods=8928, freq="5min")
                ),
                "demand_adjustment_factor": 1.5,
            },
        ),
    ],
    ids=["minimum-usage", "five-minute-demand"],
)
def test_bill_leaves_the_callers_series_and_dicts_unchanged(plan, inputs):
    """README Billing helpers: calculate_bill returns the bill DataFrame, and no
    argument is documented as an output. The 底度 rescale, the quarter-hour
    averaging of 5-minute demand and demand_adjustment_factor leave the
    caller's objects alone, and a second call bills the same."""
    usage = pd.Series(0.001, index=JULY)
    before = copy.deepcopy((usage, inputs))
    billing_inputs = tou.BillingInputs(billing_cycle_months=1, **inputs)
    first = tou.calculate_bill(usage, plan, billing_inputs)
    second = tou.calculate_bill(usage, plan, billing_inputs)
    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_series_equal(usage, before[0])
    for key, value in inputs.items():
        if isinstance(value, pd.Series):
            pd.testing.assert_series_equal(value, before[1][key])
        else:
            assert value == before[1][key]


def test_high_voltage_ev_price_does_not_compound():
    """第五章 四(四) (line 983): 高壓 電動車 is 95% of the 低壓 table, whose
    夏月 尖峰 is 12.47 (line 629). pricing_context keeps that 95% price
    (CHANGELOG 0.2.0), however often the plan is built. A 200 kW contract
    with 1 kWh at 尖峰 is 262.50 + 200 x 47.20 + 12.4 = 9714.9, 9715 元, and
    pays 95% of the rounded bill (各類電價表及計算範例 page 16), 9229."""
    usage = pd.Series(0.0, index=JULY)
    usage[pd.Timestamp("2026-07-15 17:00")] = 1.0
    inputs = tou.BillingInputs(contract_capacities={"regular": 200})
    peak = datetime(2026, 7, 15, 17, 0)
    for _ in range(3):
        assert tou.plan("high_voltage_ev").pricing_context(peak)["rate"] == (
            pytest.approx(12.47 * 0.95)
        )
        assert tou.TariffFactory().create_plan("high_voltage_ev").pricing_context(peak)[
            "rate"
        ] == pytest.approx(12.47 * 0.95)
        bill = tou.calculate_bill(usage, "high_voltage_ev", inputs)
        assert bill["total"].tolist() == [9229.0]


def test_three_phase_380_volt_meter_has_the_low_voltage_minimum():
    """第三章 二 (line 126): 表燈 is supplied at 三相四線式220/380伏特 too, and
    五(一)1(2) (line 338) bills a 三相低壓電表 at least 6 kWh per ampere, a meter
    over 10 A as 10 A. An empty July is 60 kWh at 1.78, 106.8 TWD."""
    inputs = tou.BillingInputs(
        meter_phase="three",
        meter_voltage_v=380,
        meter_ampere=30,
        billing_cycle_months=1,
        taipower_rounding=False,
    )
    usage = pd.Series(0.0, index=JULY)
    bill = tou.calculate_bill(usage, "residential_non_tou", inputs).iloc[0]
    assert bill["energy_cost"] == pytest.approx(60 * 1.78)


@pytest.mark.parametrize(("power_factor", "share"), [(0, 0.08), (100, -0.015)])
def test_power_factor_far_from_80_percent(power_factor, share):
    """第五章 六 (line 1085): 每低1%，該月份電費應增加0.1%, and 超過95%部分不予
    扣減 (README Power Factor: max discount 1.5%). 0% adds 8% and 100% takes
    1.5% off."""
    bill = _high_voltage_bill(pd.Series(0.25, index=JULY), power_factor=power_factor)
    month = bill["basic_cost"] + bill["energy_cost"]
    assert bill["adjustment"] == pytest.approx(share * month)
