"""Binary sensor platform for ctek."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .entity import CtekEntity, callback

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import CtekDataUpdateCoordinator
    from .data import CtekConfigEntry


DEVICE_STATUS_ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="device_status.connected",
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        translation_key="online",
        has_entity_name=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: CtekConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    async_add_entities(
        CtekBinarySensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
            device_id=entry.data["device_id"],
        )
        for entity_description in DEVICE_STATUS_ENTITY_DESCRIPTIONS
    )


class CtekBinarySensor(CtekEntity, BinarySensorEntity):  # type: ignore[misc]
    """ctek binary_sensor class."""

    def __init__(
        self,
        coordinator: CtekDataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize the binary_sensor class."""
        super().__init__(
            coordinator=coordinator,
            entity_description=entity_description,
            device_id=device_id,
        )
        val = self.coordinator.get_property(self.entity_description.key)
        self._attr_is_on = val in (True, "true")
        self._attr_extra_state_attributes: dict[str, Any] = {}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        val = self.coordinator.get_property(self.entity_description.key)
        self._attr_is_on = val in (True, "true")
        self.schedule_update_ha_state()
