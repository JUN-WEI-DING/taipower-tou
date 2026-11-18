from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.as_posix() not in sys.path:
    sys.path.insert(0, SRC.as_posix())

import pytest  # noqa: E402

from taipower_tou.calendar import _warn_unchecked_year  # noqa: E402
from taipower_tou.tariff import _warn_outside_price_dates  # noqa: E402


@pytest.fixture(autouse=True)
def _each_test_sees_its_own_warnings():
    """The package warns of a date outside its prices or checked years once
    per process. Forget that before each test, so whether a test warns does
    not depend on which tests ran before it."""
    _warn_outside_price_dates.cache_clear()
    _warn_unchecked_year.cache_clear()
