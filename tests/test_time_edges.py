"""Time, calendar and data-shape edges of a bill.

Expected prices come from tests/data/tariff_114_10_01.json, a transcription of
src/taipower_tou/data/詳細電價表.md (114/10/1) with the source line of each
number. Its "summer" field is each table's 夏月: 6月1日至9月30日 for 第三、四章
(lines 137, 187) and 5月16日至10月15日 for 第五章 (line 854). Day types come
from Taipower's 時間電價日曆表 (tests/data/taipower_calendar/2026.csv), whose
離峰日 are Sundays and the list at lines 313-325.
"""

import json
import os
import subprocess
import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import taipower_tou as tou

DATA = Path(__file__).parent / "data"
SRC = Path(__file__).resolve().parents[1] / "src"
TABLE = json.loads((DATA / "tariff_114_10_01.json").read_text("utf-8"))
DAY_TYPES = pd.read_csv(DATA / "taipower_calendar" / "2026.csv", index_col="date")[
    "day_type"
].to_dict()
TOU_PLANS = [
    plan for plan in TABLE if TABLE[plan]["energy"] or "derived" in TABLE[plan]
]

# Both sides of each 夏月 edge, for every plan.
SEASON_EDGES = [
    "2026-05-15",
    "2026-05-16",
    "2026-05-31",
    "2026-06-01",
    "2026-09-30",
    "2026-10-01",
    "2026-10-15",
    "2026-10-16",
]
# Listed days on a Saturday (2/21 初五, 2/28, 4/4, 10/10) or a weekday (2/16
# 除夕, 9/28, 12/25), listed Sundays (4/5 清明, 10/25), and the weekdays next
# to them (2/27, 4/3, 4/6, 10/9, 10/26), which Taipower's calendar keeps as
# weekdays.
OFFPEAK_EDGES = [
    "2026-02-16",
    "2026-02-21",
    "2026-02-27",
    "2026-02-28",
    "2026-04-03",
    "2026-04-04",
    "2026-04-05",
    "2026-04-06",
    "2026-09-28",
    "2026-10-09",
    "2026-10-10",
    "2026-10-25",
    "2026-10-26",
    "2026-12-25",
]
EDGE_DAYS = SEASON_EDGES + OFFPEAK_EDGES

HV_REGULAR_SUMMER = 223.60  # 第五章 二段式 經常契約, line 856
HV_REGULAR_NON_SUMMER = 166.90
HV_200 = {"regular": 200, "non_summer": 0, "saturday_semi_peak": 0, "off_peak": 0}


def _rows(plan_id, share=1.0):
    entry = TABLE[plan_id]
    derived = entry.get("derived")
    if derived:
        return _rows(derived["from"], share * derived["share"])
    return [{**row, "price": row["price"] * share} for row in entry["energy"]]


def _cells(plan_id, low_voltage_amounts=False):
    """(season, day type, minute of day) -> (period, price), every minute.

    low_voltage_amounts drops high_voltage_ev's 95%, which a bill takes off
    in its adjustment (CHANGELOG 0.2.0).
    """
    rows = _rows(plan_id)
    if low_voltage_amounts and "derived" in TABLE[plan_id]:
        rows = _rows(TABLE[plan_id]["derived"]["from"])
    cells = {}
    for row in rows:
        start = int(row["start"][:2]) * 60 + int(row["start"][3:])
        end = int(row["end"][:2]) * 60 + int(row["end"][3:])
        for minute in range(start, end):
            key = (row["season"], row["day_type"], minute)
            cells[key] = (row["period"], round(row["price"], 4))
    return cells


def _season(plan_id, ts):
    first, last = TABLE[plan_id]["summer"].split("..")
    return "summer" if first <= f"{ts:%m-%d}" <= last else "non_summer"


def _tariff(plan_id, index, low_voltage_amounts=False):
    cells = _cells(plan_id, low_voltage_amounts)
    return [
        cells[
            (
                _season(plan_id, ts),
                DAY_TYPES[f"{ts:%Y-%m-%d}"],
                ts.hour * 60 + ts.minute,
            )
        ]
        for ts in index
    ]


def _quarter_hours(days):
    return pd.DatetimeIndex(
        [ts for day in days for ts in pd.date_range(day, periods=96, freq="15min")]
    )


