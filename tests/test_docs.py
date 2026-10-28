"""The Python examples in the docs run as written."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
DOCS = ["README.md", "docs/api_zh.md"]
FENCE = re.compile(r"^```(python|csv)\n(.*?)^```", re.M | re.S)


@pytest.mark.parametrize("doc", DOCS)
def test_python_blocks_run_in_order(doc, tmp_path, monkeypatch):
    """Blocks share one namespace, like a reader pasting them into one session.

    A csv block is saved under the last *.csv name the text gives before it.
    """
    text = (ROOT / doc).read_text("utf-8")
    monkeypatch.chdir(tmp_path)
    namespace: dict = {}
    for fence in FENCE.finditer(text):
        before = text[: fence.start()]
        if fence.group(1) == "csv":
            name = re.findall(r"`([\w.-]+\.csv)`", before)[-1]
            (tmp_path / name).write_text(fence.group(2), "utf-8")
            continue
        line = before.count("\n") + 2
        exec(compile(fence.group(2), f"{doc}:{line}", "exec"), namespace)
