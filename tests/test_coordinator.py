"""Coordinator service call re-auth tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ctek.api import CtekApiClientAuthenticationError
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
