"""Custom types for ctek."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict, TypeGuard

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.loader import Integration

    from .api import CtekApiClient
    from .coordinator import CtekDataUpdateCoordinator
    from .enums import ChargeStateEnum, StatusReasonEnum

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

    device_id: str | None
    ongoing_transaction: bool | None
    transaction_id: int | None
    watt_hours_consumed: int | None
    momentary_voltage: str | None
    momentary_power: str | None
    momentary_current: str | None
    start_time: datetime | None
    last_updated_time: datetime | None
    device_online: bool | None
    type: str | None


class ConfigsType(TypedDict):
    """Configs data type."""

    key: str
    value: str
    read_only: bool


class ConnectorScheduleType(TypedDict, total=False):
    """Extra schedule related optional fields."""

    relative_time: str | None
    has_schedule: bool | None
    has_active_schedule: bool | None
    has_overridden_schedule: bool | None


class ConnectorType(ConnectorScheduleType):
    """Connector data type."""

    current_status: ChargeStateEnum
    update_date: datetime | None
    status_reason: StatusReasonEnum
    start_date: datetime | None
    state_localize_key: str | None


class ThirdPartyOcppStatusType(TypedDict):
    """More or less unknown stuff..."""

    external_ocpp: bool


class DeviceStatusTypeOpt(TypedDict, total=False):
    """Connector data type."""

    load_balancing_onboarded: bool
    third_party_ocpp_status: ThirdPartyOcppStatusType


class DeviceStatusType(DeviceStatusTypeOpt):
    """Connector data type."""

    connected: bool
    connectors: dict[str, ConnectorType]


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


class InstructionInfoType(TypedDict):
    """Instruction info type."""

    value: str | None
    key: str | None
    firmware: str | None
    id: str | None
    units: str | None


class InstructionType(TypedDict):
    """Instruction type."""

    id: str
    user_id: int
    device_id: str
    connector_id: int
    instruction: str
    transaction_id: int
    user_id_is_owner: bool
    timeout: datetime
    info: InstructionInfoType


class InstructionResponseType(TypedDict):
    """Schema for the data."""

    device_id: str
    instruction: InstructionType
    information: dict[Any, Any]
    ocpp: dict[Any, Any]
    accepted: bool | None


class ChargingSessionSummaryWSType(TypedDict):
    """WS message for charging session data."""

    device_id: str
    ongoing_transaction: bool
    transaction_id: int
    watt_hours_consumed: int
    momentary_voltage: str
    momentary_power: str
    momentary_current: str
    start_time: str
    last_updated_time: str
    device_online: bool
    type: str


class ConnectorStatusWSType(TypedDict):
    """WS message for connector status updates."""

    updateDate: str
    statusReason: str
    id: int
    type: str
    deviceId: str
    startDate: str
    stateLocalizeKey: str
    status: str


def is_ws_charging_session_type(val: dict) -> TypeGuard[ChargingSessionSummaryWSType]:
    """Check if the message type is chargingSessionSummary."""
    return val.get("type") == "chargingSessionSummary"


def is_ws_connector_status_type(
    val: dict | ConnectorStatusWSType,
) -> TypeGuard[ConnectorStatusWSType]:
    """Check if the message type is connectorStatus."""
    return val.get("type") == "connectorStatus"
