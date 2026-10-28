"""Error taxonomy for the TOU calculator."""

from __future__ import annotations


class PowerKitError(Exception):
    """Base class for all domain errors."""


class CalendarError(PowerKitError):
    """Raised for a year outside TaiwanCalendar's 2014-2100, or a date type a
    calendar cannot read."""


class UncheckedYearWarning(UserWarning):
    """Off-peak days for a year after the last Taipower calendar checked."""


class UncheckedPriceWarning(UserWarning):
    """Usage dated outside the period the bundled price table covers."""


class PartialPeriodWarning(UserWarning):
    """A bill covers only part of its calendar months."""


class TariffError(PowerKitError):
    """Raised for a custom schedule time that does not parse, or when pandas is
    missing."""


class InvalidUsageInput(PowerKitError):
    """Raised for usage or demand_kw no bill can read, such as an empty series,
    a negative kWh, or two readings at one timestamp."""


class MissingRequiredInput(PowerKitError):
    """Raised for a 高壓 or 特高壓 bill without a contract, and in strict mode
    for a bill without the contract or meter its plan bills on."""


class InvalidBillingInput(PowerKitError, ValueError):
    """Raised when a BillingInputs field has a value no bill can have, such as
    a negative 契約容量 or a 功率因數 above 100, and in strict mode for a
    contract_capacities key the plan does not bill."""


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
