"""Test the Ctek number platform."""

from unittest.mock import Mock, patch

import pytest
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from custom_components.ctek import CtekData
from custom_components.ctek.binary_sensor import (
    CtekBinarySensor,
    async_setup_entry,
)


@pytest.fixture
def coordinator():
    coordinator = Mock()
    coordinator.get_property.return_value = "80"
    coordinator.data = {"model": "mock", "number_of_connectors": 1}
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
    """Test setting up the binary_sensor platform."""

    # Track added entities
    added_entities = []

    def async_add_entities(entities) -> None:
        nonlocal added_entities
        added_entities.extend(entities)

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert (
        len(added_entities) == 3
    )  # We expect 3 entities to be created (for 1 connector)

    # Test connectivity sensor
    connectivity = added_entities[0]
    assert isinstance(connectivity, BinarySensorEntity)
    assert connectivity.device_class == BinarySensorDeviceClass.CONNECTIVITY
    assert connectivity.icon is None
    assert connectivity.translation_key == "online"

    # Test update available sensor
    update = added_entities[1]
    assert isinstance(update, BinarySensorEntity)
    assert update.device_class == BinarySensorDeviceClass.UPDATE
    assert update.icon is None
    assert update.state == "off"
    assert update.translation_key == "firmware_available"

    # Test connector 1 plugged sensor
    plug1 = added_entities[2]
    assert isinstance(plug1, BinarySensorEntity)
    assert plug1.device_class == BinarySensorDeviceClass.PLUG
    assert plug1.icon == "mdi:ev-plug-type2"
    assert plug1.entity_description.key == "attribute.cable_connected.1"
    assert plug1.state == "off"
    assert plug1.translation_key == "cable_connected"
    assert len(plug1.translation_placeholders) == 1
    assert plug1.translation_placeholders.get("conn") == "1"


async def test_async_setup_entry_multiple_connectors(
    hass, coordinator, mock_config_entry
):
    """Test setting up the binary_sensor platform."""

    # Track added entities
    added_entities = []

    def async_add_entities(entities) -> None:
        nonlocal added_entities
        added_entities.extend(entities)

    coordinator.data["number_of_connectors"] = 2
    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert (
        len(added_entities) == 4
    )  # We expect 4 entities to be created (for 2 connectors)


async def test_number_setting_coordinator_update(hass, coordinator):
    """Test coordinator update handling."""

    entity = CtekBinarySensor(
        coordinator=coordinator,
        entity_description=BinarySensorEntityDescription(
            key="configs.LightIntensity",
            translation_key="led_intensity",
            has_entity_name=True,
        ),
        device_id="test_device",
    )

    coordinator.get_property.return_value = True
    with patch.object(entity, "schedule_update_ha_state"):
        entity._handle_coordinator_update()
        assert entity.is_on

        # Test handling None value
        coordinator.get_property.return_value = None
        entity._handle_coordinator_update()
        assert not entity.is_on
