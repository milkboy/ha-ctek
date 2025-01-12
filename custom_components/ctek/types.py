"""Data types..."""

from enum import Enum


class ChargeStateEnum(Enum):
    """Enumeration of possible charge states."""

    AVAILABLE = "Available"
    CHARGING = "Charging"
    FINISHING = "Finishing"
    PREPARING = "Preparing"
    SUSPENDED_EVSE = "SuspendedEVSE"
    SUSPENDED_EV = "SuspendedEV"


class StatusReasonEnum(Enum):
    """Status reason enum."""

    NO_ERROR = "NoError"
    # FIXME: Add missing values