def _energy_bill(usage, plan_id, **inputs):
    inputs.setdefault("contract_capacities", {"regular": 100})
    inputs = tou.BillingInputs(taipower_rounding=False, **inputs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return tou.calculate_bill(usage, plan_id, inputs)


@pytest.mark.parametrize("plan_id", TOU_PLANS)
def test_every_quarter_hour_of_the_edge_days_has_the_tariff_price(plan_id):
    """Each quarter hour on both sides of the 夏月 edges, on listed 離峰日 that
    fall on a Saturday, and on the weekdays next to them (CHANGELOG 0.2.0:
    補假 and 彈性放假 days are no longer off-peak, and listed days that fall on
    a Saturday are now off-peak)."""
    index = _quarter_hours(EDGE_DAYS)
    context = tou.plan(plan_id).pricing_context(index)
    actual = [(p, round(r, 4)) for p, r in zip(context["period"], context["rate"])]
    expected = _tariff(plan_id, index)
    wrong = {
        str(ts): (got, want)
        for ts, got, want in zip(index, actual, expected)
        if got != want
    }
    assert wrong == {}


def _edge_instants(plan_id):
    """00:00, 23:45 and each period start with the quarter hour before it."""
    starts = {
        int(row["start"][:2]) * 60 + int(row["start"][3:]) for row in _rows(plan_id)
    }
    minutes = {0, 23 * 60 + 45} | starts | {m - 15 for m in starts if m}
    return pd.DatetimeIndex(
        [
            pd.Timestamp(day) + timedelta(minutes=minute)
            for day in EDGE_DAYS
            for minute in sorted(minutes)
        ]
    )


@pytest.mark.parametrize("plan_id", TOU_PLANS)
def test_a_single_datetime_at_an_edge_has_the_tariff_price(plan_id):
    """pricing_context(datetime) at the same edges, one instant at a time."""
    plan = tou.plan(plan_id)
    index = _edge_instants(plan_id)
    wrong = {}
    for ts, want in zip(index, _tariff(plan_id, index)):
        context = plan.pricing_context(ts.to_pydatetime())
        got = (context["period"], round(context["rate"], 4))
        if got != want:
            wrong[str(ts)] = (got, want)
    assert wrong == {}


MONTHS_2026 = ["2026-02", "2026-05", "2026-06", "2026-09", "2026-10"]


@pytest.mark.parametrize("plan_id", TOU_PLANS)
def test_monthly_bills_price_each_quarter_hour_by_its_day_and_season(plan_id):
    """February 2026 has 春節 through Saturday 2/21, 2/27 and Saturday 2/28.
    May and October hold the 5/16 and 10/16 edges, and May/June and
    September/October meet at the 6/1 and 10/1 edges. Seeded random kWh make
    every quarter hour count. A high_voltage_ev bill lists the 低壓 amounts
    (CHANGELOG 0.2.0)."""
    index = pd.DatetimeIndex(
        [
            ts
            for month in MONTHS_2026
            for ts in pd.date_range(
                month, pd.Period(month).end_time.floor("15min"), freq="15min"
            )
        ]
    )
    rng = np.random.default_rng(20261028)
    usage = pd.Series(rng.uniform(0.0, 1.0, len(index)), index=index)
    prices = [price for _, price in _tariff(plan_id, index, low_voltage_amounts=True)]
    expected = (usage * prices).groupby(index.to_period("M")).sum()
    bill = _energy_bill(usage, plan_id)
    assert bill.index.strftime("%Y-%m").tolist() == MONTHS_2026
    assert bill["energy_cost"].tolist() == pytest.approx(expected.tolist())


def _single_kwh(plan_id, freq, at):
    index = pd.date_range("2026-07-01", "2026-07-31 23:59", freq=freq)
    usage = pd.Series(0.0, index=index)
    usage[pd.Timestamp(at)] = 1.0
    return _energy_bill(usage, plan_id)["energy_cost"].iloc[0]


@pytest.mark.parametrize("freq", ["1min", "15min", "30min", "1h"])
@pytest.mark.parametrize(
    ("at", "price"),
    [("16:00", 9.39), ("22:00", 5.85), ("-16:00", 5.85), ("-22:00", 9.39)],
    ids=["from-16:00", "from-22:00", "to-16:00", "to-22:00"],
)
def test_a_timestamp_labels_the_start_of_its_interval(freq, at, price):
    """README lines 369-374 give hourly kWh labelled 06:00 as off-peak and
    09:00 as peak on 簡易型二段式, whose 夏月 尖峰 starts at 09:00 (line 191),
    so a reading covers the interval its timestamp starts. high_voltage_three_stage
    on Wednesday 2026-07-15 is 半尖峰 5.85 until 16:00 and from 22:00, and 尖峰
    9.39 between (lines 896-899). "-16:00" is the interval that ends at 16:00."""
    step = pd.Timedelta(freq)
    start = pd.Timestamp(f"2026-07-15 {at.lstrip('-')}")
    if at.startswith("-"):
        start -= step
    assert _single_kwh("high_voltage_three_stage", freq, start) == pytest.approx(price)


@pytest.mark.parametrize("freq", ["1min", "15min", "30min"])
@pytest.mark.parametrize(
    ("at", "price"),
    [("15:30", 12.47), ("21:30", 3.18), ("-15:30", 3.18), ("-21:30", 12.47)],
    ids=["from-15:30", "from-21:30", "to-15:30", "to-21:30"],
)
def test_half_hour_edges_of_batch_production(freq, at, price):
    """批次生產 is 尖峰 15:30~21:30 at 12.47 and 離峰 3.18 otherwise on a 夏月
    weekday (lines 968-971). Data every 30 minutes or finer splits the hour."""
    step = pd.Timedelta(freq)
    start = pd.Timestamp(f"2026-07-15 {at.lstrip('-')}")
    if at.startswith("-"):
        start -= step
    assert _single_kwh("high_voltage_batch", freq, start) == pytest.approx(price)


TAIPEI = timezone(timedelta(hours=8))


@pytest.mark.parametrize(
    "zone", [timezone.utc, TAIPEI, timezone(timedelta(hours=-5))], ids=str
)
@pytest.mark.parametrize(
    ("taiwan_time", "expected"),
    [
        (datetime(2026, 7, 15, 10, 0), ("summer", "peak", 5.16)),
        (datetime(2026, 6, 1, 0, 0), ("summer", "off_peak", 2.06)),
        (datetime(2026, 7, 13, 9, 0), ("summer", "peak", 5.16)),
    ],
    ids=["wednesday-10:00", "summer-starts", "monday-09:00"],
)
def test_aware_datetime_is_priced_in_taiwan_time(zone, taiwan_time, expected):
    """README line 882: Timezone-aware timestamps are converted to Taiwan time
    (UTC+8) first. CHANGELOG 0.2.0: Timezone-aware input is evaluated in Taiwan
    local time. 簡易型二段式 夏月 weekdays are 尖峰 5.16 from 09:00 and 離峰 2.06
    before (lines 191-197). 2026-07-13 is a Monday, 2026-06-01 the first 夏月 day."""
    aware = taiwan_time.replace(tzinfo=TAIPEI).astimezone(zone)
    season, period, rate = expected
    context = tou.pricing_context(aware, "residential_simple_2_tier")
    assert (context["season"], context["period"], context["rate"]) == (
        season,
        period,
        rate,
    )
    assert tou.period_at(aware, "residential_simple_2_tier").value == period
    assert tou.period_context(aware, "residential_simple_2_tier")["day_type"] == (
        "weekday"
    )


JULY_15MIN = pd.date_range("2026-07-01", "2026-07-31 23:45", freq="15min")
JULY_HOURLY = pd.date_range("2026-07-01", "2026-07-31 23:00", freq="h")


def _demand(index, readings, base=100.0):
    demand = pd.Series(base, index=index)
    for at, kw in readings.items():
        demand[pd.Timestamp(at, tz=index.tz)] = kw
    return demand


def _demand_bill(usage, demand, **inputs):
    inputs = tou.BillingInputs(
        contract_capacities=HV_200,
        demand_kw=demand,
        taipower_rounding=False,
        **inputs,
    )
    return tou.calculate_bill(usage, "high_voltage_2_tier", inputs).iloc[0]


@pytest.mark.parametrize(
    ("usage", "demand"),
    [
        (
            pd.Series(4.0, index=JULY_HOURLY),
            _demand(JULY_15MIN, {"2026-07-15 14:15": 220.0}),
        ),
        (
            pd.Series(1.0, index=JULY_15MIN),
            _demand(JULY_15MIN.tz_localize("Asia/Taipei"), {"2026-07-15 14:15": 220.0}),
        ),
        (
            pd.Series(
                1.0, index=JULY_15MIN.tz_localize("Asia/Taipei").tz_convert("UTC")
            ),
            _demand(JULY_15MIN, {"2026-07-15 14:15": 220.0}),
        ),
    ],
    ids=["hourly-kwh-15min-demand", "naive-kwh-taipei-demand", "utc-kwh-naive-demand"],
)
def test_demand_counts_when_its_index_differs_from_the_usage_index(usage, demand):
    """README lines 832-837: energy cost takes any resolution and demand needs
    15 minutes, so hourly kWh with 15-minute demand is the advised input.
    README line 882: naive timestamps are Taiwan time. 220 kW at 14:15 on
    Wednesday 2026-07-15 is 20 kW over a 200 kW 經常契約 in 夏月尖峰時間
    (第五章 七(一)1(1), lines 1093-1094), within 10% at 2x (lines 1132-1133)."""
    bill = _demand_bill(usage, demand)
    assert bill["adjustment"] == pytest.approx(20 * 2 * HV_REGULAR_SUMMER)


@pytest.mark.parametrize(
    ("readings", "over_kw"),
    [
        ({f"2026-07-15 14:{minute:02d}": 220.0 for minute in range(15)}, 20),
        ({"2026-07-15 14:07": 400.0}, 0),
    ],
    ids=["quarter-hour-at-220", "one-minute-at-400"],
)
def test_one_minute_demand_is_averaged_over_each_quarter_hour(readings, over_kw):
    """營業規章 第三條: 需量 is the 十五分鐘平均瓩數 (CHANGELOG 0.2.0). Fifteen
    minutes at 220 kW average 220 kW. One minute at 400 kW among 100 kW
    readings averages 120 kW, under the 200 kW contract."""
    index = pd.date_range("2026-07-01", "2026-07-31 23:59", freq="1min")
    demand = _demand(index, readings)
    bill = _demand_bill(pd.Series(1.0, index=JULY_15MIN), demand)
    assert bill["adjustment"] == pytest.approx(over_kw * 2 * HV_REGULAR_SUMMER)


@pytest.mark.parametrize("freq", ["30min", "1h"])
def test_demand_coarser_than_15_minutes_warns(freq):
    """README line 1043: The library will automatically warn if detected
    resolution is coarser than 15 minutes."""
    index = pd.date_range("2026-07-01", "2026-07-31 23:59", freq=freq)
    with pytest.warns(UserWarning, match="15-minute"):
        _demand_bill(pd.Series(1.0, index=JULY_15MIN), pd.Series(100.0, index=index))


def test_hourly_demand_with_the_readme_adjustment_factor():
    """README lines 1026-1041 scale hourly demand by demand_adjustment_factor.
    190 kW x 1.15 = 218.5 kW, and 最高需量 drops its fraction of a kW
    (營業規章施行細則 第二十八條), so 18 kW over a 200 kW contract at 2x."""
    demand = _demand(JULY_HOURLY, {"2026-07-01 14:00": 190.0})
    with pytest.warns(UserWarning, match="15-minute"):
        bill = _demand_bill(
            pd.Series(1.0, index=JULY_HOURLY), demand, demand_adjustment_factor=1.15
        )
    assert bill["adjustment"] == pytest.approx(18 * 2 * HV_REGULAR_SUMMER)


@pytest.mark.parametrize(
    ("month", "charged"),
    [("2026-05", True), ("2026-10", False)],
    ids=["may-20-is-summer", "october-20-is-not"],
)
def test_high_voltage_over_contract_follows_the_day_season(month, charged):
    """第五章 夏月 is 5月16日至10月15日 (line 854). 夏月尖峰時間超約瓩數 is the
    highest 尖峰 demand less 經常契約, and 非夏月 less 經常 plus 非夏月契約
    (第五章 七(一)1, lines 1093-1097). 215 kW at 10:00 on Wednesday 5/20 is 夏月
    尖峰 (09:00~24:00), 15 kW over 200 kW. 215 kW at 10:00 on Tuesday 10/20 is
    非夏月 尖峰 (06:00~11:00), under 200 + 50 kW. Neither text says how a
    month that holds both seasons prices its excess, so May asserts only that
    one is charged."""
    index = pd.date_range(month, pd.Period(month).end_time.floor("15min"), freq="15min")
    demand = _demand(index, {f"{month}-20 10:00": 215.0})
    inputs = tou.BillingInputs(
        contract_capacities={**HV_200, "non_summer": 50},
        demand_kw=demand,
        taipower_rounding=False,
    )
    bill = tou.calculate_bill(
        pd.Series(0.1, index=index), "high_voltage_2_tier", inputs
    ).iloc[0]
    if charged:
        assert bill["adjustment"] > 0
    else:
        assert bill["adjustment"] == pytest.approx(0.0)


def _whole_months(start, end, total, freq="D"):
    index = pd.date_range(start, end, freq=freq)
    return pd.Series(total / len(index), index=index)


RESIDENTIAL = dict(meter_phase="single", meter_voltage_v=110, meter_ampere=10)
# 住宅用 tiers doubled for two months (lines 138-146): 240 kWh at 1.78, then
# 241-660 kWh at 2.55 (夏月) or 2.26 (非夏月).
SUMMER_610 = 1.78 * 240 + 2.55 * 370
NON_SUMMER_610 = 1.78 * 240 + 2.26 * 370


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("2026-05-01", "2026-06-30", SUMMER_610 * 30 / 61 + NON_SUMMER_610 * 31 / 61),
        ("2026-06-01", "2026-07-31", SUMMER_610),
        ("2025-12-01", "2026-01-31", NON_SUMMER_610),
    ],
    ids=["may-june", "june-july", "december-january"],
)
def test_two_month_tiered_bill_from_an_odd_or_even_month(start, end, expected):
    """README lines 259-261: bills of billing_cycle_months calendar months from
    the first month of usage. CHANGELOG 0.2.0: 610 kWh over May-June 2026 on
    residential_non_tou is 1316.2 TWD, each season's tiered cost weighted by its
    share of the 61 days (30 in 夏月). June-July is all 夏月, and
    December-January all 非夏月 across the new year."""
    bill = tou.calculate_bill(
        _whole_months(start, end, 610),
        "residential_non_tou",
        tou.BillingInputs(taipower_rounding=False, **RESIDENTIAL),
    )
    assert bill.index.tolist() == [pd.Timestamp(start)]
    assert bill["energy_cost"].tolist() == pytest.approx([expected])


