"""DataUpdateCoordinator for ctek."""

from __future__ import annotations

import copy
import json
from typing import TYPE_CHECKING, Any

from dateutil.parser import ParserError, parse

from homeassistant.components.ctek.types import ChargeStateEnum
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

from .api import CtekApiClientAuthenticationError, CtekApiClientError
from .const import DOMAIN, LOGGER, WS_URL

if TYPE_CHECKING:
    from datetime import timedelta

    from homeassistant.core import HomeAssistant

    from .data import CtekConfigEntry

from .data import ChargingSessionType, ConnectorType, DataType
from .ws import WebSocketClient


class CtekDataUpdateCoordinator(
    TimestampDataUpdateCoordinator[DataType]  # type: ignore[misc]
):
    """Class to manage fetching data from the API."""

    config_entry: CtekConfigEntry

    data: DataType

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: CtekConfigEntry,
        update_interval: timedelta,
        *,
        always_update: bool = False,
    ) -> None:
        """Initialize the coordinator."""
        self.config_entry = config_entry
        self.device_id = config_entry.data[CONF_DEVICE_ID]
        self.ws_connected: bool = False
        self.device_entry: dr.DeviceEntry
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN} {config_entry.data[CONF_DEVICE_ID]} DataUpdateCoordinator",
            update_interval=update_interval,
            always_update=always_update,
            config_entry=config_entry,
        )

    async def async_unload_entry(
        self, hass: HomeAssistant, entry: CtekConfigEntry
    ) -> bool:
        """Unload a config entry."""
        client = hass.data[DOMAIN][entry.entry_id].get("websocket_client")
        if client:
            await client.stop()
        return True

    async def _async_setup(self) -> bool:
        """First run. Set up the data from the API and create device."""
        try:
            devices = await self.config_entry.runtime_data.client.list_devices()
            d = devices.get("data", [])
            for device in devices.get("data", []):
                if self.device_id != device["device_id"]:
                    continue

                self.data = self.parse_data(d)

                self.data["configs"] = (
                    (
                        await self.config_entry.runtime_data.client.get_configuration(
                            device_id=device["device_id"]
                        )
                    )
                    .get("data", {})
                    .get("configurations", {})
                )

                if self.hass.data.get(DOMAIN) is None:
                    self.hass.data[DOMAIN] = {}

                device_registry = dr.async_get(self.hass)
                tmp = device_registry.async_get_or_create(
                    config_entry_id=self.config_entry.entry_id,
                    identifiers={(DOMAIN, self.data["device_id"])},
                    manufacturer="CTEK",
                    name=device["device_alias"],
                    model=device["model"],
                    model_id=device["standardized_model"],
                    sw_version=device["firmware_id"],
                    hw_version=device["hardware_id"],
                    connections={
                        (
                            dr.CONNECTION_NETWORK_MAC,
                            device["device_info"]["mac_address"],
                        )
                    },
                )
                self.device_entry = tmp
                return True
        except CtekApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except CtekApiClientError as exception:
            raise UpdateFailed(exception) from exception

        return False

    async def _async_update_data(self) -> Any:
        """Update data via library."""

        async def ws_message(message: str) -> None:
            # Process the incoming message
            data = json.loads(message)
            new_data: DataType = copy.deepcopy(self.data)
            if data.get("type") == "chargingSessionSummary":
                LOGGER.debug(f"Charging session summary: {message}")
                sessData: ChargingSessionType = {
                    "device_id": data.get("device_id"),
                    "transaction_id": data.get("transaction_id"),
                    "device_online": data.get("device_online"),
                    "last_updated_time": None
                    if data.get("last_update_time", None) in ("", None)
                    else parse(data.get("last_update_time")),
                    "momentary_current": data.get("momentary_current"),
                    "momentary_power": data.get("momentary_power"),
                    "momentary_voltage": data.get("momentary_voltage"),
                    "ongoing_transaction": data.get("ongoing_transaction"),
                    "start_time": None
                    if data.get("start_time", None) in ("", None)
                    else parse(data.get("start_time")),
                    "type": data.get("type"),
                    "watt_hours_consumed": data.get("watt_hours_consumed"),
                }
                if new_data["charging_session"] is None:
                    new_data["charging_session"] = sessData
                else:
                    new_data["charging_session"].update(sessData)
            elif data.get("type") == "connectorStatus":
                LOGGER.debug(f"Status update: {message}")
                c = copy.deepcopy(
                    self.data["device_status"]["connectors"][str(data.get("id"))]
                )
                c["update_date"] = None if data.get("updateDate", None) in (None, "") else parse(data.get("updateDate"))
                c["status_reason"] = data.get("statusReason")
                c["current_status"] = data.get("status")
                c["start_date"] = None if data.get("startDate") in (None, "") else parse(data.get("startDate"))
                new_data["device_status"]["connectors"][str(data.get("id"))] = c
            else:
                LOGGER.error(f"Not implemented: {message}")

            self.async_set_updated_data(new_data)

        try:
            devices = await self.config_entry.runtime_data.client.list_devices()

            configs = (
                (
                    await self.config_entry.runtime_data.client.get_configuration(
                        device_id=self.device_id
                    )
                )
                .get("data", {})
                .get("configurations", {})
            )

            d = devices.get("data", [])
            ret = copy.copy(self.data)
            ret.update(self.parse_data(d))
            ret.update({"configs": configs})

            LOGGER.debug(ret)

            # Subscribe to updates via websocket
            client = self.hass.data[DOMAIN][self.config_entry.entry_id].get(
                "websocket_client"
            )
            if client is None:
                websocket_url = f"{WS_URL}{self.device_id}"
                client = WebSocketClient(
                    hass=self.hass,
                    url=websocket_url,
                    entry=self.config_entry,
                    callback=ws_message,
                )

                # Start the WebSocket connection
                await client.start()

                # Store the client instance
                self.hass.data[DOMAIN][self.config_entry.entry_id]["websocket_client"] = (
                    client
                )

        # TODO: fetch charging schedules
        except CtekApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except CtekApiClientError as exception:
            raise UpdateFailed(exception) from exception
        return ret

    def get_property(self, key: str) -> str | bool | int | None:  # noqa: PLR0911
        """Get property value."""
        if key.startswith("configs."):
            return self.get_configuration(key)

        # FIXME: replace with string split
        if key.startswith("device_status.connected"):
            return bool(self.data.get("device_status", {}).get("connected", False))
        if key.startswith("device_status.connectors."):
            connector = key.removeprefix("device_status.connectors.")[0]
            key = key.removeprefix(f"device_status.connectors.{connector}.")
            if key in self.data["device_status"]["connectors"][str(connector)]:
                return self.data["device_status"]["connectors"][str(connector)][key]  # type: ignore[literal-required,no-any-return]
            return None

        if key.startswith("firmware_update."):
            key = key.removeprefix("firmware_update.")
            if key in self.data["firmware_update"]:
                return self.data["firmware_update"][key]  # type: ignore[literal-required,no-any-return]
            return None

        if key.startswith("charging_session."):
            key = key.removeprefix("charging_session.")
            if (
                self.data["charging_session"] is not None
                and key in self.data["charging_session"]
            ):
                return self.data["charging_session"][key]  # type: ignore[literal-required,no-any-return]
            return None

        if key in self.data:
            return self.data[key]  # type: ignore[literal-required,no-any-return]
        LOGGER.debug(f"Property {key} not found")
        return None

    async def set_config(self, name: str, value: str) -> None:
        """Post a configuration change to the chager."""
        # TODO: Don't try to update read-only values
        if name.startswith("configs."):
            name = name.replace("configs.", "")

        await self.config_entry.runtime_data.client.set_config(
            name=name, device_id=self.device_id, value=value
        )

        conf = (
            (
                await self.config_entry.runtime_data.client.get_configuration(
                    device_id=self.device_id
                )
            )
            .get("data", {})
            .get("configurations", {})
        )

        new_data = self.data
        new_data["configs"] = conf
        self.async_set_updated_data(new_data)

    def parse_data(self, data: list) -> DataType:
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
        for d in data:
            if d["device_id"] == self.device_id:
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
                    "connectors": self.parse_connectors(
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

    def parse_connectors(self, connectors: list) -> dict[str, ConnectorType]:
        """Parse connector related data."""
        ret = {}
        for c in connectors:
            if ret.get(str(c["id"]), None) is not None:
                old: ConnectorType = copy.deepcopy(ret[str(c["id"])])
            else:
                old = None
            new: ConnectorType = {
                "current_status": c.get("current_status"),
                "start_date": None if c.get("start_date") in (None, "") else parse(c.get("start_date")),
                "status_reason": c.get("status_reason"),
                "update_date": None if c.get("update_date") in (None, "") else parse(c.get("update_date")),
                "relative_time": c.get("relative_time"),
                "has_schedule": c.get("has_schedule"),
                "has_active_schedule": c.get("has_active_schedule"),
                "has_overridden_schedule": c.get("has_overridden_schedule"),
            }
            ret[str(c["id"])] = old.update(new) if old is not None else new
        return ret

    def get_configuration(self, key: str) -> str | int | None:
        """Get configuration value."""
        if key.startswith("configs."):
            key = key.replace("configs.", "")
        for c in self.data["configs"]:
            if c["key"] == key:
                return c["value"]
        LOGGER.error(f"Configuration key {key} not found")
        return None

    def update_configuration(
        self, key: str, value: str, *, ret: bool = False
    ) -> DataType | None:
        """Update configuration value."""
        if key.startswith("configs."):
            key = key.replace("configs.", "")
        tmp: DataType = copy.deepcopy(self.data)
        found = False
        for c in tmp["configs"]:
            if c["key"] == key:
                c["value"] = value
                found = True
                break
        if not found:
            err_str = f"Configuration key {key} not found"
            raise ValueError(err_str)
        if ret:
            return tmp
        self.data = tmp
        return None

    def update_configurations(self, values: dict) -> None:
        """Update configuration value."""
        for c in values:
            self.update_configuration(c.get("key"), c.get("value"))

    async def start_charge(self, connector_id: int) -> None:
        """Logic for starting a charge."""
        await self.config_entry.runtime_data.client.start_charge(
            device_id=self.device_id,
            connector_id=connector_id,
            resume_charging=self.data.get("device_status", {})
            .get("connectors", {})
            .get(str(connector_id), {})
            .get("current_status")
            == ChargeStateEnum.SUSPENDED_EVSE.value,
        )
        # Check connector state
        # override schedule?
        # set meter value reporting to 30 s?
        # send start command

    async def stop_charge(self, connector_id: int) -> None:
        """Logic for stopping a charge."""
        LOGGER.info(f"Stopping charge on connector {connector_id}")
        # Check connector state
        await self.config_entry.runtime_data.client.stop_charge(
            device_id=self.device_id,
            connector_id=connector_id,
            resume_schedule=self.data.get("device_status", {}).get("connectors", {}).get(str(connector_id), {}).get("has_active_schedule", False)
            .get("connectors", {})
            .get(str(connector_id), {})
            .get("current_status")
            == ChargeStateEnum.SUSPENDED_EVSE.value,
        )
