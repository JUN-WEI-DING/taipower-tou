"""Every line of the 電價表 chapters this package bills is a clause with a test.

tests/data/clauses/*.json split each chapter of
src/taipower_tou/data/詳細電價表.md into clauses by line range. A clause of
kind "billing" names the tests that check it. A clause of kind
"not_billing" says why no bill depends on it, such as a heading, a page
number or a rule about applying for a contract. A new or changed clause
fails here until it is tested or explained.
"""

import ast
import json
from pathlib import Path

import pytest

TESTS = Path(__file__).parent
SOURCE = TESTS.parent / "src" / "taipower_tou" / "data" / "詳細電價表.md"
CHAPTERS = {
    path.stem: json.loads(path.read_text("utf-8"))
    for path in sorted((TESTS / "data" / "clauses").glob("*.json"))
}

# Chapters with no plan in this package, so no bill depends on them.
NOT_BILLED = {
    "封面與目次": (1, 33),
    "第一章 包燈電價": (34, 93),
    "第二章 包用電力電價": (94, 119),
    "第六章 臨時用電電價": (1176, 1206),
    "第七章 備用電力電價": (1207, 1507),
    "附錄一 適用電價調整係數行業或用戶電費計算方式": (1600, 2629),
}


def _test_functions():
    names = set()
    for path in TESTS.glob("test_*.py"):
        tree = ast.parse(path.read_text("utf-8"))
        names |= {
            f"{path.name}::{node.name}"
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        }
    return names


def test_chapters_and_not_billed_parts_cover_the_whole_tariff():
    ranges = sorted(
        [tuple(chapter["lines"]) for chapter in CHAPTERS.values()]
        + list(NOT_BILLED.values())
    )
    assert ranges[0][0] == 1
    assert ranges[-1][1] == SOURCE.read_text("utf-8").count("\n")
    gaps = [
        (end, start)
        for (_, end), (start, _) in zip(ranges, ranges[1:])
        if start != end + 1
    ]
    assert gaps == []


@pytest.mark.parametrize("name", CHAPTERS)
def test_clauses_cover_every_line_of_the_chapter_once(name):
    chapter = CHAPTERS[name]
    first, last = chapter["lines"]
    clauses = chapter["clauses"]
    assert clauses[0]["lines"][0] == first
    assert clauses[-1]["lines"][1] == last
    breaks = [
        (a["id"], b["id"])
        for a, b in zip(clauses, clauses[1:])
        if b["lines"][0] != a["lines"][1] + 1
    ]
    assert breaks == []


@pytest.mark.parametrize("name", CHAPTERS)
def test_every_billing_clause_names_tests_that_exist(name):
    tests = _test_functions()
    problems = []
    for clause in CHAPTERS[name]["clauses"]:
        if clause["kind"] == "billing":
            missing = [t for t in clause.get("tests", []) if t not in tests]
            if not clause.get("tests") or missing:
                problems.append((clause["id"], missing or "no tests"))
        elif clause["kind"] == "not_billing":
            if not clause.get("reason"):
                problems.append((clause["id"], "no reason"))
        else:
            problems.append((clause["id"], f"unknown kind {clause['kind']}"))
    assert problems == []


@pytest.mark.parametrize("name", CHAPTERS)
def test_clause_ids_are_unique(name):
    ids = [clause["id"] for clause in CHAPTERS[name]["clauses"]]
    assert len(ids) == len(set(ids))
