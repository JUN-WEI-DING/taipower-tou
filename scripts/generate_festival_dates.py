"""Generate src/taipower_tou/data/festival_dates.csv.

Taipower's off-peak-day rule needs, per Gregorian year, the dates of 春節
(lunar 1/1), 端午 (lunar 5/5), 中秋 (lunar 8/15) and the 清明 solar term,
all as civil dates in Taiwan time (UTC+8).

Every date comes from two independent sources and the script fails if they
disagree:

- lunar_python, a port of the 寿星天文历 (sxwnl) algorithms.
- astronomy-engine (VSOP87 / lunar theory ephemeris), with the Chinese
  calendar month rule applied here: a month starts on the UTC+8 date of a
  new moon, month 11 contains 冬至, and in a 13-month year the first month
  without a principal term (中氣) is the leap month.

Dev-only requirements (not package dependencies):

    pip install lunar_python==1.4.8 astronomy-engine==2.1.19

Usage:

    python scripts/generate_festival_dates.py [--start 2000] [--end 2100]
    python scripts/generate_festival_dates.py --check
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import NamedTuple

import astronomy
from lunar_python import Lunar, Solar

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "src" / "taipower_tou" / "data" / "festival_dates.csv"
UTC8 = timedelta(hours=8)


class FestivalDates(NamedTuple):
    year: int
    spring_festival: date
    dragon_boat: date
    mid_autumn: date
    qingming: date


def _solar_date(solar: Solar) -> date:
    return date(solar.getYear(), solar.getMonth(), solar.getDay())


def from_lunar_python(year: int) -> FestivalDates:
    terms = Solar.fromYmd(year, 4, 1).getLunar().getJieQiTable()
    return FestivalDates(
        year=year,
        spring_festival=_solar_date(Lunar.fromYmd(year, 1, 1).getSolar()),
        dragon_boat=_solar_date(Lunar.fromYmd(year, 5, 5).getSolar()),
        mid_autumn=_solar_date(Lunar.fromYmd(year, 8, 15).getSolar()),
        qingming=_solar_date(terms["清明"]),
    )


def _utc8_date(moment: astronomy.Time) -> date:
    return (moment.Utc() + UTC8).date()


def _sun_longitude_after(longitude: float, start: astronomy.Time) -> astronomy.Time:
    found = astronomy.SearchSunLongitude(longitude, start, 40)
    if found is None:
        raise RuntimeError(f"Sun longitude {longitude} not found after {start}")
    return found


def _lunar_month_starts(year: int) -> dict[int, date]:
    """Start dates of the non-leap months between 冬至 of year-1 and of year."""
    solstice = _sun_longitude_after(270, astronomy.Time.Make(year - 1, 12, 1, 0, 0, 0))
    principal_terms = [solstice]
    for step in range(1, 13):
        longitude = (270 + 30 * step) % 360
        principal_terms.append(_sun_longitude_after(longitude, principal_terms[-1]))
    terms = [_utc8_date(t) for t in principal_terms]

    new_moons: list[date] = []
    cursor = astronomy.Time.Make(year - 1, 11, 1, 0, 0, 0)
    while not new_moons or new_moons[-1] <= terms[-1]:
        moon = astronomy.SearchMoonPhase(0, cursor, 40)
        if moon is None:
            raise RuntimeError(f"New moon not found after {cursor}")
        new_moons.append(_utc8_date(moon))
        cursor = moon.AddDays(1)

    first = max(d for d in new_moons if d <= terms[0])
    last = max(d for d in new_moons if d <= terms[-1])
    bounds = [d for d in new_moons if first <= d <= last]
    month_count = len(bounds) - 1
    if month_count not in (12, 13):
        raise RuntimeError(f"{year}: {month_count} lunar months between solstices")

    leap_pending = month_count == 13
    number = 11
    starts = {number: bounds[0]}
    for start, end in zip(bounds[1:-1], bounds[2:]):
        if leap_pending and not any(start <= t < end for t in terms):
            leap_pending = False
            continue
        number = number % 12 + 1
        starts[number] = start
    if leap_pending:
        raise RuntimeError(f"{year}: 13 lunar months but no month lacks a 中氣")
    return starts


def from_astronomy_engine(year: int) -> FestivalDates:
    starts = _lunar_month_starts(year)
    qingming = _sun_longitude_after(15, astronomy.Time.Make(year, 3, 20, 0, 0, 0))
    return FestivalDates(
        year=year,
        spring_festival=starts[1],
        dragon_boat=starts[5] + timedelta(days=4),
        mid_autumn=starts[8] + timedelta(days=14),
        qingming=_utc8_date(qingming),
    )


def render(start: int, end: int) -> str:
    lines = [",".join(FestivalDates._fields)]
    mismatches: list[str] = []
    for year in range(start, end + 1):
        primary = from_lunar_python(year)
        secondary = from_astronomy_engine(year)
        for field, a, b in zip(FestivalDates._fields[1:], primary[1:], secondary[1:]):
            if a != b:
                mismatches.append(
                    f"{year} {field}: lunar_python={a} astronomy-engine={b}"
                )
        lines.append(",".join([str(year), *(d.isoformat() for d in primary[1:])]))
    if mismatches:
        raise SystemExit("Sources disagree:\n" + "\n".join(mismatches))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=int, default=2000)
    parser.add_argument("--end", type=int, default=2100)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the committed CSV differs from a fresh render",
    )
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("--start must not be after --end")

    content = render(args.start, args.end)
    if args.check:
        current = (
            OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
        )
        if current != content:
            sys.exit(f"{OUTPUT_PATH.relative_to(ROOT)} is stale; rerun the generator")
        print(f"{OUTPUT_PATH.relative_to(ROOT)} is up to date")
        return
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} ({args.start}-{args.end})")


if __name__ == "__main__":
    main()
