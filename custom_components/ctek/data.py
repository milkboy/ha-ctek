"""Custom types for ctek."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from homeassistant.loader import Integration

    from .api import CtekApiClient
    from .coordinator import CtekDataUpdateCoordinator
    from .types import ChargeStateEnum, StatusReasonEnum

type CtekConfigEntry = ConfigEntry[CtekData]


@dataclass
class CtekData:
    """Data for the CTEK integration."""

    client: CtekApiClient
    coordinator: CtekDataUpdateCoordinator
    integration: Integration


class FirmwareUpdateType(TypedDict):
    """Firmware update related data."""

    update_available: bool


class DeviceInfoType(TypedDict):
    """Misc device info."""

    mac_address: str
    passkey: str


class ChargingSessionType(TypedDict):
    """Charging session data."""

    transaction_id: int


class ConfigsType(TypedDict):
    """Configs data type."""

    key: str
    value: str
    read_only: bool


class ConnectorType(TypedDict):
    """Connector data type."""

    # TODO: should the dates be handled as dates?

    current_status: list[ChargeStateEnum]
    update_date: str
    status_reason: StatusReasonEnum
    start_date: str
    relative_time: str | None
    has_schedule: bool | None
    has_active_schedule: bool | None
    has_overridden_schedule: bool | None


class ThirdPartyOcppStatusType(TypedDict):
    """More or less unknown stuff..."""

    external_ocpp: bool


class DeviceStatusType(TypedDict):
    """Connector data type."""

    connected: bool
    connectors: dict[str, ConnectorType]
    load_balancing_onboarded: bool
    third_party_ocpp_status: ThirdPartyOcppStatusType


class DataType(TypedDict):
    """Schema for the data."""

    device_id: str
    device_alias: str | None
    device_type: str
    hardware_id: str
    firmware_id: str
    model: str
    standardized_model: str
    number_of_connectors: int
    firmware_version: str
    has_schedules: bool
    owner: bool
    configs: list[ConfigsType]
    charging_session: ChargingSessionType | None
    device_status: DeviceStatusType
    device_info: DeviceInfoType
    firmware_update: FirmwareUpdateType
