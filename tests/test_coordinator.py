"""Coordinator service call re-auth tests."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.util.dt import DEFAULT_TIME_ZONE

from custom_components.ctek.api import CtekApiClientAuthenticationError
from custom_components.ctek.const import DOMAIN
from custom_components.ctek.coordinator import CtekDataUpdateCoordinator


@pytest.fixture
def coordinator(hass):
    """Minimal coordinator with mocked dependencies."""
    entry = MagicMock()
    entry.options = {"enable_quirks": False}
    entry.data = {
        "username": "u",
        "password": "p",
        "client_id": "c",
        "client_secret": "s",
        "device_id": "dev1",
    }
    entry.runtime_data.client = AsyncMock()

    with patch(
        "custom_components.ctek.coordinator.TimestampDataUpdateCoordinator.__init__",
        return_value=None,
    ):
        coord = CtekDataUpdateCoordinator.__new__(CtekDataUpdateCoordinator)
        coord.hass = hass
        coord.config_entry = entry
        coord.device_id = "dev1"
        coord.data = {
            "device_status": {
                "connected": True,
                "connectors": {
                    "1": {
                        "current_status": MagicMock(),
                        "has_active_schedule": False,
                    }
                },
            }
        }
        coord.logger = MagicMock()
        coord._timer = None
    return coord


async def test_send_command_triggers_reauth_on_auth_failure(coordinator):
    """send_command must trigger re-auth on CtekApiClientAuthenticationError."""
    coordinator.config_entry.runtime_data.client.send_command = AsyncMock(
        side_effect=CtekApiClientAuthenticationError("bad token")
    )

    with pytest.raises(CtekApiClientAuthenticationError):
        await coordinator.send_command("REBOOT")

    coordinator.config_entry.async_start_reauth.assert_called_once_with(
        coordinator.hass
    )


async def test_start_charge_triggers_reauth_on_auth_failure(coordinator):
    """start_charge must trigger re-auth on CtekApiClientAuthenticationError."""
    with (
        patch.object(
            coordinator,
            "set_config",
            AsyncMock(side_effect=CtekApiClientAuthenticationError("bad token")),
        ),
        pytest.raises(CtekApiClientAuthenticationError),
    ):
        await coordinator.start_charge(connector_id=1)

    coordinator.config_entry.async_start_reauth.assert_called_once_with(
        coordinator.hass
    )


async def test_start_ws_recovers_when_existing_client_stop_raises(coordinator, hass):
    """A dead/failed WS client must not block creating a fresh one.

    Regression: when ws._run() ended with an exception, every subsequent
    coordinator update would re-raise it via client.stop() -> await self._task,
    leaving the same dead client in hass.data forever.
    """
    hass.data[DOMAIN] = {coordinator.config_entry.entry_id: {}}

    dead_client = MagicMock()
    dead_client.running = AsyncMock(return_value=False)
    err_msg = "dead task re-raised"
    dead_client.stop = AsyncMock(side_effect=RuntimeError(err_msg))

    bucket = hass.data[DOMAIN][coordinator.config_entry.entry_id]
    bucket["websocket_client"] = dead_client
    # Older than 5-minute throttle so start_ws will try to replace it.
    bucket["websocket_client_start"] = datetime.now(tz=DEFAULT_TIME_ZONE) - timedelta(
        minutes=10
    )

    new_client = MagicMock()
    new_client.start = AsyncMock()

    with patch(
        "custom_components.ctek.coordinator.WebSocketClient", return_value=new_client
    ):
        await coordinator.start_ws()

    dead_client.stop.assert_awaited_once()
    new_client.start.assert_awaited_once()
    assert bucket["websocket_client"] is new_client


async def test_unload_calls_token_listener_unsub(coordinator):
    """coordinator.unload must release the token-bus listener captured at setup.

    Regression: _async_setup called bus.async_listen() but discarded the unsub.
    Each reload accumulated another handler; the orphaned coordinator kept
    receiving events and writing to its old store.
    """
    unsub = MagicMock()
    coordinator._unsub_token_listener = unsub
    coordinator._store = MagicMock()
    coordinator._store.async_save = AsyncMock()
    coordinator._data = {}

    await coordinator.unload()

    unsub.assert_called_once()


async def test_async_setup_captures_token_listener_unsub(coordinator):
    """_async_setup must store the unsub returned by bus.async_listen."""
    fake_unsub = MagicMock()
    coordinator.hass = MagicMock()
    coordinator.hass.bus.async_listen = MagicMock(return_value=fake_unsub)

    with patch.object(coordinator, "init_data", AsyncMock(return_value=True)):
        await coordinator._async_setup()

    assert coordinator._unsub_token_listener is fake_unsub


async def test_stop_charge_triggers_reauth_on_auth_failure(coordinator):
    """stop_charge must trigger re-auth on CtekApiClientAuthenticationError."""
    coordinator.config_entry.runtime_data.client.stop_charge = AsyncMock(
        side_effect=CtekApiClientAuthenticationError("bad token")
    )

    with pytest.raises(CtekApiClientAuthenticationError):
        await coordinator.stop_charge(connector_id=1)

    coordinator.config_entry.async_start_reauth.assert_called_once_with(
        coordinator.hass
    )
