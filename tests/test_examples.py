"""Every script in examples/ runs as written, without a deprecated call."""

import runpy
from pathlib import Path

import pytest

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.py"))


@pytest.mark.filterwarnings("ignore::UserWarning")
@pytest.mark.parametrize("script", EXAMPLES, ids=[p.name for p in EXAMPLES])
def test_example_runs(script: Path, tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    runpy.run_path(str(script), run_name="__main__")
