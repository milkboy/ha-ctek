"""Tests for __init__.py setup/unload/reload lifecycle."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.ctek import async_reload_entry, async_unload_entry
from custom_components.ctek.const import DOMAIN
from custom_components.ctek.coordinator import CtekDataUpdateCoordinator
from custom_components.ctek.data import CtekData


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


async def test_unload_entry_cleans_hass_data(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """hass.data[DOMAIN][entry_id] must be removed on unload."""
    hass.data[DOMAIN] = {mock_config_entry.entry_id: {"some_key": "some_value"}}

    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        await async_unload_entry(hass, mock_config_entry)

    assert mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})
    assert DOMAIN not in hass.data


async def test_unload_entry_cleans_hass_data_missing_domain_key(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """async_unload_entry must not raise if hass.data[DOMAIN] is absent."""
    hass.data.pop(DOMAIN, None)

    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        result = await async_unload_entry(hass, mock_config_entry)

    assert result is True


async def test_unload_entry_stops_websocket_client(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """WebSocket client must be stopped when present."""
    mock_client = AsyncMock()
    hass.data[DOMAIN] = {mock_config_entry.entry_id: {"websocket_client": mock_client}}

    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        await async_unload_entry(hass, mock_config_entry)

    mock_client.stop.assert_awaited_once()


async def test_reload_entry_delegates_to_config_entries(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """async_reload_entry must schedule a reload via async_schedule_reload."""
    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        async_reload_entry(hass, mock_config_entry)

    mock_reload.assert_called_once_with(mock_config_entry.entry_id)


def test_coordinator_has_no_async_unload_entry() -> None:
    """coordinator.async_unload_entry is dead code and must not exist."""
    assert not hasattr(CtekDataUpdateCoordinator, "async_unload_entry")


@pytest.fixture
def mock_coordinator():
    """Mock coordinator with cancel_delayed_operation and unload."""
    coordinator = MagicMock()
    coordinator.unload = AsyncMock()
    return coordinator


@pytest.fixture
def mock_config_entry_with_coordinator(hass: HomeAssistant, mock_coordinator):
    """Config entry with runtime_data carrying a mock coordinator."""
    entry = MagicMock()
    entry.entry_id = "test_entry_with_coordinator"
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
    entry.runtime_data = CtekData(
        coordinator=mock_coordinator,
        client=MagicMock(),
        integration=MagicMock(),
    )
    return entry


async def test_unload_cancels_delayed_operation(
    hass: HomeAssistant, mock_config_entry_with_coordinator, mock_coordinator
) -> None:
    """async_unload_entry must cancel any pending coordinator timer."""
    hass.data[DOMAIN] = {mock_config_entry_with_coordinator.entry_id: {}}

    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        await async_unload_entry(hass, mock_config_entry_with_coordinator)

    mock_coordinator.cancel_delayed_operation.assert_called_once()
