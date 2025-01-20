"""Data parsers."""

import copy

from dateutil.parser import parse
from homeassistant.util.dt import DEFAULT_TIME_ZONE

from .const import _LOGGER
from .data import ChargingSessionType, ConnectorType, DataType, InstructionResponseType
from .enums import ChargeStateEnum, StatusReasonEnum

LOGGER = _LOGGER.getChild("parser")


def parse_connectors(connectors: list) -> dict[str, ConnectorType]:
    """Parse connector related data."""
    ret: dict[str, ConnectorType] = {}
    for c in connectors:
        old: ConnectorType | None = None
        new: ConnectorType
        if ret.get(str(c["id"]), None) is not None:
            old = copy.deepcopy(ret[str(c["id"])])
        if c.get("statusReason") is not None:
            new = {
                "current_status": ChargeStateEnum.find(c.get("status")),
                "start_date": None
                if c.get("startDate") in (None, "")
                else parse(c.get("startDate"))
                .astimezone(DEFAULT_TIME_ZONE)
                .replace(second=0, microsecond=0),
                "status_reason": StatusReasonEnum.find(c.get("statusReason")),
                "update_date": None
                if c.get("updateDate") in (None, "")
                else parse(c.get("updateDate")).astimezone(DEFAULT_TIME_ZONE),
                "state_localize_key": c.get("stateLocalizeKey", ""),
            }
        else:
            new = {
                "current_status": ChargeStateEnum.find(c.get("current_status")),
                "start_date": None
                if c.get("start_date", c.get("startDate")) in (None, "")
                else parse(c.get("start_date", c.get("startDate")))
                .astimezone(DEFAULT_TIME_ZONE)
                .replace(second=0, microsecond=0),
                "status_reason": StatusReasonEnum.find(
                    c.get("status_reason", c.get("statusReason"))
                ),
                "update_date": None
                if c.get("update_date", c.get("updateDate")) in (None, "")
                else parse(c.get("update_date", c.get("updateDate")))
                .astimezone(DEFAULT_TIME_ZONE)
                .replace(second=0, microsecond=0),
                "relative_time": c.get("relative_time", ""),
                "has_schedule": c.get("has_schedule", False),
                "has_active_schedule": c.get("has_active_schedule", False),
                "has_overridden_schedule": c.get("has_overridden_schedule", False),
                "state_localize_key": c.get("state_localize_key", ""),
            }

        if old is not None:
            old.update(new)
        ret[str(c["id"])] = old if old is not None else new
    return ret


def parse_data(original_data: DataType, device_id: str, data: list) -> DataType:
    """Parse data."""
    ret: DataType = {
        "device_id": "",
        "device_alias": "",
        "device_type": "",
        "hardware_id": "",
        "firmware_id": "",
        "model": "",
        "standardized_model": "",
        "number_of_connectors": 0,
        "firmware_version": "",
        "device_status": {
            "connected": False,
            "connectors": {},
            "load_balancing_onboarded": False,
            "third_party_ocpp_status": {"external_ocpp": False},
        },
        "firmware_update": {"update_available": False},
        "has_schedules": False,
        "device_info": {
            "mac_address": "",
            "passkey": "",
        },
        "owner": False,
        "configs": [],
        "charging_session": None,
    }
    if original_data is not None:
        ret.update(original_data)
    for d in data:
        if d["device_id"] == device_id:
            ret["device_id"] = d.get("device_id")
            ret["device_alias"] = d.get("device_alias")
            ret["device_type"] = d.get("device_type")
            ret["hardware_id"] = d.get("hardware_id")
            ret["firmware_id"] = d.get("firmware_id")
            ret["model"] = d.get("model")
            ret["standardized_model"] = d.get("standardized_model")
            ret["number_of_connectors"] = d.get("number_of_connectors")
            ret["firmware_version"] = d.get("firmware_version")
            ret["device_status"] = {
                "connected": d.get("device_status").get("connected"),
                "connectors": parse_connectors(
                    d.get("device_status").get("connectors")
                ),
                "load_balancing_onboarded": d.get("device_status").get(
                    "load_balancing_onboarded"
                ),
                "third_party_ocpp_status": {
                    "external_ocpp": (
                        d.get("device_status")
                        .get("third_party_ocpp_status")
                        .get("external_ocpp")
                    )
                },
            }
            ret["firmware_update"] = {
                "update_available": d.get("firmware_update").get("update_available")
            }
            ret["has_schedules"] = d.get("has_schedules")
            ret["device_info"] = {
                "mac_address": d.get("device_info").get("mac_address"),
                "passkey": d.get("device_info").get("passkey"),
            }
            ret["owner"] = d.get("owner")
            break
    return ret


