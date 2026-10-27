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


class PartialPeriodWarning(UserWarning):
    """A bill covers only part of its calendar months."""


class TariffError(PowerKitError):
    """Tariff-related failures."""


class InvalidUsageInput(PowerKitError):
    """Raised when usage inputs are missing or invalid."""


class MissingRequiredInput(PowerKitError):
    """Raised when required inputs for a plan are missing.

    This is raised when a plan requires specific inputs (e.g., contract capacity
    for high voltage plans) but they are not provided in BillingInputs.
    """


class InvalidBillingInput(PowerKitError, ValueError):
    """Raised when a BillingInputs field has a value no bill can have, such as
    a negative 契約容量 or a 功率因數 above 100."""


class InvalidBasicFeeInput(InvalidBillingInput):
    """Raised when basic_fee_inputs has a value no bill can have, such as a
    negative 裝置契約, or, in strict mode, a label the plan does not bill."""


class UnknownPlanError(PowerKitError, KeyError, ValueError):
    """Raised when a plan name matches no plan, more than one, or a removed one.

    It is also a KeyError and a ValueError, the types calculate_bill and
    tou.plan raised for an unknown plan before, so code that catches those
    keeps working.
    """

    # KeyError's str() quotes the message.
    __str__ = Exception.__str__
