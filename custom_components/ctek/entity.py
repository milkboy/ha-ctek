"""CtekEntity class."""

from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import CtekDataUpdateCoordinator

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.helpers.entity import EntityDescription


def callback(func: Callable[..., Any]) -> Callable[..., Any]:
    """Return the callback function."""
    return func


class CtekEntity(CoordinatorEntity[CtekDataUpdateCoordinator], Entity):  # type: ignore[misc]
    """CtekEntity class."""

    _icon_func: Callable | None
    _icon_color_func: Callable | None

    def __init__(
        self,
        coordinator: CtekDataUpdateCoordinator,
        device_id: str,
        entity_description: EntityDescription,
        icon_func: Callable | None = None,
        icon_color_func: Callable | None = None, # FIXME: This is not working currently
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        clean_name = (
            f"{entity_description.key.lower()}".lower()
            .replace(" ", "_")
            .replace(".", "_")
        )
        self._icon_func = icon_func
        self._icon_color_func = icon_color_func
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

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        if self._icon_color_func is not None:
            attrs["icon_color"] = self._icon_color_func(self.state)
        return attrs

    @property
    def icon(self) -> str | None:
        """Return dynamic icon."""
        if self._icon_func is not None:
            return self._icon_func(self.state)
        if hasattr(self, "_attr_icon"):
            return self._attr_icon
        if hasattr(self, "entity_description"):
            return self.entity_description.icon
        return None


    # @property
    # def state_attributes(self) -> dict:
    #     """Return the state attributes with optional icon color."""
    #     color = None

    #     if self._icon_color_func is not None:
    #         color = self._icon_color_func(self.state)
    #         if hasattr(self, "_attr_state_attributes"):
    #             attr = copy.deepcopy(self._attr_state_attributes)
    #         else:
    #             attr = {}
    #         attr.update({"icon_color": color})
    #         return attr

    #     if hasattr(self, "_attr_state_attributes"):
    #         return self._attr_state_attributes
    #     return None
