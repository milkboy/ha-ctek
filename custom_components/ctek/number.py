"""Module to define Ctek number entities for Home Assistant."""

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import LOGGER
from .coordinator import CtekDataUpdateCoordinator
from .data import CtekConfigEntry
from .entity import CtekEntity, callback


class CtekNumberEntityDescription(NumberEntityDescription):  # type: ignore[misc]
    """Description for Ctek number entity."""

    step: int = 1
    min_value: int = 0
    max_value: int = 10


DEVICE_STATUS_ENTITY_DESCRIPTIONS: tuple[CtekNumberEntityDescription, ...] = ()


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: CtekConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    async_add_entities(
        [
            *[
                CtekNumberSetting(
                    coordinator=entry.runtime_data.coordinator,
                    entity_description=entity_description,
                    device_id=entry.data["device_id"],
                )
                for entity_description in DEVICE_STATUS_ENTITY_DESCRIPTIONS
            ],
            CtekNumberSetting(
                coordinator=entry.runtime_data.coordinator,
                entity_description=CtekNumberEntityDescription(
                    key="configs.CurrentMaxAssignment",
                    translation_key="max_current",
                    has_entity_name=True,
                    native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                    step=1,
                    entity_category=EntityCategory.CONFIG,
                    max_value=entry.runtime_data.coordinator.get_max_current(),
                    min_value=entry.runtime_data.coordinator.get_min_current(),
                    icon="mdi:current-ac",
                ),
                device_id=entry.data["device_id"],
            ),
        ]
    )


class CtekNumberSetting(CtekEntity, NumberEntity):  # type: ignore[misc]
    """Number entity to control maximum current."""

    def __init__(
        self,
        coordinator: CtekDataUpdateCoordinator,
        entity_description: CtekNumberEntityDescription,
        device_id: str,
    ) -> None:
        """
        Initialize the number entity.

        :param coordinator: The data update coordinator.
        :param entity_description: The description of the entity.
        :param device_id: The ID of the device.
        """
        super().__init__(
            coordinator=coordinator,
            device_id=device_id,
            entity_description=entity_description,
        )
        """Initialize the number entity."""
        self._attr_unique_id = "device_max_current_setting"
        self._attr_native_value = 16  # Default value

        self._attr_native_min_value = entity_description.min_value
        self._attr_native_max_value = entity_description.max_value
        self._attr_native_step = entity_description.step

        self._attr_native_unit_of_measurement = (
            entity_description.native_unit_of_measurement
        )
        self._attr_entity_category = entity_description.entity_category

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        try:
            # Your code to actually set the value on the device
            await self.coordinator.set_config(
                name=self.entity_description.key, value=str(int(value))
            )
            self._attr_native_value = int(value)
        except Exception as ex:
            msg = f"Failed to set maximum current: {ex}"
            LOGGER.error(msg)
            raise HomeAssistantError(msg) from ex

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        val = self.coordinator.get_property(self.entity_description.key)
        self._attr_native_value = int(val) if val is not None else 0
        self.schedule_update_ha_state()
