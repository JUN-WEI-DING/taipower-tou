"""The energy side of a bill, one path of its statechart at a time.

Each test replays a path through calculate_bill_breakdown: the caller asks for
a bill, the meter's registers are read, a 表燈非時間 bill under its 底度 is
billed its 底度, the kWh are priced, and a 簡易型 bill pays 1.04 more on its
kWh over 2000 a month. The registers and the billed kWh are the breakdown's
details, and the priced kWh its summary.

施行細則 第二十八條 (docs/references/營業規章施行細則第四章.txt lines 2-6) reads
有效電度 to the whole kWh, half up. The README (Complete Bill Example) reads a
時間電價 meter's 尖峰 and 離峰 on registers of their own and keeps every kWh
unrounded with taipower_rounding=False. Prices and rules are the 電價表 第三章
(src/taipower_tou/data/詳細電價表.md): 住宅 tiers lines 134-145, 簡易型 lines
183-226, 底度 lines 332-341, 隔月 tiers lines 347-348 and 簡易型 rules lines
349-356. Usage falls at 17:00 (尖峰 on both 簡易型 plans in 夏月) and 03:00
(離峰 in both seasons) on weekdays that Taipower's 時間電價日曆表
(tests/data/taipower_calendar/2026.csv) lists as weekdays.
"""

import pandas as pd
import pytest

import taipower_tou as tou

SIMPLE_2 = "residential_simple_2_tier"
SIMPLE_3 = "residential_simple_3_tier"
METER = {"meter_phase": "single", "meter_voltage_v": 110, "meter_ampere": 10}


def _usage(first_day, last_day, kwh):
    index = pd.date_range(first_day, f"{last_day} 23:00", freq="h")
    usage = pd.Series(0.0, index=index)
    for at, value in kwh.items():
        usage[pd.Timestamp(at)] = value
    return usage


def _breakdown(usage, plan, **inputs):
    return tou.calculate_bill_breakdown(usage, plan, tou.BillingInputs(**inputs))


def _registers(breakdown):
    return breakdown["details"].groupby("period_type")["usage_kwh"].sum()


@pytest.mark.parametrize(
    ("plan", "rounding", "kwh", "read", "energy", "extra"),
    [
        (SIMPLE_2, True, (1200, 1000), (1200, 1000), 8252.0, 208.0),
        (SIMPLE_3, True, (1200, 1000), (1200, 1000), 10616.0, 208.0),
        (SIMPLE_2, True, (1000.4, 1000.4), (1000, 1000), 7220.0, 0.0),
        (SIMPLE_3, True, (1000.4, 1000.4), (1000, 1000), 9190.0, 0.0),
        (SIMPLE_2, False, (1000.4, 1000.4), (1000.4, 1000.4), 7222.888, 0.832),
        (SIMPLE_3, False, (1000.4, 1000.4), (1000.4, 1000.4), 9193.676, 0.832),
        (SIMPLE_2, True, (1000.5, 999.6), (1001, 1000), 7225.1, 1.0),
        (SIMPLE_3, True, (1000.5, 999.6), (1001, 1000), 9197.1, 1.0),
        (SIMPLE_2, False, (1000.5, 999.6), (1000.5, 999.6), 7221.756, 0.104),
        (SIMPLE_3, False, (1000.5, 999.6), (1000.5, 999.6), 9192.741, 0.104),
    ],
    ids=[
        "2-tier-1200-and-1000",
        "3-tier-1200-and-1000",
        "2-tier-fractions-read-2000",
        "3-tier-fractions-read-2000",
        "2-tier-fractions-unrounded",
        "3-tier-fractions-unrounded",
        "2-tier-half-reads-up-to-2001",
        "3-tier-half-reads-up-to-2001",
        "2-tier-half-unrounded",
        "3-tier-half-unrounded",
    ],
)
def test_simple_month_reads_each_register_then_adds_1_04_over_2000(
    plan, rounding, kwh, read, energy, extra
):
    """第三章 五(二)2: 每月總度數超過2,000度之部分依適用電價加計流動電費, 加1.04
    a kWh, on the sum of the registers, as 各類電價表及計算範例 page 4 works it:
    [（1,200度+1,000度）-2,000度 ]×1.04元. 尖峰 is 5.16 (二段式) or 7.13
    (三段式) and 離峰 2.06 in 夏月. Rounded, 1000.4 and 1000.4 kWh read 1000
    each, 2000 in all, with no 加計. 1000.5 and 999.6 read 1001 and 1000, so
    1 kWh pays 1.04, cut to 1.0 (第二十九條). Unrounded, 0.8 and 0.1 kWh pay."""
    peak, off = kwh
    usage = _usage(
        "2026-08-01",
        "2026-08-31",
        {"2026-08-03 17:00": peak, "2026-08-03 03:00": off},
    )
    breakdown = _breakdown(usage, plan, taipower_rounding=rounding)
    registers = _registers(breakdown)
    assert registers["peak"] == pytest.approx(read[0])
    assert registers["off_peak"] == pytest.approx(read[1])
    bill = breakdown["summary"].iloc[0]
    assert bill["energy_cost"] == pytest.approx(energy)
    assert bill["surcharge"] == pytest.approx(extra)


