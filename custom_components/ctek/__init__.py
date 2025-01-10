"""Custom integration to integrate ctek "smart" chargers with Home Assistant."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import CtekApiClient
from .const import DOMAIN, LOGGER
from .coordinator import CtekDataUpdateCoordinator
from .data import CtekData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

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
    hass.data.setdefault(DOMAIN, {})
    coordinator = CtekDataUpdateCoordinator(
        hass=hass,
        update_interval=timedelta(hours=1),
        always_update=False,
        config_entry=entry,
    )
    entry.runtime_data = CtekData(
        client=CtekApiClient(
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            client_id=entry.data["client_id"],
            client_secret=entry.data["client_secret"],
            session=async_get_clientsession(hass),
            refresh_token=entry.data.get("refresh_token", None),
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    async def shutdown_listener(event) -> None:  # type: ignore[no-untyped-def] # noqa: ARG001, ANN001
        LOGGER.info(f"Shutting down {DOMAIN} integration")
        # Cleanup code, close connections, etc.
        # Store current refresh token to avoid login on startup
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                "refresh_token": entry.runtime_data.client.get_refresh_token(),
            },
        )

    if hass.data[DOMAIN].get(entry.entry_id, None) is None:
        hass.data[DOMAIN][entry.entry_id] = {}

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register the shutdown listener
    hass.bus.async_listen_once("homeassistant_stop", shutdown_listener)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: CtekConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    client: WebSocketClient = hass.data[DOMAIN][entry.entry_id]["websocket_client"]
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
