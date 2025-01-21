"""Test the Ctek number platform."""

import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricCurrent
from homeassistant.exceptions import HomeAssistantError

from custom_components.ctek import CtekData
from custom_components.ctek.number import (
    CtekNumberEntityDescription,
    CtekNumberSetting,
    async_setup_entry,
    light_intensity_icon,
)


@pytest.fixture
def coordinator():
    coordinator = Mock()
    coordinator.get_property.return_value = "80"
    coordinator.data = {"model": "mock"}
    return coordinator


@pytest.fixture
def mock_config_entry(coordinator):
    """Mock config entry."""
    entry = Mock()
    entry.data = {"device_id": "test_device_id"}
    # entry.runtime_data = Mock()
    entry.runtime_data = CtekData(
        coordinator=coordinator, client=Mock(), integration=Mock()
    )
    return entry


async def test_async_setup_entry(hass, coordinator, mock_config_entry):
    """Test setting up the number platform."""

    coordinator.get_min_current.return_value = 6
    coordinator.get_max_current.return_value = 32
    # Track added entities
    added_entities = []

    def async_add_entities(entities) -> None:
        nonlocal added_entities
        added_entities.extend(entities)

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert len(added_entities) == 2  # We expect 2 entities to be created

    # Test max current entity
    max_current = added_entities[0]
    assert isinstance(max_current, CtekNumberSetting)
    assert max_current.native_unit_of_measurement == UnitOfElectricCurrent.AMPERE
    assert max_current.native_min_value == 6
    assert max_current.native_max_value == 32
    assert max_current.native_step == 2
    assert max_current.entity_category == EntityCategory.CONFIG
    assert max_current.icon == "mdi:current-ac"

    # Test LED intensity entity
    led_intensity = added_entities[1]
    assert isinstance(led_intensity, CtekNumberSetting)
    assert led_intensity.native_unit_of_measurement == PERCENTAGE
    assert led_intensity.native_min_value == 1
    assert led_intensity.native_max_value == 100
    assert led_intensity.native_step == 1
    assert led_intensity.entity_category == EntityCategory.CONFIG


async def test_number_setting_set_value(hass, coordinator, caplog):
    """Test setting values on the number entity."""

    entity = CtekNumberSetting(
        coordinator=coordinator,
        entity_description=CtekNumberEntityDescription(
            key="configs.CurrentMaxAssignment",
            translation_key="max_current",
            has_entity_name=True,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            step=2,
            max_value=32,
            min_value=6,
        ),
        device_id="test_device",
    )

    # Test successful value setting
    with patch.object(coordinator, "set_config", new_callable=AsyncMock):
        await entity.async_set_native_value(16)
        coordinator.set_config.assert_called_once_with(
            name="configs.CurrentMaxAssignment", value="16"
        )
        assert entity.native_value == 16

    # Test error handling
    coordinator.set_config.side_effect = Exception("Test error")
    with (
        pytest.raises(HomeAssistantError),
        caplog.at_level(logging.CRITICAL, logger="custom_components.ctek.entity"),
    ):
        await entity.async_set_native_value(20)


async def test_number_setting_coordinator_update(hass, coordinator):
    """Test coordinator update handling."""

    entity = CtekNumberSetting(
        coordinator=coordinator,
        entity_description=CtekNumberEntityDescription(
            key="configs.LightIntensity",
            translation_key="led_intensity",
            has_entity_name=True,
        ),
        device_id="test_device",
    )

    with patch.object(entity, "schedule_update_ha_state"):
        entity._handle_coordinator_update()
        assert entity.native_value == 80

        # Test handling None value
        coordinator.get_property.return_value = None
        entity._handle_coordinator_update()
        assert entity.native_value == 0


def test_light_intensity_icon():
    """Test light intensity icon function."""
    assert light_intensity_icon(None) == "mdi:lightbulb-off"
    assert light_intensity_icon(90) == "mdi:lightbulb-on"
    assert light_intensity_icon(60) == "mdi:lightbulb-on-50"
    assert light_intensity_icon(30) == "mdi:lightbulb-on-10"


async def test_number_setting_with_icon_func(hass, coordinator):
    """Test number setting with custom icon function."""
    entity = CtekNumberSetting(
        coordinator=coordinator,
        entity_description=CtekNumberEntityDescription(
            key="configs.LightIntensity",
            translation_key="led_intensity",
            has_entity_name=True,
        ),
        device_id="test_device",
        icon_func=light_intensity_icon,
    )

    with patch.object(entity, "schedule_update_ha_state"):
        entity._handle_coordinator_update()
        assert entity.icon == "mdi:lightbulb-on"

        coordinator.get_property.return_value = "55"
        entity._handle_coordinator_update()
        assert entity.icon == "mdi:lightbulb-on-50"

        coordinator.get_property.return_value = "40"
        entity._handle_coordinator_update()
        assert entity.icon == "mdi:lightbulb-on-10"
