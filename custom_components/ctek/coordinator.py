"""DataUpdateCoordinator for ctek."""

from __future__ import annotations

import copy
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from dateutil.parser import parse
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_call_from_config
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util.dt import DEFAULT_TIME_ZONE

from .api import CtekApiClientAuthenticationError, CtekApiClientError
from .const import _LOGGER, DOMAIN, WS_URL
from .enums import ChargeStateEnum

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable

    from homeassistant.components.switch import SwitchEntity
    from homeassistant.core import HomeAssistant

    from .data import CtekConfigEntry

from datetime import timedelta

from .data import ChargingSessionType, ConnectorType, DataType, InstructionResponseType
from .ws import WebSocketClient

LOGGER = _LOGGER.getChild("coordinator")


def callback(func: Callable[..., Any]) -> Callable[..., Any]:
    """Return the callback function."""
    return func


class CtekDataUpdateCoordinator(TimestampDataUpdateCoordinator[DataType]):
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
        self.device_entry: dr.DeviceEntry
        self._transaction_id: int | None = None
        self._store: Store = Store(hass, 1, f"{DOMAIN}_cache")
        self._data: dict = {}
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN} {config_entry.data[CONF_DEVICE_ID]} DataUpdateCoordinator",
            update_interval=update_interval,
            always_update=always_update,
            config_entry=config_entry,
        )
        self._timer: asyncio.TimerHandle | None = None

    async def async_unload_entry(
        self, hass: HomeAssistant, entry: CtekConfigEntry
    ) -> bool:
        """Unload a config entry."""
        self._timer = None
        client: WebSocketClient | None = hass.data[DOMAIN][entry.entry_id].get(
            "websocket_client"
        )
        if client:
            await client.stop()
        return True

    def cancel_delayed_operation(self) -> None:
        """Cancel any existing timer."""
        if self._timer:
            self._timer.cancel()
            self._timer = None

    async def start_delayed_operation(
        self, delay: int, func: Callable, **kwargs: Any
    ) -> None:
        """Start the delayed operation."""
        self.cancel_delayed_operation()

        try:
            self._timer = self.hass.loop.call_later(
                delay,
                lambda: self.hass.async_create_task(func(**kwargs)),
            )
        except Exception:
            LOGGER.exception("Failed to schedule delayed operation")

    @callback
    async def handle_tokens(self, event: Any) -> None:
        """Handle token update events."""
        if self._data.get("refresh_token") != event.data.get("refresh"):
            LOGGER.debug("Tokens updated; storing")
            self._data.update({"refresh_token": event.data.get("refresh")})
            await self._store.async_save(self._data)
        else:
            LOGGER.debug("Token not changed")

    async def get_token(self) -> str | None:
        """Retrieve the refresh token."""
        if self._data == {}:
            stored: dict | None = await self._store.async_load()
        if stored is not None:
            self._data = stored
        return self._data.get("refresh_token")

    async def init_data(self) -> bool:
        """Initialize data from the API and create device entry."""
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
        return False

    async def _async_setup(self) -> bool:
        """First run. Set up the data from the API and create device."""
        try:
            self.hass.bus.async_listen(f"{DOMAIN}_tokens_updated", self.handle_tokens)
            await self.init_data()
        except CtekApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except CtekApiClientError as exception:
            raise UpdateFailed(exception) from exception

        return False

    async def ws_message(self, message: str) -> None:
        """Process the incoming message."""
        data = json.loads(message)
        new_data: DataType = copy.deepcopy(self.data)
        if data.get("type") == "chargingSessionSummary":
            LOGGER.debug("Charging session summary: %s", message)
            if self.device_id != data.get("device_id"):
                LOGGER.warning("Data for wrong device received")
                return
            session_data: ChargingSessionType = {
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
                new_data["charging_session"] = session_data
            else:
                new_data["charging_session"].update(session_data)

        elif data.get("type") == "connectorStatus":
            LOGGER.debug("Status update: %s", message)
            c = copy.deepcopy(
                self.data["device_status"]["connectors"][str(data.get("id"))]
            )
            c.update(self.parse_connectors([data])[str(data.get("id"))])
            new_data["device_status"]["connectors"][str(data.get("id"))] = c
        else:
            LOGGER.error("Not implemented: %s", message)

        self.async_set_updated_data(new_data)

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        try:
            if self.data is None or self.device_entry is None:
                # Possibly reconfigured, so data is not there
                await self.init_data()
                await self.start_ws(force=True)
                return self.data

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

            await self.start_ws()

        # TODO: fetch charging schedules
        except CtekApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except CtekApiClientError as exception:
            raise UpdateFailed(exception) from exception
        return ret

    async def start_ws(self, *, force: bool = False) -> None:
        """Subscribe to updates via websocket."""
        client: WebSocketClient | None = self.hass.data[DOMAIN][
            self.config_entry.entry_id
        ].get("websocket_client")
        if client is not None:
            start: datetime = self.hass.data[DOMAIN][self.config_entry.entry_id].get(
                "websocket_client_start"
            )
            if (
                (datetime.now(tz=DEFAULT_TIME_ZONE) - start).total_seconds()
                < timedelta(minutes=5).seconds
                and await client.running()
                and not force
            ):
                return

            await client.stop()

        websocket_url = f"{WS_URL}{self.device_id}"
        client = WebSocketClient(
            hass=self.hass,
            url=websocket_url,
            entry=self.config_entry,
            callback=self.ws_message,
        )

        # Store the client instance
        self.hass.data[DOMAIN][self.config_entry.entry_id]["websocket_client"] = client
        self.hass.data[DOMAIN][self.config_entry.entry_id]["websocket_client_start"] = (
            datetime.now(tz=DEFAULT_TIME_ZONE)
        )

        # Start the WebSocket connection
        await client.start()

    def cable_connected(self, connector_id: int) -> bool:
        """Check if the cable is connected for a given connector ID.

        Args:
            connector_id (int): The ID of the connector to check.

        Returns:
            bool: True if the cable is connected, False otherwise.

        """
        val: ChargeStateEnum = self.data["device_status"]["connectors"][
            str(connector_id)
        ]["current_status"]
        return val not in (
            ChargeStateEnum.available,
            ChargeStateEnum.faulted,
            ChargeStateEnum.reserved,
            ChargeStateEnum.unavailable,
        )

    def get_property(  # noqa: PLR0911
        self, key: str
    ) -> str | bool | int | datetime | ChargeStateEnum | None:
        """Get property value."""
        if key.startswith("attribute."):
            key = key.removeprefix("attribute.")
            if key.startswith("cable_connected"):
                conn_id = key.removeprefix("cable_connected.")
                if conn_id.isnumeric():
                    return self.cable_connected(int(conn_id))
                LOGGER.debug("Failed to parse connector from '%s'", key)
                return None
            LOGGER.warning("Unknown property '%s' requested", key)
            return None

        if key.startswith("configs."):
            return self.get_configuration(key)

        # FIXME: replace with string split
        if key.startswith("device_status.connected"):
            return bool(self.data.get("device_status", {}).get("connected", False))
        if key.startswith("device_status.connectors."):
            connector = key.removeprefix("device_status.connectors.")[0]
            key = key.removeprefix(f"device_status.connectors.{connector}.")
            if key in self.data["device_status"]["connectors"][str(connector)]:
                return self.data["device_status"]["connectors"][str(connector)][key]  # type: ignore[literal-required]

        if key.startswith("firmware_update."):
            key = key.removeprefix("firmware_update.")
            if key in self.data["firmware_update"]:
                return self.data["firmware_update"][key]  # type: ignore[literal-required]

        if key.startswith("charging_session."):
            key = key.removeprefix("charging_session.")
            if (
                self.data["charging_session"] is not None
                and key in self.data["charging_session"]
            ):
                return self.data["charging_session"][key]  # type: ignore[literal-required]

        if key in self.data:
            return self.data[key]  # type: ignore[literal-required]
        LOGGER.debug("Property '%s' not found", key)
        return None

    async def set_config(self, name: str, value: str) -> None:
        """Post a configuration change to the chager."""
        if name.startswith("configs."):
            name = name.replace("configs.", "")
        if self.is_readonly_configuration(name):
            LOGGER.error("Configuration '%s' is read-only", name)
            return

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
        if self.data is not None:
            ret.update(self.data)
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
                    "status_reason": c.get("statusReason"),
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
                    "status_reason": c.get("status_reason", c.get("statusReason")),
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

    def get_configuration(self, key: str) -> str | int | None:
        """Get configuration value."""
        if key.startswith("configs."):
            key = key.replace("configs.", "")
        for c in self.data["configs"]:
            if c["key"] == key:
                return c["value"]
        LOGGER.error("Configuration key '%s' not found", key)
        return None

    def is_readonly_configuration(self, key: str) -> str | int | None:
        """Get configuration value."""
        if key.startswith("configs."):
            key = key.replace("configs.", "")
        for c in self.data["configs"]:
            if c["key"] == key:
                return c["read_only"]
        LOGGER.error("Configuration key '%s' not found", key)
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
        """Logic for starting a charge.

        If the charge was previously stopped, or maybe waiting for a schedule, we need
        to send a different command than if the charger is waiting for authorization.

        """
        LOGGER.info("Trying to start a charge")

        # set meter value reporting to 30 s
        await self.set_config("configs.MeterValueSampleInterval", "30")

        if self.config_entry.options["enable_quirks"]:
            LOGGER.info("Quirks enabled")

        # send start command
        # SuspendedEVSE -> needs to resume
        # Preparing -> needs authorize
        res: InstructionResponseType = (
            await self.config_entry.runtime_data.client.start_charge(
                device_id=self.device_id,
                connector_id=connector_id,
                resume_charging=self.get_connector_status_sync(
                    connector_id=connector_id
                )
                == ChargeStateEnum.suspended_evse,
            )
        )

        if not res["accepted"]:
            msg = "Charger refused or failed the request"
            LOGGER.error(msg)
            raise HomeAssistantError(msg)

        delay = 60

        async def handle_car_quirks(
            tries: int = 3, tried_quirks: list | None = None
        ) -> None:
            if tried_quirks is None:
                tried_quirks = []
            if tries > 0:
                LOGGER.info("Trying quirks. Already tried: %s", tried_quirks)
                state = self.get_connector_status_sync(connector_id)
                reboot: bool = self.config_entry.options[
                    "reboot_station_if_start_fails"
                ]
                toggle: str | None = self.config_entry.options.get(
                    "quirks_toggle_switch"
                )
                service_action: list[dict] | None = self.config_entry.options.get(
                    "quirks_call_service"  # action is name, data contains args as dict
                )

                if state in (ChargeStateEnum.suspended_evse, ChargeStateEnum.preparing):
                    LOGGER.info("Charge is not started. Trying again")
                    await self.start_delayed_operation(
                        delay=delay,
                        func=handle_car_quirks,
                        tries=tries - 1,
                        tried_quirks=tried_quirks,
                    )
                    await self.config_entry.runtime_data.client.start_charge(
                        device_id=self.device_id,
                        connector_id=connector_id,
                        resume_charging=self.get_connector_status_sync(
                            connector_id=connector_id
                        )
                        == ChargeStateEnum.suspended_evse,
                    )
                    return

                if state == ChargeStateEnum.charging:
                    LOGGER.info("Charge has started; setting MAX current")
                    await self.set_config(
                        name="configs.CurrentMaxAssignment",
                        value=str(self.get_max_current()),
                    )
                    return

                if (
                    state in (ChargeStateEnum.suspended_ev, ChargeStateEnum.preparing)
                    and toggle is not None
                    and "toggle" not in tried_quirks
                ):
                    LOGGER.warning("Toggling switch: %s", toggle)
                    tried_quirks.append("toggle")
                    await self.start_delayed_operation(
                        delay,
                        handle_car_quirks,
                        tries=tries - 1,
                        tried_quirks=tried_quirks,
                    )

                    registry = er.async_get(self.hass)
                    switch: SwitchEntity = registry.async_get(toggle)
                    switch.toggle()
                    return

                if (
                    state in (ChargeStateEnum.suspended_ev, ChargeStateEnum.preparing)
                    and service_action is not None
                    and service_action != []
                    and "service_action" not in tried_quirks
                ):
                    LOGGER.warning("Calling service: %s", service_action)
                    tried_quirks.append("service_action")
                    service_call = {
                        "service": service_action[0].get("action"),
                        "data": service_action[0].get("data", {}),
                    }

                    await self.start_delayed_operation(
                        delay,
                        handle_car_quirks,
                        tries=tries - 1,
                        tried_quirks=tried_quirks,
                    )
                    await async_call_from_config(self.hass, service_call)
                    return

                if (
                    state in (ChargeStateEnum.suspended_ev, ChargeStateEnum.preparing)
                    and reboot
                    and "reboot" not in tried_quirks
                ):
                    tried_quirks.append("reboot")
                    LOGGER.warning(
                        "Seems like charge did not start as expected; rebooting"
                    )
                    await self.send_command(command="REBOOT")
                    await self.start_delayed_operation(
                        delay=2 * delay,
                        func=handle_car_quirks,
                        tries=tries - 1,
                        tried_quirks=tried_quirks,
                    )
                    return

                LOGGER.warning("Charge not started; checking again in %ds", delay)
                await self.start_delayed_operation(
                    delay, handle_car_quirks, tries=tries - 1, tried_quirks=tried_quirks
                )
                return

            LOGGER.error("Start charge apparently failed")

        if self.config_entry.options["enable_quirks"]:
            await self.start_delayed_operation(delay=delay, func=handle_car_quirks)

    async def stop_charge(self, connector_id: int) -> bool | None:
        """Logic for stopping a charge."""
        LOGGER.info("Stopping charge on connector %s", connector_id)
        # Check connector state
        # Fixme: check that a charge is actually ongoing
        self.cancel_delayed_operation()
        status = self.get_connector_status_sync(connector_id=connector_id)
        if status not in (ChargeStateEnum.charging, ChargeStateEnum.suspended_ev):
            LOGGER.warning("Connector status is %s", status.value)

        res: InstructionResponseType = (
            await self.config_entry.runtime_data.client.stop_charge(
                device_id=self.device_id,
                connector_id=connector_id,
                resume_schedule=bool(
                    self.data.get("device_status", {})  # type: ignore[call-overload]
                    .get("connectors", {})
                    .get(str(connector_id), {})
                    .get("has_active_schedule", False)
                ),
            )
        )
        if res.get("accepted"):
            await self.async_request_refresh()
        return res.get("accepted")

    def get_connector_status_sync(self, connector_id: int) -> ChargeStateEnum:
        """Retrieve the status of a specific connector.

        Args:
            connector_id (int): The ID of the connector to retrieve the status for.

        Returns:
            ChargeStateEnum: The current status of the specified connector.

        """
        return self.data["device_status"]["connectors"][str(connector_id)][
            "current_status"
        ]

    def get_min_current(self) -> int:
        """Get the minimum supported current."""
        val = self.get_configuration("CurrentMinAssignment")
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
        return 6

    def get_max_current(self) -> int:
        """Get the maximum supported current."""
        val = self.get_configuration("CurrentMaxAssignment")
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
        return 10

    async def send_command(self, command: str) -> InstructionResponseType:
        """Send a command to the API."""
        res: InstructionResponseType = (
            await self.config_entry.runtime_data.client.send_command(
                device_id=self.device_id,
                # connector_id=connector_id,
                command=command,
            )
        )
        LOGGER.debug(res)
        return res

    async def unload(self) -> None:
        """Unload the coordinator and save the data."""
        await self._store.async_save(self._data)
