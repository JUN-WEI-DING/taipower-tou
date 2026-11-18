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


def deprecated(old: str, new: str) -> None:
    """Warn that old goes away in 0.4.0, and what to write instead."""
    warn(f"{old} will be removed in 0.4.0. {new}", DeprecationWarning)


def unused_calendar_args(cache_dir: object, api_timeout: object) -> None:
    """Warn when a caller passes cache_dir or api_timeout, which do nothing."""
    if cache_dir is not None or api_timeout is not None:
        deprecated(
            "cache_dir and api_timeout, which have no effect,",
            "Leave them out.",
        )
