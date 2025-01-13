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
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        translation_key="online",
    ),
    BinarySensorEntityDescription(
        key="firmware_update.update_available",
        translation_key="firmware_available",
        device_class=BinarySensorDeviceClass.UPDATE,
    ),
    BinarySensorEntityDescription(
        key="attribute.cable_connected.{e}",
        device_class=BinarySensorDeviceClass.PLUG,
        translation_key="cable_connected",
        translation_placeholders={"conn": "{e}"},
        icon="mdi:ev-plug-type2",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: CtekConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    async_add_entities(
        [
            CtekBinarySensor(
                coordinator=entry.runtime_data.coordinator,
                entity_description=BinarySensorEntityDescription(
                    device_class=entity_description.device_class,
                    entity_category=entity_description.entity_category,
                    has_entity_name=True,
                    icon=entity_description.icon,
                    key=entity_description.key.replace("{e}", str(e)),
                    translation_key=entity_description.translation_key,
                    translation_placeholders={
                        k: v.replace("{e}", str(e))
                        for k, v in (
                            entity_description.translation_placeholders.items()
                            if entity_description.translation_placeholders is not None
                            else {}.items()
                        )
                    },
                ),
                device_id=entry.data["device_id"],
            )
            for entity_description in DEVICE_STATUS_ENTITY_DESCRIPTIONS
            for e in (
                range(
                    1, entry.runtime_data.coordinator.data["number_of_connectors"] + 1
                )
                if "{e}" in entity_description.key
                else [""]
            )
        ]
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
