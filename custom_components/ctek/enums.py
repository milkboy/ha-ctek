"""Data types..."""

from enum import Enum


class ChargeStateEnum(Enum):
    """Enumeration of possible charge states."""

    available = "Available"
    charging = "Charging"
    faulted = "Faulted"  # Never seen this (yet)
    finishing = "Finishing"
    preparing = "Preparing"
    reserved = "Reserved"  # Probably unused
    suspended_ev = "SuspendedEV"
    suspended_evse = "SuspendedEVSE"
    unavailable = "Unavailable"  # May not be used
    offline = "Offline"

    @staticmethod
    def find(val: str) -> "ChargeStateEnum":
        """
        Find and return the corresponding ChargeStateEnum member for the given value.

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
        raise ValueError(msg)

    def __str__(self) -> str:
        """Return the name of the ChargeStateEnum member."""
        return self.name


class StatusReasonEnum(Enum):
    """Status reason enum."""

    NO_ERROR = "NoError"
    # FIXME: Add missing values
