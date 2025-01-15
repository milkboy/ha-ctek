"""Switch platform for ctek."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)

from .const import _LOGGER
from .entity import CtekEntity, callback
from .enums import ChargeStateEnum

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import CtekDataUpdateCoordinator
    from .data import ConfigsType, CtekConfigEntry

ENTITY_DESCRIPTIONS = (
    SwitchEntityDescription(
        key="configs.AuthMode",
        translation_key="require_auth",
        icon="mdi:lock",
        has_entity_name=True,
    ),
)

LOGGER = _LOGGER.getChild("entity")


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
                        translation_key="connector_charging",
                        translation_placeholders={"conn": str(e)},
                        has_entity_name=True,
                    ),
                    device_id=entry.data["device_id"],
                    connector_id=e,
                    config_as_extra_attributes=True,
                )
                for e in range(
                    1, entry.runtime_data.coordinator.data["number_of_connectors"] + 1
                )
            ],
        ]
    )


class CtekSwitch(CtekEntity, SwitchEntity):
    """ctek switch class."""

    _attr_is_on: bool | None
    _configs: bool = False

    def __init__(
        self,
        coordinator: CtekDataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
        device_id: str,
        *,
        config_as_extra_attributes: bool = False,
    ) -> None:
        """Initialize the switch class."""
        super().__init__(
            coordinator=coordinator,
            entity_description=entity_description,
            device_id=device_id,
        )
        self._configs = config_as_extra_attributes
        self._attr_extra_state_attributes: dict[str, Any] = {}

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
        val = self.coordinator.get_property(self.entity_description.key) in (
            True,
            "true",
        )
        LOGGER.debug(
            "Updating %s: %s -> %s",
            self.name,
            self._attr_is_on,
            val,
        )
        self._attr_is_on = val
        self.schedule_update_ha_state()


class CtekConnectorSwitch(CtekSwitch):
    """Overrides for handling the connector charging."""

    _previous_state: ChargeStateEnum | None = None

    def __init__(
        self,
        coordinator: CtekDataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
        device_id: str,
        connector_id: int,
        *,
        config_as_extra_attributes: bool = False,
    ) -> None:
        """Initialize the switch class."""
        super().__init__(
            coordinator=coordinator,
            entity_description=entity_description,
            device_id=device_id,
            config_as_extra_attributes=config_as_extra_attributes,
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
        ) in (ChargeStateEnum.charging, ChargeStateEnum.charging)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        state = self.coordinator.get_property(
            f"device_status.connectors.{self._connector_id}.current_status"
        )
        LOGGER.debug(
            "Updating %s: %s -> %s",
            self.name,
            self._previous_state,
            state,
        )
        self._previous_state = state
        self.schedule_update_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the extra state attributes."""
        attrs: dict[str, Any] = self._attr_extra_state_attributes
        if self._configs:
            confs: list[ConfigsType] = self.coordinator.data["configs"]
            for c in confs:
                key = c.get("key")
                value = c.get("value")
                if key is not None and value is not None:
                    attrs[key] = value
        return attrs
