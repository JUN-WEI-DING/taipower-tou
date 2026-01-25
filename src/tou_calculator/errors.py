"""Error taxonomy for the TOU calculator."""

from __future__ import annotations


class PowerKitError(Exception):
    """Base class for all domain errors."""


class CalendarError(PowerKitError):
    """Calendar-related failures."""


class TariffError(PowerKitError):
    """Tariff-related failures."""


class InvalidUsageInput(PowerKitError):
    """Raised when usage inputs are missing or invalid."""
