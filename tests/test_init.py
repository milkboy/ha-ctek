"""Tests for __init__.py setup/unload/reload lifecycle."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.ctek import async_unload_entry
from custom_components.ctek.const import DOMAIN


@pytest.fixture
def mock_config_entry(hass: HomeAssistant):
    """Minimal config entry fixture."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.state = ConfigEntryState.LOADED
    entry.data = {
        "username": "user",
        "password": "pass",
        "client_id": "cid",
        "client_secret": "csec",
        "device_id": "dev1",
    }
    entry.options = {}
    entry.runtime_data = None
    return entry


async def test_unload_entry_returns_true_on_success(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """async_unload_entry must return True when platform unload succeeds."""
    hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=True,
    ) as mock_unload:
        result = await async_unload_entry(hass, mock_config_entry)

    assert result is True
    mock_unload.assert_awaited_once()


async def test_unload_entry_propagates_false_on_failure(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """async_unload_entry must propagate False when platform unload fails."""
    hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=False,
    ):
        result = await async_unload_entry(hass, mock_config_entry)

    assert result is False


async def test_unload_entry_removes_services(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Services registered during setup must be removed on unload."""
    hass.data[DOMAIN] = {mock_config_entry.entry_id: {}}

    hass.services.async_register(DOMAIN, "force_refresh", AsyncMock())
    hass.services.async_register(DOMAIN, "send_command", AsyncMock())

    assert hass.services.has_service(DOMAIN, "force_refresh")
    assert hass.services.has_service(DOMAIN, "send_command")

    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        await async_unload_entry(hass, mock_config_entry)

    assert not hass.services.has_service(DOMAIN, "force_refresh")
    assert not hass.services.has_service(DOMAIN, "send_command")
