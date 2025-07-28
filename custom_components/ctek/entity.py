"""CtekEntity class."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BASE_LOGGER, DOMAIN
from .coordinator import CtekDataUpdateCoordinator

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.helpers.entity import EntityDescription

LOGGER = BASE_LOGGER.getChild("entity")


def callback(func: Callable[..., Any]) -> Callable[..., Any]:
    """Return the callback function."""
    return func


class CtekEntity(CoordinatorEntity[CtekDataUpdateCoordinator], Entity):
    """CtekEntity class."""

    _icon_func: Callable[[Any], str] | None
    _icon_color_func: Callable[[Any], str] | None

    def __init__(
        self,
        coordinator: CtekDataUpdateCoordinator,
        device_id: str,
        entity_description: EntityDescription | None = None,
        icon_func: Callable[[Any], str] | None = None,
        icon_color_func: Callable[[Any], str]
        | None = None,  # FIXME: This is not working currently
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        desc = entity_description.key.lower() if entity_description is not None else ""
        clean_name = f"{desc}".lower().replace(" ", "_").replace(".", "_")
        self._icon_func = icon_func
        self._icon_color_func = icon_color_func
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{clean_name}"
        self._name = f"{coordinator.data['model']}_{clean_name}"
        self._device_id = device_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, device_id)},
        )
        self.entity_description: EntityDescription | None = entity_description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.error("Entity update should be handled in subclass %s", self.name)

    @property
    def icon(self) -> str | None:
        """Return dynamic icon."""
        if self._icon_func is not None:
            return self._icon_func(self.state)
        if hasattr(self, "_attr_icon") and self._attr_icon is not None:
            return self._attr_icon
        if hasattr(self, "entity_description") and self.entity_description is not None:
            return self.entity_description.icon
        return None