@pytest.mark.parametrize(
    ("cycle", "start", "end", "label", "expected"),
    [
        (
            tou.BillingCycleType.EVEN_MONTH,
            "2026-05-01",
            "2026-06-30",
            "2026-06-01",
            SUMMER_610 * 30 / 61 + NON_SUMMER_610 * 31 / 61,
        ),
        (
            tou.BillingCycleType.ODD_MONTH,
            "2026-06-01",
            "2026-07-31",
            "2026-07-01",
            SUMMER_610,
        ),
        (
            tou.BillingCycleType.ODD_MONTH,
            "2025-12-01",
            "2026-01-31",
            "2026-01-01",
            NON_SUMMER_610,
        ),
    ],
    ids=["even-may-june", "odd-june-july", "odd-december-january"],
)
def test_tariff_plan_pairs_months_by_the_reading_month(
    cycle, start, end, label, expected
):
    """README lines 222-227: odd-month readings bill 12月-1月 ... 6月-7月, read in
    the later month, and even-month readings bill 1月-2月 ... 5月-6月."""
    costs = tou.plan("residential_non_tou", billing_cycle_type=cycle).calculate_costs(
        _whole_months(start, end, 610)
    )
    assert costs.index.tolist() == [pd.Timestamp(label)]
    assert costs.tolist() == pytest.approx([expected])