def parse_ws_message(data: dict, device_id: str, old_data: DataType) -> DataType:
    """Parse a message from web socket connection."""
    if data.get("type") == "chargingSessionSummary":
        LOGGER.debug("Charging session summary: %s", data)
        if device_id != data.get("device_id"):
            LOGGER.warning("Data for wrong device received")
            return old_data
        updated = (
            None
            if data.get("last_update_time") in ("", None)
            else parse(data.get("last_update_time"))
        )
        start = (
            None
            if data.get("start_time") in ("", None)
            else parse(data.get("start_time"))
        )

        session_data: ChargingSessionType = {
            "device_id": data.get("device_id"),
            "transaction_id": data.get("transaction_id"),
            "device_online": data.get("device_online"),
            "last_updated_time": updated,
            "momentary_current": data.get("momentary_current"),
            "momentary_power": data.get("momentary_power"),
            "momentary_voltage": data.get("momentary_voltage"),
            "ongoing_transaction": data.get("ongoing_transaction"),
            "start_time": start,
            "type": data.get("type"),
            "watt_hours_consumed": data.get("watt_hours_consumed"),
        }
        prev = old_data.get("charging_session")
        if prev is None:
            old_data["charging_session"] = session_data
        else:
            prev.update(session_data)

    elif data.get("type") == "connectorStatus":
        LOGGER.debug("Status update: %s", data)
        c = copy.deepcopy(
            old_data["device_status"].get("connectors", {}).get(str(data.get("id")))
        )
        if c is None:
            c = parse_connectors([data])[str(data.get("id"))]
        else:
            c.update(parse_connectors([data])[str(data.get("id"))])
        old_data["device_status"]["connectors"][str(data.get("id"))] = c
    else:
        LOGGER.error("Not implemented: %s", data)

    return old_data


def parse_instruction_response(res: dict) -> InstructionResponseType:
    """Parse the instruction response from a given dictionary.

    Args:
        res (dict): The response dictionary containing instruction data.

    Returns:
        InstructionResponseType: A dictionary containing parsed instruction
          response data.

    """
    data: InstructionResponseType = {
        "device_id": res.get("device_id", ""),
        "information": res.get("information", {}),
        "instruction": {
            "connector_id": res.get("instruction", {}).get("connector_id"),
            "device_id": res.get("instruction", {}).get("device_id"),
            "info": {
                "firmware": res.get("instruction", {}).get("info", {}).get("firmware"),
                "id": res.get("instruction", {}).get("info", {}).get("id"),
                "key": res.get("instruction", {}).get("info", {}).get("key"),
                "units": res.get("instruction", {}).get("info", {}).get("units"),
                "value": res.get("instruction", {}).get("info", {}).get("value"),
            },
            "id": res.get("instruction", {}).get("id"),
            "instruction": res.get("instruction", {}).get("instruction"),
            "timeout": res.get("instruction", {}).get("timeout"),
            "transaction_id": res.get("instruction", {}).get("transaction_id"),
            "user_id": res.get("instruction", {}).get("user_id"),
            "user_id_is_owner": res.get("instruction", {}).get("user_id_is_owner"),
        },
        "ocpp": {},
        "accepted": res.get("accepted"),
    }

    return data
