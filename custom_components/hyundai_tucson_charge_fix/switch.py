"""Switches for Hyundai Tucson Charge Fix."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up switch entities."""
    coordinator: TucsonChargeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AutoEnforceSwitch(coordinator, entry),
            ManualChargeSwitch(coordinator, entry),
        ]
    )


class _BaseTucsonSwitch(CoordinatorEntity[TucsonChargeCoordinator], SwitchEntity):
    """Base class for Tucson switches."""

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


class AutoEnforceSwitch(_BaseTucsonSwitch):
    """Master toggle for automatic schedule enforcement."""

    _attr_name = "Auto Enforce Schedule"
    _attr_icon = "mdi:calendar-check"

    def __init__(
        self, coordinator: TucsonChargeCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "auto_enforce")

    @property
    def is_on(self) -> bool:
        """Return True if automatic enforcement is active."""
        return self.coordinator.data.auto_enforce

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable automatic enforcement."""
        await self.coordinator.async_set_auto_enforce(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable automatic enforcement."""
        await self.coordinator.async_set_auto_enforce(False)


class ManualChargeSwitch(_BaseTucsonSwitch):
    """Manual charging switch for immediate start/stop."""

    _attr_name = "Charging"
    _attr_icon = "mdi:ev-station"

    def __init__(
        self, coordinator: TucsonChargeCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "manual_charge")

    @property
    def is_on(self) -> bool:
        """Return True if the vehicle is currently charging."""
        return self.coordinator.data.charging

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start charging immediately."""
        await self.coordinator.async_manual_charge(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop charging immediately."""
        await self.coordinator.async_manual_charge(False)