@pytest.mark.parametrize(
    ("monthly_kwh", "surcharge"),
    [(2000, 0.0), (2200, 2 * 200 * 1.04)],
    ids=["2000-each-month", "2200-each-month"],
)
def test_two_month_simple_tou_bill_charges_over_2000_kwh_per_month(
    monthly_kwh, surcharge
):
    """簡易型: 每月總度數超過2000度之部分 每度 加 1.04 (line 204), and
    第三章 五(二)2 adds it for 每月總度數超過2,000度之部分. A two-month bill
    with 2000 kWh in each month has no month over 2000 kWh. CHANGELOG 0.2.0:
    calculate_bill doubles each tier's kWh for two-month bills."""
    index = pd.date_range("2026-07-01", "2026-08-31 23:45", freq="15min")
    per_month = pd.Series(1, index=index).groupby(index.month).transform("sum")
    usage = pd.Series(monthly_kwh / per_month.to_numpy(), index=index)
    bill = tou.calculate_bill(
        usage,
        "residential_simple_2_tier",
        tou.BillingInputs(taipower_rounding=False, billing_cycle_months=2),
    ).iloc[0]
    assert bill["surcharge"] == pytest.approx(surcharge, abs=1e-6)


@pytest.mark.parametrize(
    "month", ["2026-02", "2026-03", "2026-04"], ids=["28-days", "31-days", "30-days"]
)
def test_basic_fee_does_not_depend_on_the_days_in_the_month(month):
    """營業規章 第二十六條: 每月抄表收費之用戶，全期按三十日計算. 200 kW of 非夏月
    經常契約 at 166.90 (line 856) whatever the month's length."""
    index = pd.date_range(month, pd.Period(month).end_time.floor("15min"), freq="15min")
    bill = tou.calculate_bill(
        pd.Series(0.1, index=index),
        "high_voltage_2_tier",
        tou.BillingInputs(contract_capacities=HV_200, taipower_rounding=False),
    ).iloc[0]
    assert bill["basic_cost"] == pytest.approx(200 * HV_REGULAR_NON_SUMMER)


