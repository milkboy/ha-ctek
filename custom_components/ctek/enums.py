"""Data types..."""

from enum import Enum

from .const import BASE_LOGGER as LOGGER


class ChargeStateEnum(Enum):
    """Enumeration of possible charge states."""

    available = "Available"
    charging = "Charging"
    faulted = "Faulted"  # Never seen this (yet)
    finishing = "Finishing"
    offline = "Offline"
    preparing = "Preparing"
    reserved = "Reserved"  # Probably unused
    suspended_ev = "SuspendedEV"
    suspended_evse = "SuspendedEVSE"
    unavailable = "Unavailable"  # May not be used
    unknown = "Unknown"

    @staticmethod
    def find(val: str | None) -> "ChargeStateEnum":
        """Find and return the corresponding ChargeStateEnum member for the given value.

        Args:
            val (str): The value to search for, which can be either the name or
              the value of a ChargeStateEnum member.

        Returns:
            ChargeStateEnum: The corresponding ChargeStateEnum member if found.

        Raises:
            ValueError: If the given value does not correspond to any
              ChargeStateEnum member.

        """
        for state in ChargeStateEnum:
            if val in (state.value, state.name):
                return state
        msg = f"{val} is not a valid ChargeStateEnum value"
        LOGGER.warning(msg)
        return ChargeStateEnum.unknown

    def __str__(self) -> str:
        """Return the name of the ChargeStateEnum member."""
        return self.name


class StatusReasonEnum(Enum):
    """Status reason enum."""

    ground_failure = "GroundFailure"
    high_temperature = "HighTemperature"
    internal_error = "InternalError"
    no_error = "NoError"
    other_error = "OtherError"
    power_meter_failure = "PowerMeterFailure"
    unknown = "Unknown"
    weak_signal = "WeakSignal"

    @staticmethod
    def find(val: str | None) -> "StatusReasonEnum":
        """Return the corresponding StatusReasonEnum member for the given value.

        Args:
            val (str): The value to search for, which can be either the name or
              the value of a StatusReasonEnum member.

        Returns:
            StatusReasonEnum: The corresponding StatusReasonEnum member if found.

        """
        for state in StatusReasonEnum:
            if val in (state.value, state.name):
                return state
        msg = f"{val} is not a valid StatusReasonEnum value. Please report/add this."
        LOGGER.warning(msg)
        return StatusReasonEnum.unknown

    def __str__(self) -> str:
        """Return the name of the StatusReasonEnum member."""
        return self.name