@pytest.mark.parametrize("plan", [SIMPLE_2, SIMPLE_3])
@pytest.mark.parametrize(
    ("july", "august", "energy", "extra"),
    [(2200, 2200, 9064.0, 416.0), (3000, 500, 7210.0, 0.0)],
    ids=["2200-each-month", "3000-then-500"],
)
def test_two_month_simple_bill_adds_1_04_over_4000(plan, july, august, energy, extra):
    """README (How TOU Rates Work): a two-month bill pays the 1.04 on its kWh
    over 4000, 2000 for each month. 離峰 is 2.06 in 夏月. 2200 kWh in each
    month pays on 400 kWh. 3000 kWh in July and 500 in August, 3500 in all,
    pays none."""
    usage = _usage(
        "2026-07-01",
        "2026-08-31",
        {"2026-07-06 03:00": july, "2026-08-03 03:00": august},
    )
    breakdown = _breakdown(usage, plan, billing_cycle_months=2)
    assert _registers(breakdown)["off_peak"] == pytest.approx(july + august)
    bill = breakdown["summary"].iloc[0]
    assert bill["energy_cost"] == pytest.approx(energy)
    assert bill["surcharge"] == pytest.approx(extra)


@pytest.mark.parametrize("plan", [SIMPLE_2, SIMPLE_3])
@pytest.mark.parametrize(
    ("first_day", "last_day", "days"),
    [
        ("2026-05-01", "2026-06-30", ("2026-05-12", "2026-06-02")),
        ("2026-09-01", "2026-10-31", ("2026-09-01", "2026-10-06")),
    ],
    ids=["over-6-1", "over-10-1"],
)
@pytest.mark.parametrize(
    ("rounding", "each", "energy"),
    [(True, 0.5, 2.0), (False, 0.6, 0.6 * 1.99 + 0.6 * 2.06)],
    ids=["rounded", "unrounded"],
)
def test_simple_register_over_two_seasons_prices_each_part_in_its_season(
    plan, first_day, last_day, days, rounding, each, energy
):
    """第三章 五(二)2: 流動電費依...離峰時間實用電度分別計算, at 1.99 in 非夏月
    and 2.06 in 夏月. The 離峰 register reads 0.6 + 0.6 kWh as 1 kWh, which
    falls half in each season (README, Complete Bill Example): 0.995 + 1.03 =
    2.025, cut to 2.0. Unrounded, each 0.6 kWh keeps its own season."""
    usage = _usage(first_day, last_day, {f"{day} 03:00": 0.6 for day in days})
    breakdown = _breakdown(
        usage, plan, billing_cycle_months=2, taipower_rounding=rounding
    )
    off_peak = breakdown["details"].query("period_type == 'off_peak'")
    assert off_peak.groupby("season")["usage_kwh"].sum().to_dict() == pytest.approx(
        {"summer": each, "non_summer": each}
    )
    bill = breakdown["summary"].iloc[0]
    assert bill["energy_cost"] == pytest.approx(energy)
    assert bill["surcharge"] == 0