def test_two_month_bill_pays_two_months_of_basic_fee():
    """營業規章 第二十六條: 隔月抄表收費...全期按六十日計算. 簡易型 按戶計收 is
    75.00 每戶每月 (line 189)."""
    usage = _whole_months("2026-07-01", "2026-08-31 23:00", 600, freq="h")
    bill = tou.calculate_bill(
        usage,
        "residential_simple_2_tier",
        tou.BillingInputs(taipower_rounding=False, billing_cycle_months=2),
    ).iloc[0]
    assert bill["basic_cost"] == pytest.approx(2 * 75.00)


EMPTY = pd.Series([], index=pd.DatetimeIndex([]), dtype=float)
ENTRY_POINTS = {
    "calculate_bill": lambda usage: tou.calculate_bill(
        usage, "residential_simple_2_tier"
    ),
    "calculate_bill_breakdown": lambda usage: tou.calculate_bill_breakdown(
        usage, "residential_simple_2_tier"
    ),
    "calculate_bill_tiered": lambda usage: tou.calculate_bill(
        usage, "residential_non_tou", tou.BillingInputs(**RESIDENTIAL)
    ),
    "calculate_costs": lambda usage: tou.plan(
        "residential_simple_2_tier"
    ).calculate_costs(usage),
    "monthly_breakdown": lambda usage: tou.plan(
        "residential_simple_2_tier"
    ).monthly_breakdown(usage),
}


