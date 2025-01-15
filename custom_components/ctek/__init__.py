"""Custom integration to integrate ctek "smart" chargers with Home Assistant."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import CtekApiClient
from .const import _LOGGER as LOGGER
from .const import DOMAIN
from .coordinator import CtekDataUpdateCoordinator
from .data import CtekData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from .data import CtekConfigEntry
    from .ws import WebSocketClient

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: CtekConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    LOGGER.setLevel(entry.options.get("log_level", "INFO"))
    hass.data.setdefault(DOMAIN, {})
    coordinator = CtekDataUpdateCoordinator(
        hass=hass,
        update_interval=timedelta(hours=1),
        always_update=False,
        config_entry=entry,
    )

    entry.runtime_data = CtekData(
        client=CtekApiClient(
            hass=hass,
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            client_id=entry.data["client_id"],
            client_secret=entry.data["client_secret"],
            session=async_get_clientsession(hass),
            refresh_token=await coordinator.get_token(),
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    if hass.data[DOMAIN].get(entry.entry_id, None) is None:
        hass.data[DOMAIN][entry.entry_id] = {}

    if entry.state == ConfigEntryState.SETUP_IN_PROGRESS:
        # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
        await coordinator.async_config_entry_first_refresh()
    else:
        # Handle the case where the entry is already loaded
        await coordinator.async_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register service
    async def handle_refresh(call: ServiceCall) -> Any:
        """Handle the service call."""
        try:
            await coordinator.async_refresh()
        except Exception as ex:
            msg = "API call failed"
            LOGGER.error("%s: %s", msg, ex)
            raise HomeAssistantError(msg) from ex
        else:
            if call.return_response:
                return True

    hass.services.async_register(
        DOMAIN,
        "force_refresh",
        handle_refresh,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
            }
        ),
    )

    async def handle_send_command(call: ServiceCall) -> Any:
        """Handle the service call."""
        command = call.data["command"]

        device_registry = dr.async_get(hass)
        device_ids = call.data[ATTR_DEVICE_ID]

        for device_id in device_ids:
            device = device_registry.async_get(device_id)
            if device is not None and coordinator.device_entry.id == device_id:
                try:
                    # Your API call implementation
                    result = await coordinator.send_command(command=command)
                    # hass.data[DOMAIN]["api"].call_endpoint(endpoint, payload)
                except Exception as ex:
                    LOGGER.error("API call failed: %s", ex)
                    msg = f"API call failed: {ex}"
                    raise HomeAssistantError(msg) from ex
                else:
                    LOGGER.debug("Got result: %s", result)
                    if call.return_response:
                        return result
        return None

    hass.services.async_register(
        domain=DOMAIN,
        service="send_command",
        service_func=handle_send_command,
        schema=vol.Schema(
            {
                vol.Required("command"): cv.string,
                vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
            }
        ),
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: CtekConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    LOGGER.info(f"Unloading {DOMAIN} integration")

    client: WebSocketClient | None = hass.data[DOMAIN][entry.entry_id][
        "websocket_client"
    ]
    # Cleanup code, close connections, etc.
    if client is not None:
        await client.stop()
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True


async def async_reload_entry(
    hass: HomeAssistant,
    entry: CtekConfigEntry,
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
