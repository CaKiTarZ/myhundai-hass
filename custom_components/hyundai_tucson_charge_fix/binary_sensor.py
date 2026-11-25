"""Binary sensors for Hyundai Tucson Charge Fix."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TucsonChargeCoordinator, TucsonChargeState


@dataclass(frozen=True, kw_only=True)
class TucsonBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Tucson binary sensor."""

    value_fn: Callable[[TucsonChargeState], bool | None]


BINARY_SENSORS: tuple[TucsonBinarySensorDescription, ...] = (
    TucsonBinarySensorDescription(
        key="charging_window_active",
        name="Charging Window Active",
        icon="mdi:calendar-clock",
        value_fn=lambda s: s.window_allowed,
    ),
    TucsonBinarySensorDescription(
        key="plugged_in",
        name="Plugged In",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda s: s.plugged_in,
    ),
    TucsonBinarySensorDescription(
        key="charging",
        name="Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda s: s.charging,
    ),
    TucsonBinarySensorDescription(
        key="car_schedule_enabled",
        name="In-Car Schedule Enabled",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-circle-outline",
        value_fn=lambda s: s.car_schedule_enabled,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator: TucsonChargeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TucsonBinarySensor(coordinator, entry, desc) for desc in BINARY_SENSORS
    )


class TucsonBinarySensor(
    CoordinatorEntity[TucsonChargeCoordinator], BinarySensorEntity
):
    """Binary sensor for Hyundai Tucson Charge Fix."""

    entity_description: TucsonBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TucsonChargeCoordinator,
        entry: ConfigEntry,
        description: TucsonBinarySensorDescription,
    ) -> None:
        """Initialize binary sensor."""
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
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)