@pytest.mark.parametrize("entry", ENTRY_POINTS)
def test_empty_usage_raises_invalid_usage_input(entry):
    """CHANGELOG 0.2.0: An empty usage series raises InvalidUsageInput."""
    with pytest.raises(tou.InvalidUsageInput):
        ENTRY_POINTS[entry](EMPTY)


def test_empty_usage_dict_raises_invalid_usage_input():
    """CHANGELOG 0.2.0: An empty usage series raises InvalidUsageInput."""
    with pytest.raises(tou.InvalidUsageInput):
        tou.calculate_bill_from_dict({}, "residential_simple_2_tier")


def _bad_usage(kind):
    usage = pd.Series(1.0, index=JULY_HOURLY)
    if kind == "unsorted":
        return usage.iloc[::-1]
    usage.iloc[5] = {"nan": np.nan, "negative": -1.0}[kind]
    return usage


@pytest.mark.parametrize("entry", ENTRY_POINTS)
@pytest.mark.parametrize("bad", ["nan", "negative", "unsorted"])
def test_invalid_usage_raises_invalid_usage_input(bad, entry):
    """errors.InvalidUsageInput: Raised when usage inputs are missing or invalid.
    The 電價表 bills 實用電度, so a negative (exported) kWh is not usage."""
    with pytest.raises(tou.InvalidUsageInput):
        ENTRY_POINTS[entry](_bad_usage(bad))


