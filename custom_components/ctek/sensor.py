"""Sensor platform for ctek."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from dateutil.parser import parse
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    StateType,
    date,
    datetime,
)
from homeassistant.core import callback
from propcache import cached_property

from .entity import CtekEntity
from .types import ChargeStateEnum

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import CtekDataUpdateCoordinator
    from .data import CtekConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: CtekConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        [
            CtekSensor(
                coordinator=entry.runtime_data.coordinator,
                entity_description=SensorEntityDescription(
                    key="firmware_update.update_available",
                    name="Firmware Update Available",
                    icon="mdi:upload",
                    translation_key="firmware_available",
                    has_entity_name=True,
                ),
                device_id=entry.data["device_id"],
            ),
            CtekSensor(
                coordinator=entry.runtime_data.coordinator,
                entity_description=SensorEntityDescription(
                    key="charging_session.transaction_id",
                    name="Transaction ID",
                    icon="mdi:id-card",
                    # device_class=SensorDeviceClass.NUMERIC,
                    translation_key="transaction_id",
                    has_entity_name=True,
                ),
                device_id=entry.data["device_id"],
            ),
            CtekSensor(
                coordinator=entry.runtime_data.coordinator,
                entity_description=SensorEntityDescription(
                    key="charging_session.watt_hours_consumed",
                    name="Watt Hours Consumed",
                    icon="mdi:power-plug-battery",
                    device_class=SensorDeviceClass.ENERGY,
                    native_unit_of_measurement="Wh",
                    translation_key="wh_consumed",
                    has_entity_name=True,
                ),
                device_id=entry.data["device_id"],
            ),
            CtekSensor(
                coordinator=entry.runtime_data.coordinator,
                entity_description=SensorEntityDescription(
                    key="charging_session.momentary_voltage",
                    name="Voltage",
                    translation_key="voltage",
                    icon="mdi:gauge",
                    device_class=SensorDeviceClass.VOLTAGE,
                    native_unit_of_measurement="V",
                    has_entity_name=True,
                ),
                device_id=entry.data["device_id"],
            ),
            CtekSensor(
                coordinator=entry.runtime_data.coordinator,
                entity_description=SensorEntityDescription(
                    key="charging_session.momentary_current",
                    name="Current",
                    icon="mdi:gauge",
                    translation_key="current",
                    device_class=SensorDeviceClass.CURRENT,
                    native_unit_of_measurement="A",
                    has_entity_name=True,
                ),
                device_id=entry.data["device_id"],
            ),
            CtekSensor(
                coordinator=entry.runtime_data.coordinator,
                entity_description=SensorEntityDescription(
                    key="charging_session.momentary_power",
                    name="Power",
                    translation_key="power",
                    icon="mdi:gauge",
                    device_class=SensorDeviceClass.POWER,
                    native_unit_of_measurement="W",
                    has_entity_name=True,
                ),
                device_id=entry.data["device_id"],
            ),
            *[
                CtekSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entity_description=SensorEntityDescription(
                        key=f"device_status.connectors.{e}.current_status",
                        name=f"Connector {e} Status",
                        icon="mdi:status",
                        device_class=SensorDeviceClass.ENUM,
                        options=[e.value for e in ChargeStateEnum],
                        translation_key="connector.status",
                        translation_placeholders={"conn": str(e)},
                        has_entity_name=True,
                    ),
                    device_id=entry.data["device_id"],
                )
                for e in range(
                    1, entry.runtime_data.coordinator.data["number_of_connectors"] + 1
                )
            ],
            *[
                CtekSensor(
                    coordinator=entry.runtime_data.coordinator,
                    entity_description=SensorEntityDescription(
                        key=f"device_status.connectors.{e}.start_date",
                        name=f"Connector {e} Start date",
                        icon="mdi:status",
                        device_class=SensorDeviceClass.DATE,
                        translation_key="connector.start_date",
                        translation_placeholders={"conn": str(e)},
                        has_entity_name=True,
                    ),
                    device_id=entry.data["device_id"],
                )
                for e in range(
                    1, entry.runtime_data.coordinator.data["number_of_connectors"] + 1
                )
            ],
        ]
    )


class CtekSensor(CtekEntity, SensorEntity):
    """ctek Sensor class."""

    def __init__(
        self,
        coordinator: CtekDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(
            coordinator=coordinator,
            entity_description=entity_description,
            device_id=device_id,
        )
        self._attr_native_value = self.coordinator.get_property(
            self.entity_description.key
        )
        self._attr_extra_state_attributes = {}

    @cached_property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        if self.device_class == SensorDeviceClass.DATE:
            if self._attr_native_value is None or self._attr_native_value == "":
                return None
            return parse(str(self._attr_native_value))
        return self._attr_native_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.get_property(
            self.entity_description.key
        )
        # Might not apply to all sensors?
        if self._attr_native_value == "":
            self._attr_native_value = None
        self.schedule_update_ha_state()
