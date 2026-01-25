from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLANS_PATH = ROOT / "src" / "tou_calculator" / "data" / "plans.json"
SUMMARY_PATH = ROOT / "src" / "tou_calculator" / "data" / "plans_summary.md"


def _format_definitions(definitions: dict) -> list[str]:
    lines: list[str] = []
    lines.append("## Definitions")
    lines.append("")

    lines.append("### Seasons")
    for key in ("seasons", "seasons_high_voltage"):
        seasons = definitions.get(key, [])
        if not seasons:
            continue
        lines.append(f"- {key}:")
        for season in seasons:
            lines.append(f"  - {season['name']}: {season['start']} ~ {season['end']}")
    lines.append("")

    periods = definitions.get("periods", [])
    lines.append("### Periods")
    lines.append(f"- {', '.join(periods)}")
    lines.append("")

    day_types = definitions.get("day_types", [])
    lines.append("### Day types")
    lines.append(f"- {', '.join(day_types)}")
    lines.append("")

    return lines


def _plan_notes(plan: dict) -> str:
    notes: list[str] = []
    if "basic_fee" in plan:
        notes.append("basic_fee")
    if "basic_fees" in plan:
        notes.append("basic_fees")
    if "tiers" in plan:
        notes.append(f"tiers:{len(plan['tiers'])}")
    if "rates" in plan:
        notes.append(f"rates:{len(plan['rates'])}")
    if "schedules" in plan:
        notes.append(f"schedules:{len(plan['schedules'])}")
    if "over_2000_kwh_surcharge" in plan:
        notes.append("over_2000_kwh_surcharge")
    if "variant" in plan:
        notes.append(plan["variant"])
    return ", ".join(notes) or "-"


def _format_plans(plans: list[dict]) -> list[str]:
    lines: list[str] = []
    lines.append("## Plans")
    lines.append("")
    lines.append("| id | name | type | category | season_strategy | notes |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for plan in plans:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(plan.get("id", "")),
                    str(plan.get("name", "")),
                    str(plan.get("type", "")),
                    str(plan.get("category", "")),
                    str(plan.get("season_strategy", "")),
                    _plan_notes(plan),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def main() -> None:
    data = json.loads(PLANS_PATH.read_text(encoding="utf-8"))
    lines: list[str] = []

    lines.append("# plans.json Summary")
    lines.append("")
    lines.append(f"Version: {data.get('version', '')}")
    lines.append("")

    definitions = data.get("definitions", {})
    lines.extend(_format_definitions(definitions))

    plans = data.get("plans", [])
    lines.extend(_format_plans(plans))

    SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