def test_partial_period_warns_on_every_call():
    """README line 261: usage that starts or ends mid-month raises
    PartialPeriodWarning. Unlike UncheckedPriceWarning (once per process) and
    UncheckedYearWarning (once per year), no limit is given. A second customer
    with the same reading dates gets the same mismatched bill."""
    usage = _whole_months("2026-03-10", "2026-04-09 23:00", 300, freq="h")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tou.calculate_bill(usage, "residential_simple_2_tier")
    with pytest.warns(tou.PartialPeriodWarning):
        tou.calculate_bill(usage, "residential_simple_2_tier")


FRESH_PROCESS = r"""
import json
import warnings

import pandas as pd

import taipower_tou as tou

seen = {}


def bill(name, start, end, basic=False, **kwargs):
    usage = pd.Series(0.1, index=pd.date_range(start, end, freq="15min"))
    contracts = {"regular": 200, "non_summer": 0, "saturday_semi_peak": 0,
                 "off_peak": 0}
    inputs = tou.BillingInputs(contract_capacities=contracts,
                               taipower_rounding=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            result = tou.calculate_bill(usage, "high_voltage_2_tier", inputs,
                                        **kwargs)
        except tou.CalendarError:
            seen[name] = "CalendarError"
            return
    seen[name] = sorted(
        {w.category.__name__ for w in caught if w.category is not UserWarning}
    )
    if basic:
        seen[name + " basic"] = round(float(result["basic_cost"].iloc[0]), 2)


bill("first priced month", "2025-10-01", "2025-10-31 23:45")
bill("last priced month", "2026-12-01", "2026-12-31 23:45")
bill("month before", "2025-09-01", "2025-09-30 23:45")
bill("month after", "2027-01-01", "2027-01-31 23:45")
bill("month after again", "2027-02-01", "2027-02-28 23:45")
bill("last checked calendar", "2027-12-01", "2027-12-31 23:45")
bill("leap february", "2028-02-01", "2028-02-29 23:45", basic=True)
bill("leap february again", "2028-03-01", "2028-03-31 23:45")
bill("leap february to the 28th", "2028-02-01", "2028-02-28 23:45")
bill("one interval", "2026-07-15 10:00", "2026-07-15 10:00")
bill("2013", "2013-12-01", "2013-12-31 23:45")
bill("2101", "2101-01-01", "2101-01-31 23:45")
bill("2013 custom calendar", "2013-12-01", "2013-12-31 23:45",
     calendar_instance=tou.custom_calendar())
print(json.dumps(seen))
"""


def test_dates_outside_the_prices_and_calendars_in_a_fresh_process():
    """README lines 30-32 and CHANGELOG 0.2.0: usage before 2025-10-01 or after
    2026-12-31 raises UncheckedPriceWarning once per process. README line 897:
    years after 2027 raise UncheckedYearWarning once per year. CHANGELOG
    0.2.0: years outside 2014-2100 raise CalendarError, and
    calendar_instance=custom_calendar(...) bills them. README line 261:
    usage that starts or ends mid-month raises PartialPeriodWarning, so a whole
    leap February does not and one that stops on the 28th does. 營業規章
    第二十六條 bills every month as 30 days, so February 2028 pays a full
    month's basic fee, 200 kW x 166.90 (line 856). A fresh process keeps
    other tests' warnings out."""
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    result = subprocess.run(
        [sys.executable, "-c", FRESH_PROCESS],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=True,
    )
    seen = json.loads(result.stdout.splitlines()[-1])
    price, year, partial = (
        "UncheckedPriceWarning",
        "UncheckedYearWarning",
        "PartialPeriodWarning",
    )
    assert seen == {
        "first priced month": [],
        "last priced month": [],
        "month before": [price],
        "month after": [price],
        "month after again": [],
        "last checked calendar": [],
        "leap february": [year],
        "leap february basic": round(200 * HV_REGULAR_NON_SUMMER, 2),
        "leap february again": [],
        "leap february to the 28th": [partial],
        "one interval": [partial],
        "2013": "CalendarError",
        "2101": "CalendarError",
        "2013 custom calendar": [],
    }
