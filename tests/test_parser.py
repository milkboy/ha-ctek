"""Message parser tests."""

from copy import deepcopy
from datetime import datetime

import pytest
from homeassistant.util.dt import DEFAULT_TIME_ZONE

from custom_components.ctek.data import DataType
from custom_components.ctek.enums import ChargeStateEnum, StatusReasonEnum
from custom_components.ctek.parser import parse_connectors, parse_data, parse_ws_message


@pytest.fixture
def faulted_connector():
    return {
        "id": "1",
        "current_status": "Faulted",
        "status_reason": "GroundFailure",
        "start_date": "2025-01-20T12:00:00Z",
        "update_date": "2025-01-20T12:05:00Z",
    }


@pytest.fixture
def connector_status_error():
    return {
        "id": "1",
        "status": "Unavailable",
        "statusReason": "GroundFailure",
        "startDate": "2025-01-20T12:00:00Z",
        "updateDate": "2025-01-20T12:05:00Z",
        "stateLocalizeKey": "maintenance",
        "type": "connectorStatus",
    }


@pytest.fixture
def basic_device_data():
    return {
        "device_id": "test_device",
        "device_alias": "Test Charger",
        "device_type": "HOME",
        "hardware_id": "HW123",
        "firmware_id": "FW123",
        "model": "Test Model",
        "standardized_model": "TEST-1",
        "number_of_connectors": 1,
        "firmware_version": "1.0.0",
        "device_status": {
            "connected": True,
            "connectors": {},
            "load_balancing_onboarded": False,
            "third_party_ocpp_status": {"external_ocpp": False},
        },
        "firmware_update": {"update_available": False},
        "has_schedules": False,
        "device_info": {"mac_address": "00:11:22:33:44:55", "passkey": "123456"},
        "owner": True,
    }


@pytest.fixture
def charging_session_message():
    return {
        "type": "chargingSessionSummary",
        "device_id": "test_device",
        "transaction_id": "123",
        "device_online": True,
        "last_update_time": "2025-01-20T12:05:00Z",
        "momentary_current": 16.0,
        "momentary_power": 3.7,
        "momentary_voltage": 230.0,
        "ongoing_transaction": True,
        "start_time": "2025-01-20T12:00:00Z",
        "watt_hours_consumed": 1000,
    }


@pytest.fixture
def connector_status_message_charging():
    return {
        "type": "connectorStatus",
        "id": "1",
        "status": "Charging",
        "updateDate": "2025-01-20T12:05:00Z",
        "statusReason": "NoError",
    }


def test_parse_connectors_basic(faulted_connector):
    """Test basic connector parsing."""
    faulted_connector["current_status"] = "Available"
    faulted_connector["start_date"] = "2025-01-20T10:47:53.12345678"
    faulted_connector["start_date"] = "2025-01-20T11:47:53.77520805"

    result = parse_connectors([faulted_connector])

    assert "1" in result
    assert result["1"]["current_status"] == ChargeStateEnum.available
    assert isinstance(result["1"]["start_date"], datetime)
    assert isinstance(result["1"]["update_date"], datetime)
    assert result["1"]["state_localize_key"] == ""


def test_parse_connectors_with_reason(connector_status_error):
    """Test connector parsing with status reason."""
    result = parse_connectors([connector_status_error])

    assert result["1"]["status_reason"] == StatusReasonEnum.ground_failure
    assert result["1"]["state_localize_key"] == "maintenance"


def test_parse_data_basic(basic_device_data):
    """Test basic data parsing."""
    device_id = "test_device"
    updated_data = deepcopy(basic_device_data)
    result = parse_data(basic_device_data, device_id, [updated_data])

    assert result["device_id"] == device_id
    assert result["device_alias"] == "Test Charger"
    assert result["device_type"] == "HOME"
    assert result["hardware_id"] == "HW123"
    assert result["device_status"]["connected"] is True
    assert result["owner"] is True


def test_parse_ws_message_charging_session(charging_session_message, basic_device_data):
    """Test parsing websocket charging session message."""
    device_id = "test_device"

    result = parse_ws_message(charging_session_message, device_id, basic_device_data)

    assert result["charging_session"] is not None
    assert result["charging_session"]["transaction_id"] == "123"
    assert result["charging_session"]["momentary_power"] == 3.7
    assert result["charging_session"]["watt_hours_consumed"] == 1000


def test_parse_ws_message_charging_session_update(
    charging_session_message, basic_device_data
):
    """Test parsing websocket charging session message."""
    device_id = "test_device"
    basic_device_data["charging_session"] = {
        "transaction_id": charging_session_message.get("transaction_id"),
        "momentary_powewr": 1.2,
        "watt_hours_consumed": 700,
    }

    result = parse_ws_message(charging_session_message, device_id, basic_device_data)

    assert result["charging_session"] is not None
    assert result["charging_session"]["transaction_id"] == "123"
    assert result["charging_session"]["momentary_power"] == 3.7
    assert result["charging_session"]["watt_hours_consumed"] == 1000


def test_parse_ws_message_connector_status_new(
    connector_status_message_charging, basic_device_data
):
    """Test parsing websocket connector status message."""
    device_id = "test_device"

    result = parse_ws_message(
        connector_status_message_charging, device_id, basic_device_data
    )

    assert (
        result["device_status"]["connectors"]["1"]["current_status"]
        == ChargeStateEnum.charging
    )


def test_parse_ws_message_connector_update(
    connector_status_message_charging, basic_device_data: DataType
):
    """Test parsing websocket connector status message."""
    device_id = "test_device"

    basic_device_data["device_status"] = {
        "connected": False,
        "connectors": {
            "1": {
                "current_status": ChargeStateEnum.offline,
                "update_date": datetime.now(tz=DEFAULT_TIME_ZONE),
                "status_reason": StatusReasonEnum.unknown,
                "start_date": None,
                "state_localize_key": "",
            }
        },
        "load_balancing_onboarded": False,
        "third_party_ocpp_status": {"external_ocpp": False},
    }

    result = parse_ws_message(
        connector_status_message_charging, device_id, basic_device_data
    )

    assert (
        result["device_status"]["connectors"]["1"]["current_status"]
        == ChargeStateEnum.charging
    )
    assert (
        result["device_status"]["connectors"]["1"]["status_reason"]
        == StatusReasonEnum.no_error
    )
