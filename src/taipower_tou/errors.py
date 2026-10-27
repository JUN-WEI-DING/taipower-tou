"""Error taxonomy for the TOU calculator."""

from __future__ import annotations


class PowerKitError(Exception):
    """Base class for all domain errors."""


class CalendarError(PowerKitError):
    """Calendar-related failures."""


class UncheckedYearWarning(UserWarning):
    """Off-peak days for a year after the last Taipower calendar checked."""


class UncheckedPriceWarning(UserWarning):
    """Usage dated outside the period the bundled price table covers."""


class TariffError(PowerKitError):
    """Tariff-related failures."""


class InvalidUsageInput(PowerKitError):
    """Raised when usage inputs are missing or invalid."""


class MissingRequiredInput(PowerKitError):
    """Raised when required inputs for a plan are missing.

    This is raised when a plan requires specific inputs (e.g., contract capacity
    for high voltage plans) but they are not provided in BillingInputs.
    """


class InvalidBasicFeeInput(PowerKitError):
    """Raised when basic_fee_inputs contains invalid keys or values.

    In strict mode, this ensures users only provide valid fee labels for
    their selected plan.
    """
