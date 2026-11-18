"""The data files a script writes match a fresh run of that script."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts"


def _check(script: str) -> None:
    run = subprocess.run(
        [sys.executable, str(SCRIPTS / script), "--check"],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr or run.stdout


def test_plans_summary_matches_plans_json() -> None:
    _check("generate_plans_summary.py")


def test_festival_dates_match_both_ephemerides() -> None:
    pytest.importorskip("lunar_python")
    pytest.importorskip("astronomy")
    _check("generate_festival_dates.py")
