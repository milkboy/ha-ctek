"""Sensor platform for ctek."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dateutil.parser import ParserError, parse
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    cached_property,
)
from homeassistant.components.sensor.const import (
    SensorDeviceClass,
)

from .entity import CtekEntity, callback
from .types import ChargeStateEnum

if TYPE_CHECKING:
    from datetime import date, datetime
    from decimal import Decimal

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import StateType

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
            #CtekSensor(
            #    coordinator=entry.runtime_data.coordinator,
            #    entity_description=SensorEntityDescription(
            #        key="charging_session.transaction_id",
            #        name="Transaction ID",
            #        icon="mdi:id-card",
            #        translation_key="transaction_id",
            #        has_entity_name=True,
            #        device_class=None,
            #    ),
            #    device_id=entry.data["device_id"],
            #),
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


class CtekSensor(CtekEntity, SensorEntity):  # type: ignore[misc]
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

    @cached_property # type: ignore[misc]
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
        val = self.coordinator.get_property(
            self.entity_description.key
        )

        if val is None or val == "":
            val = None
        elif self.device_class == SensorDeviceClass.DATE:
            try:
                val = parse(str(val))
            except ParserError:
                val = None
            except OverflowError:
                val = None

        self._attr_native_value = val

        self.schedule_update_ha_state()
