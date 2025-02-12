"""Sensor platform for ctek."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dateutil.parser import ParserError, parse
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.util.dt import DEFAULT_TIME_ZONE

from .entity import CtekEntity, callback
from .enums import ChargeStateEnum

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import CtekDataUpdateCoordinator
    from .data import CtekConfigEntry


def status_icon(status: ChargeStateEnum) -> str:
    """Get the icon corresponding to a given charge state.

    Args:
        status (ChargeStateEnum): The charge state for which to get the icon.

    Returns:
        str: The icon associated with the given charge state.
          If the status is not recognized, returns "mdi:ev-station".

    """
    return {
        ChargeStateEnum.available: "mdi:power-plug-off",
        ChargeStateEnum.charging: "mdi:battery-charging-medium",
        ChargeStateEnum.suspended_evse: "mdi:timer-pause",
        ChargeStateEnum.suspended_ev: "mdi:battery",
        ChargeStateEnum.preparing: "mdi:battery-alert",
        ChargeStateEnum.finishing: "mdi:pause-octagon",
    }.get(status, "mdi:ev-station")


def status_icon_color(status: ChargeStateEnum) -> str:  # noqa: ARG001
    """Return the color code for the given status.

    Args:
        status (str): The status for which the color code is required.

    Returns:
        str: The color code as a hexadecimal string.

    """
    return "#ff1111"


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
                    key="charging_session.transaction_id",
                    icon="mdi:id-card",
                    translation_key="transaction_id",
                    has_entity_name=True,
                    device_class=None,
                ),
                device_id=entry.data["device_id"],
            ),
            CtekSensor(
                coordinator=entry.runtime_data.coordinator,
                entity_description=SensorEntityDescription(
                    key="charging_session.watt_hours_consumed",
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
                        device_class=SensorDeviceClass.ENUM,
                        translation_key="connector_status",
                        translation_placeholders={"conn": str(e)},
                        has_entity_name=True,
                    ),
                    icon_func=status_icon,
                    icon_color_func=status_icon_color,
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
                        icon="mdi:calendar",
                        device_class=SensorDeviceClass.DATE,
                        translation_key="connector_start_date",
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

    _attr_native_value: ChargeStateEnum | str | int | float | datetime | None = None

    def __init__(
        self,
        coordinator: CtekDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        device_id: str,
        icon_func: Callable | None = None,
        icon_color_func: Callable | None = None,  # FIXME: not working :sad_panda:
    ) -> None:
        """Initialize the sensor class."""
        CtekEntity.__init__(
            self=self,
            coordinator=coordinator,
            entity_description=entity_description,
            device_id=device_id,
            icon_color_func=icon_color_func,
            icon_func=icon_func,
        )

        SensorEntity.__init__(self)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        val = self.coordinator.get_property(self.entity_description.key)

        if val is None or val == "":
            val = None
            if self._numeric_state_expected:
                val = 0
        elif self.device_class == SensorDeviceClass.DATE and isinstance(val, str):
            try:
                val = (
                    parse(str(val))
                    .astimezone(DEFAULT_TIME_ZONE)
                    .replace(second=0, microsecond=0)
                )
            except ParserError:
                val = None
            except OverflowError:
                val = None

        self._attr_native_value = val

        self.schedule_update_ha_state()
