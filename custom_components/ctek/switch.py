"""Switch platform for ctek."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)

from .const import LOGGER
from .entity import CtekEntity, callback
from .types import ChargeStateEnum

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import CtekDataUpdateCoordinator
    from .data import CtekConfigEntry

ENTITY_DESCRIPTIONS = (
    SwitchEntityDescription(
        key="configs.AuthMode",
        translation_key="require_auth",
        icon="mdi:lock",
        has_entity_name=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: CtekConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    async_add_entities(
        [
            *[
                CtekSwitch(
                    coordinator=entry.runtime_data.coordinator,
                    entity_description=entity_description,
                    device_id=entry.data["device_id"],
                )
                for entity_description in ENTITY_DESCRIPTIONS
            ],
            *[
                CtekConnectorSwitch(
                    coordinator=entry.runtime_data.coordinator,
                    entity_description=SwitchEntityDescription(
                        key=f"device_status.connectors.{e}.current_status",
                        icon="mdi:ev-station",
                        device_class=SwitchDeviceClass.SWITCH,
                        translation_key="connector.charging",
                        translation_placeholders={"conn": str(e)},
                        has_entity_name=True,
                    ),
                    device_id=entry.data["device_id"],
                    connector_id=e,
                )
                for e in range(
                    1, entry.runtime_data.coordinator.data["number_of_connectors"] + 1
                )
            ],
        ]
    )


class CtekSwitch(CtekEntity, SwitchEntity):  # type: ignore[misc]
    """ctek switch class."""

    _attr_is_on: bool | None

    def __init__(
        self,
        coordinator: CtekDataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize the switch class."""
        super().__init__(
            coordinator=coordinator,
            entity_description=entity_description,
            device_id=device_id,
        )

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        if self.coordinator.data is None:
            return False
        val = self.coordinator.get_property(self.entity_description.key)
        return val in (True, "true")

    async def async_turn_on(self, **_: Any) -> None:
        """Turn on the switch."""
        await self.coordinator.set_config(
            name=self.entity_description.key, value="true"
        )

    async def async_turn_off(self, **_: Any) -> None:
        """Turn off the switch."""
        await self.coordinator.set_config(
            name=self.entity_description.key, value="false"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug(
            "Updating %s: %s -> %s",
            self.name,
            self._attr_is_on,
            self.coordinator.get_property(self.entity_description.key),
        )
        val = self.coordinator.get_property(self.entity_description.key)
        self._attr_is_on = val in (True, "true")
        self.schedule_update_ha_state()


class CtekConnectorSwitch(CtekSwitch):
    """Overrides for handling the connector charging."""

    def __init__(
        self,
        coordinator: CtekDataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
        device_id: str,
        connector_id: int,
    ) -> None:
        """Initialize the switch class."""
        super().__init__(
            coordinator=coordinator,
            entity_description=entity_description,
            device_id=device_id,
        )
        self._connector_id = connector_id

    async def async_turn_on(self, **_: Any) -> None:
        """Start charging."""
        await self.coordinator.start_charge(self._connector_id)

    async def async_turn_off(self, **_: Any) -> None:
        """Stop charging."""
        await self.coordinator.stop_charge(self._connector_id)

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.get_property(
            f"device_status.connectors.{self._connector_id}.current_status"
        ) in (ChargeStateEnum.CHARGING, ChargeStateEnum.SUSPENDED_EV)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug(
            "Updating %s: %s -> %s",
            self.name,
            self._attr_is_on,
            self.coordinator.get_property(self.entity_description.key),
        )
        self._attr_is_on = self.coordinator.get_property(
            f"device_status.connectors.{self._connector_id}.current_status"
        ) in (ChargeStateEnum.CHARGING, ChargeStateEnum.SUSPENDED_EV)
        self.schedule_update_ha_state()
