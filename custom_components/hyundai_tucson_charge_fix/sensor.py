"""Sensors for Hyundai Tucson Charge Fix."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TucsonChargeCoordinator, TucsonChargeState


@dataclass(frozen=True, kw_only=True)
class TucsonSensorDescription(SensorEntityDescription):
    """Describe a Tucson sensor."""

    value_fn: Callable[[TucsonChargeState], Any]
    attrs_fn: Callable[[TucsonChargeState], dict[str, Any]] | None = None


SENSORS: tuple[TucsonSensorDescription, ...] = (
    TucsonSensorDescription(
        key="battery_level",
        name="Battery Level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda s: s.battery_percentage,
    ),
    TucsonSensorDescription(
        key="last_action",
        name="Last Action",
        icon="mdi:history",
        value_fn=lambda s: s.last_action,
        attrs_fn=lambda s: {
            "last_action_time": s.last_action_time.isoformat()
            if s.last_action_time
            else None,
            "last_error": s.last_error,
        },
    ),
    TucsonSensorDescription(
        key="next_window_change",
        name="Next Window Change",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
        value_fn=lambda s: s.next_transition,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator: TucsonChargeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(TucsonSensor(coordinator, entry, desc) for desc in SENSORS)


class TucsonSensor(CoordinatorEntity[TucsonChargeCoordinator], SensorEntity):
    """Sensor for Hyundai Tucson Charge Fix."""

    entity_description: TucsonSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TucsonChargeCoordinator,
        entry: ConfigEntry,
        description: TucsonSensorDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.vehicle_id)},
            name=coordinator.data.vehicle_name,
            manufacturer="Hyundai",
            model="Tucson",
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes if defined."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
