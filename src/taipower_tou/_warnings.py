"""Warnings that name the caller's line."""

from __future__ import annotations

import functools
import os
import sys
import warnings

_PACKAGE = os.path.dirname(os.path.abspath(__file__)) + os.sep
# A pure-Python functools wrapper, such as singledispatchmethod, can sit
# between package frames.
_FUNCTOOLS = functools.__file__


def warn(message: str, category: type[Warning]) -> None:
    """Warn at the first frame outside this package, however deep the call."""
    frame = sys._getframe(1)
    level = 2
    while frame.f_back is not None and (
        frame.f_code.co_filename.startswith(_PACKAGE)
        or frame.f_code.co_filename == _FUNCTOOLS
    ):
        frame = frame.f_back
        level += 1
    warnings.warn(message, category, stacklevel=level)
