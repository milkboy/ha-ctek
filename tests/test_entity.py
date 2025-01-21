"""Test the Ctek number platform."""

import logging
from typing import Any
from unittest.mock import Mock

import pytest

from custom_components.ctek.entity import CtekEntity
from custom_components.ctek.number import (
    CtekNumberEntityDescription,
)


@pytest.fixture
def coordinator():
    coordinator = Mock()
    coordinator.get_property.return_value = "80"
    coordinator.data = {"model": "mock"}
    return coordinator


async def test_coordinator_update(hass, coordinator, caplog):
    """Test coordinator update handling."""
    caplog.set_level(logging.ERROR, "custom_components.ctek")
    entity = CtekEntity(
        coordinator=coordinator,
        entity_description=CtekNumberEntityDescription(
            key="configs.LightIntensity",
            translation_key="led_intensity",
            has_entity_name=True,
            name="foo bar",
        ),
        device_id="test_device",
    )
    entity._attr_name = "fooo"

    entity._handle_coordinator_update()

    assert "Entity update should be handled in subclass fooo" in caplog.text
    caplog.clear()


async def test_icon(hass, coordinator, caplog):
    """Test coordinator update handling."""
    caplog.set_level(logging.ERROR, "custom_components.ctek")
    entity = CtekEntity(
        coordinator=coordinator,
        entity_description=CtekNumberEntityDescription(
            key="configs.LightIntensity",
            translation_key="led_intensity",
            has_entity_name=True,
            name="foo bar",
            icon="foo",
        ),
        device_id="test_device",
    )

    def icon(status: Any) -> str:
        return "yay"

    entity._icon_func = icon
    assert entity.icon == "yay"

    entity._icon_func = None

    entity._attr_icon = None
    assert entity.icon == "foo"

    entity._attr_icon = "nay"
    assert entity.icon == "nay"

    entity2 = CtekEntity(
        coordinator=coordinator,
        device_id="test_device",
    )
    assert entity2.icon is None
