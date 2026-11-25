"""Buttons for Hyundai Tucson Charge Fix."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TucsonChargeCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    coordinator: TucsonChargeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ForceRefreshButton(coordinator, entry),
            EnforceNowButton(coordinator, entry),
        ]
    )


class _BaseTucsonButton(CoordinatorEntity[TucsonChargeCoordinator], ButtonEntity):
    """Base class for Tucson buttons."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TucsonChargeCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.vehicle_id)},
            name=coordinator.data.vehicle_name,
            manufacturer="Hyundai",
            model="Tucson",
        )


class ForceRefreshButton(_BaseTucsonButton):
    """Button to wake the vehicle and fetch live state from Bluelink."""

    _attr_name = "Force Refresh"
    _attr_icon = "mdi:car-connected"

    def __init__(
        self, coordinator: TucsonChargeCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "force_refresh")

    async def async_press(self) -> None:
        """Wake vehicle and refresh state."""
        await self.coordinator.async_force_refresh()


class EnforceNowButton(_BaseTucsonButton):
    """Button to immediately poll cached state and enforce the schedule."""

    _attr_name = "Enforce Schedule Now"
    _attr_icon = "mdi:play-circle-outline"

    def __init__(
        self, coordinator: TucsonChargeCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "enforce_now")

    async def async_press(self) -> None:
        """Run coordinator update and enforcement immediately."""
        await self.coordinator.async_request_refresh()
