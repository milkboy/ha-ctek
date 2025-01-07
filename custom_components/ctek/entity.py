"""CtekEntity class."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import CtekDataUpdateCoordinator


class CtekEntity(CoordinatorEntity[CtekDataUpdateCoordinator]):
    """CtekEntity class."""

    def __init__(
        self,
        coordinator: CtekDataUpdateCoordinator,
        device_id: str,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        clean_name = (
            f"{entity_description.key.lower()}".lower()
            .replace(" ", "_")
            .replace(".", "_")
        )
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{clean_name}"
        self._name = f"{coordinator.data["model"]}_{clean_name}"
        self._device_id = device_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, device_id)},
        )
        self.entity_description = entity_description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.error("Entity update should be handled in subclass %s", self.name)
