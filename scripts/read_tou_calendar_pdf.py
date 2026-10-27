"""Read a Taipower 時間電價日曆表 PDF into one day-type CSV per year.

Each page holds one year. The year comes from the page title (民國 year + 1911)
and each day's type from the fill colour of its cell: red is sunday_holiday,
yellow is saturday, unfilled or white is weekday.

Dev-only requirement (not a package dependency):

    pip install pdfplumber==0.11.10

Usage:

    python scripts/read_tou_calendar_pdf.py <pdf> [--out tests/data/taipower_calendar]
"""

from __future__ import annotations

import argparse
import calendar
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "tests" / "data" / "taipower_calendar"
MONTH_LABELS = (
    "一月",
    "二月",
    "三月",
    "四月",
    "五月",
    "六月",
    "七月",
    "八月",
    "九月",
    "十月",
    "十一月",
    "十二月",
)
TITLE = re.compile(r"(\d{2,3})年時間電價日曆表")
DAY_NUMBER = re.compile(r"\d{1,2}")
ROW_TOLERANCE = 5.0


class CalendarPdfError(Exception):
    pass


def _rgb(color: Any) -> tuple[float, float, float]:
    if isinstance(color, (int, float)):
        return (color, color, color)
    if isinstance(color, (tuple, list)):
        if len(color) == 1:
            return (color[0], color[0], color[0])
        if len(color) == 3:
            return (color[0], color[1], color[2])
        if len(color) == 4:
            c, m, y, k = color
            return ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
    raise CalendarPdfError(f"unsupported fill colour {color!r}")


def _fill_day_type(color: Any) -> str:
    r, g, b = _rgb(color)
    if r > 0.8 and g < 0.2 and b < 0.2:
        return "sunday_holiday"
    if r > 0.8 and g > 0.8 and b < 0.2:
        return "saturday"
    if min(r, g, b) > 0.9:
        return "weekday"
    raise CalendarPdfError(f"day cell has unexpected fill colour {color!r}")


def _centre(obj: dict[str, Any]) -> tuple[float, float]:
    return ((obj["x0"] + obj["x1"]) / 2, (obj["top"] + obj["bottom"]) / 2)


def _year(page: Any) -> int:
    text = re.sub(r"\s+", "", page.extract_text() or "")
    match = TITLE.search(text)
    if match is None:
        raise CalendarPdfError("title 「XXX年時間電價日曆表」 not found")
    return int(match.group(1)) + 1911


def _month_labels(words: list[dict[str, Any]]) -> dict[int, tuple[float, float]]:
    found = [w for w in words if w["text"] in MONTH_LABELS]
    labels = {
        MONTH_LABELS.index(w["text"]) + 1: (_centre(w)[0], w["top"]) for w in found
    }
    if len(found) != 12 or len(labels) != 12:
        names = sorted(w["text"] for w in found)
        raise CalendarPdfError(f"expected 12 month blocks, found {names}")
    return labels


def _month_of(word: dict[str, Any], labels: dict[int, tuple[float, float]]) -> int:
    above = [(top, x, month) for month, (x, top) in labels.items() if top < word["top"]]
    row_top = max(top for top, _, _ in above)
    x = _centre(word)[0]
    row = [
        (abs(lx - x), month)
        for top, lx, month in above
        if row_top - top < ROW_TOLERANCE
    ]
    return min(row)[1]


def _day_type(word: dict[str, Any], fills: list[dict[str, Any]]) -> str:
    x, y = _centre(word)
    kinds = {
        _fill_day_type(r["non_stroking_color"])
        for r in fills
        if r["x0"] <= x <= r["x1"] and r["top"] <= y <= r["bottom"]
    }
    coloured = kinds - {"weekday"}
    if len(coloured) > 1:
        raise CalendarPdfError(f"day {word['text']} sits in cells {sorted(coloured)}")
    return coloured.pop() if coloured else "weekday"


def _violations(year: int, days: dict[date, str]) -> list[str]:
    first = date(year, 1, 1)
    length = 366 if calendar.isleap(year) else 365
    expected = {first + timedelta(days=n) for n in range(length)}
    problems = [f"{d} missing" for d in sorted(expected - days.keys())]
    for day, kind in sorted(days.items()):
        weekday = day.weekday()
        if weekday == 6 and kind != "sunday_holiday":
            problems.append(f"{day} is a Sunday but {kind}")
        elif weekday == 5 and kind == "weekday":
            problems.append(f"{day} is a Saturday but weekday")
        elif weekday < 5 and kind == "saturday":
            problems.append(f"{day} is Monday-Friday but saturday")
    return problems


def read_page(page: Any) -> tuple[int, dict[date, str]]:
    year = _year(page)
    words = page.extract_words()
    labels = _month_labels(words)
    fills = [r for r in page.rects if r.get("fill")]
    first_row = min(top for _, top in labels.values())
    days: dict[date, str] = {}
    for word in words:
        if not DAY_NUMBER.fullmatch(word["text"]) or word["top"] <= first_row:
            continue
        month = _month_of(word, labels)
        try:
            day = date(year, month, int(word["text"]))
        except ValueError:
            raise CalendarPdfError(f"{month}/{word['text']} is not a date") from None
        if day in days:
            raise CalendarPdfError(f"{day} appears twice")
        days[day] = _day_type(word, fills)
    problems = _violations(year, days)
    if problems:
        raise CalendarPdfError(f"{year}: " + "; ".join(problems))
    return year, days


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    years: dict[int, dict[date, str]] = {}
    with pdfplumber.open(args.pdf) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            try:
                year, days = read_page(page)
            except CalendarPdfError as error:
                sys.exit(f"{args.pdf} page {number}: {error}")
            if year in years:
                sys.exit(f"{args.pdf} page {number}: year {year} appears twice")
            years[year] = days

    args.out.mkdir(parents=True, exist_ok=True)
    for year, days in sorted(years.items()):
        path = args.out / f"{year}.csv"
        rows = "".join(f"{day.isoformat()},{days[day]}\n" for day in sorted(days))
        path.write_text("date,day_type\n" + rows, encoding="utf-8")
        print(f"Wrote {path} ({len(days)} days)")


if __name__ == "__main__":
    main()