@pytest.mark.parametrize(
    ("kwh", "rounding", "billed", "energy"),
    [
        (0.4, True, 20, 35.6),
        (0.4, False, 20, 35.6),
        (19.5, True, 20, 35.6),
        (19.5, False, 20, 35.6),
        (120.5, True, 121, 216.1),
        (120.5, False, 120.5, 1.78 * 120 + 2.55 * 0.5),
    ],
    ids=[
        "0.4-reads-0-billed-at-minimum",
        "0.4-unrounded-billed-at-minimum",
        "19.5-reads-20",
        "19.5-unrounded-billed-at-minimum",
        "120.5-reads-121",
        "120.5-unrounded",
    ],
)
def test_tiered_month_reads_whole_kwh_then_minimum_usage_then_tiers(
    kwh, rounding, billed, energy
):
    """A 表燈非時間 meter reads all its kWh on one register (第二十八條), and a
    bill under its 底度 is billed the 底度, 2 kWh an ampere on a single-phase
    10 A meter (第三章 五(一)1). 120 kWh are at 1.78 and the next at 2.55 in
    夏月 (四(一)1). 60.25 + 60.25 kWh read 121 on the one register, 120 x
    1.78 + 2.55 = 216.15, cut to 216.1. 19.5 kWh read 20, the 底度 itself.
    20 x 1.78 = 35.6."""
    usage = _usage(
        "2026-08-01",
        "2026-08-31",
        {"2026-08-03 03:00": kwh / 2, "2026-08-20 15:00": kwh / 2},
    )
    breakdown = _breakdown(
        usage,
        "residential_non_tou",
        billing_cycle_months=1,
        taipower_rounding=rounding,
        **METER,
    )
    assert breakdown["details"]["usage_kwh"].sum() == pytest.approx(billed)
    assert breakdown["summary"].iloc[0]["energy_cost"] == pytest.approx(energy)


@pytest.mark.parametrize(
    ("rounding", "billed", "energy"),
    [(True, 241, 429.7), (False, 240.5, 1.78 * 240 + 2.55 * 0.5)],
    ids=["reads-241", "unrounded"],
)
def test_two_month_tiered_bill_doubles_its_tiers(rounding, billed, energy):
    """第三章 五(一)2: 用戶因實施隔月抄表、收費，其計費之分段度數加倍計算, so a
    July and August bill has 240 kWh at 1.78. 240.5 kWh read 241, 427.2 +
    2.55 = 429.75, cut to 429.7."""
    usage = _usage(
        "2026-07-01",
        "2026-08-31",
        {"2026-07-06 03:00": 120.25, "2026-08-03 03:00": 120.25},
    )
    breakdown = _breakdown(
        usage, "residential_non_tou", taipower_rounding=rounding, **METER
    )
    assert breakdown["details"]["usage_kwh"].sum() == pytest.approx(billed)
    assert breakdown["summary"].iloc[0]["energy_cost"] == pytest.approx(energy)


SUMMER_350 = 1.78 * 240 + 2.55 * 110
NON_SUMMER_350 = 1.78 * 240 + 2.26 * 110
SUMMER_350_4 = 1.78 * 240 + 2.55 * 110.4
NON_SUMMER_350_4 = 1.78 * 240 + 2.26 * 110.4


@pytest.mark.parametrize(
    ("first_day", "last_day", "days"),
    [
        ("2026-05-01", "2026-06-30", ("2026-05-12", "2026-06-02")),
        ("2026-09-01", "2026-10-31", ("2026-09-01", "2026-10-06")),
    ],
    ids=["over-6-1", "over-10-1"],
)
@pytest.mark.parametrize(
    ("rounding", "billed", "summer", "non_summer", "energy"),
    [
        (True, 350, SUMMER_350, NON_SUMMER_350, 691.4),
        (
            False,
            350.4,
            SUMMER_350_4,
            NON_SUMMER_350_4,
            (30 * SUMMER_350_4 + 31 * NON_SUMMER_350_4) / 61,
        ),
    ],
    ids=["reads-350", "unrounded"],
)
def test_two_month_tiered_bill_over_6_1_or_10_1_weights_each_season_by_its_days(
    first_day, last_day, days, rounding, billed, summer, non_summer, energy
):
    """README (Rate Change Apportionment), after Taipower's FAQ 請問電費如何計算:
    a period over 夏月 and 非夏月 prices all its kWh at each season's tiered
    prices, tiers doubled, and weights each by its share of the days. May and
    June have 31 days of 非夏月 and 30 of 夏月, and September and October 30 of
    夏月 and 31 of 非夏月. 350.4 kWh read 350: 707.7 x 30/61 + 675.8 x 31/61 =
    691.49, cut to 691.4."""
    usage = _usage(first_day, last_day, {f"{day} 03:00": 175.2 for day in days})
    breakdown = _breakdown(
        usage, "residential_non_tou", taipower_rounding=rounding, **METER
    )
    details = breakdown["details"].set_index("season")
    assert details["usage_kwh"].sum() == pytest.approx(billed)
    assert details.loc["summer", "energy_cost"] == pytest.approx(summer * 30 / 61)
    assert details.loc["non_summer", "energy_cost"] == pytest.approx(
        non_summer * 31 / 61
    )
    assert breakdown["summary"].iloc[0]["energy_cost"] == pytest.approx(energy)
