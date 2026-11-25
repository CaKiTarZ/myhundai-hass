"""DataUpdateCoordinator for Hyundai Tucson Charge Fix."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import logging
import time
from typing import Any

from hyundai_kia_connect_api import VehicleManager
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    BRAND_HYUNDAI,
    COMMAND_COOLDOWN_SECONDS,
    CONF_AUTO_ENFORCE,
    CONF_DISABLE_CAR_SCHEDULE,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_POLL_INTERVAL,
    CONF_REGION,
    CONF_TIMEZONE,
    CONF_USERNAME,
    CONF_VEHICLE_ID,
    CONF_WEEKDAY_END,
    CONF_WEEKDAY_START,
    CONF_WEEKEND_ALL_DAY,
    DEFAULT_AUTO_ENFORCE,
    DEFAULT_DISABLE_CAR_SCHEDULE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_REGION,
    DEFAULT_TIMEZONE,
    DEFAULT_WEEKDAY_END,
    DEFAULT_WEEKDAY_START,
    DEFAULT_WEEKEND_ALL_DAY,
    DOMAIN,
)
from .schedule_logic import is_charging_allowed, next_window_transition

_LOGGER = logging.getLogger(__name__)


@dataclass
class TucsonChargeState:
    """Snapshot of the vehicle and schedule enforcement state."""

    vehicle_id: str
    vehicle_name: str
    plugged_in: bool
    charging: bool
    battery_percentage: int | None
    car_schedule_enabled: bool | None
    window_allowed: bool
    next_transition: dt.datetime | None
    auto_enforce: bool
    last_action: str
    last_action_time: dt.datetime | None
    last_error: str | None


def _is_car_schedule_enabled(vehicle: Any) -> bool | None:
    """Best-effort detection of whether in-car scheduled/off-peak charging is enabled."""
    for attr in (
        "ev_schedule_charge_enabled",
        "off_peak_charge_only_enabled",
        "charging_schedule_enabled",
    ):
        val = getattr(vehicle, attr, None)
        if isinstance(val, bool) and val:
            return True

    data = getattr(vehicle, "data", None)
    if isinstance(data, dict):
        # EU API often nests reservation/off-peak info under vehicleStatus.evStatus.reservChargeInfos
        ev_status = (
            data.get("vehicleStatus", {}).get("evStatus", {})
            if isinstance(data.get("vehicleStatus"), dict)
            else {}
        )
        reserv = ev_status.get("reservChargeInfos", {})
        if isinstance(reserv, dict):
            off_peak = reserv.get("offpeakPowerInfo", {})
            if isinstance(off_peak, dict) and off_peak.get("offPeakPowerTime1"):
                mode = off_peak.get("offPeakPowerMode")
                if mode in (1, True):
                    return True
            reserv_flag = reserv.get("reservFlag")
            if reserv_flag in (1, True):
                return True

    # If attributes exist and none were True, return False; otherwise None (unknown)
    for attr in ("ev_schedule_charge_enabled", "off_peak_charge_only_enabled"):
        if hasattr(vehicle, attr) and getattr(vehicle, attr) is False:
            return False
    return None


class TucsonChargeCoordinator(DataUpdateCoordinator[TucsonChargeState]):
    """Coordinator managing Bluelink polling and charging schedule enforcement."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self._cfg = {**entry.data, **entry.options}
        poll_minutes = int(self._cfg.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=dt.timedelta(minutes=poll_minutes),
        )

        self._vm: VehicleManager | None = None
        self._vehicle_id: str | None = self._cfg.get(CONF_VEHICLE_ID) or None
        self.auto_enforce: bool = bool(
            self._cfg.get(CONF_AUTO_ENFORCE, DEFAULT_AUTO_ENFORCE)
        )
        self._last_action: str = "Initialized"
        self._last_action_time: dt.datetime | None = None
        self._last_error: str | None = None
        self._last_command_monotonic: dict[str, float] = {}
        self._unsub_boundary: CALLBACK_TYPE | None = None

    def _get_manager(self) -> VehicleManager:
        """Create or return the VehicleManager instance (runs in executor)."""
        if self._vm is None:
            self._vm = VehicleManager(
                region=int(self._cfg.get(CONF_REGION, DEFAULT_REGION)),
                brand=BRAND_HYUNDAI,
                username=self._cfg[CONF_USERNAME],
                password=self._cfg[CONF_PASSWORD],
                pin=self._cfg.get(CONF_PIN, ""),
            )
        return self._vm

    def _cooldown_ready(self, action_key: str) -> bool:
        """Return True if enough time has passed since the same command was sent."""
        last = self._last_command_monotonic.get(action_key)
        if last is None:
            return True
        return (time.monotonic() - last) >= COMMAND_COOLDOWN_SECONDS

    def _mark_command(self, action_key: str, description: str) -> None:
        """Record a sent command for cooldown and diagnostics."""
        self._last_command_monotonic[action_key] = time.monotonic()
        self._last_action = description
        self._last_action_time = dt_util.utcnow()
        self._last_error = None

    def _sync_poll_and_enforce(self, force_vehicle_update: bool = False) -> TucsonChargeState:
        """Fetch vehicle state and enforce charging schedule (runs in executor)."""
        vm = self._get_manager()
        vm.check_and_refresh_token()

        if force_vehicle_update:
            vm.force_update_all_vehicles_states()
        else:
            vm.update_all_vehicles_with_cached_state()

        if not vm.vehicles:
            raise UpdateFailed("No vehicles found on this Hyundai Bluelink account.")

        if self._vehicle_id and self._vehicle_id in vm.vehicles:
            vid = self._vehicle_id
        else:
            vid = next(iter(vm.vehicles.keys()))
            self._vehicle_id = vid

        vehicle = vm.vehicles[vid]
        plugged_in = bool(getattr(vehicle, "ev_battery_is_plugged_in", False))
        charging = bool(getattr(vehicle, "ev_battery_is_charging", False))
        battery_pct = getattr(vehicle, "ev_battery_percentage", None)
        car_schedule = _is_car_schedule_enabled(vehicle)

        tz_name = str(self._cfg.get(CONF_TIMEZONE, DEFAULT_TIMEZONE))
        w_start = str(self._cfg.get(CONF_WEEKDAY_START, DEFAULT_WEEKDAY_START))
        w_end = str(self._cfg.get(CONF_WEEKDAY_END, DEFAULT_WEEKDAY_END))
        weekend_all = bool(self._cfg.get(CONF_WEEKEND_ALL_DAY, DEFAULT_WEEKEND_ALL_DAY))
        disable_schedule = bool(
            self._cfg.get(CONF_DISABLE_CAR_SCHEDULE, DEFAULT_DISABLE_CAR_SCHEDULE)
        )

        now_utc = dt_util.utcnow()
        window_allowed = is_charging_allowed(
            now_utc, tz_name, w_start, w_end, weekend_all
        )
        next_trans = next_window_transition(
            now_utc, tz_name, w_start, w_end, weekend_all
        )

        if self.auto_enforce:
            # 1. Disable rogue in-car schedule if it randomly enabled itself
            if disable_schedule and car_schedule is True and self._cooldown_ready("disable_schedule"):
                try:
                    self._disable_in_car_schedule(vm, vid, vehicle)
                    self._mark_command("disable_schedule", "Disabled rogue in-car schedule")
                    car_schedule = False
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Failed to disable rogue car schedule: %s", err)
                    self._last_error = f"Schedule disable failed: {err}"

            # 2. Enforce start/stop charging based on Spain schedule
            if plugged_in:
                is_full = battery_pct is not None and battery_pct >= 100
                if window_allowed and not charging and not is_full:
                    if self._cooldown_ready("start_charge"):
                        try:
                            vm.start_charge(vid)
                            self._mark_command("start_charge", "Started charging (in window)")
                        except Exception as err:  # noqa: BLE001
                            _LOGGER.warning("Failed to start charge: %s", err)
                            self._last_error = f"Start charge failed: {err}"
                elif not window_allowed and charging:
                    if self._cooldown_ready("stop_charge"):
                        try:
                            vm.stop_charge(vid)
                            self._mark_command("stop_charge", "Stopped charging (outside window)")
                        except Exception as err:  # noqa: BLE001
                            _LOGGER.warning("Failed to stop charge: %s", err)
                            self._last_error = f"Stop charge failed: {err}"

        return TucsonChargeState(
            vehicle_id=vid,
            vehicle_name=str(getattr(vehicle, "name", "Hyundai Tucson")),
            plugged_in=plugged_in,
            charging=charging,
            battery_percentage=battery_pct,
            car_schedule_enabled=car_schedule,
            window_allowed=window_allowed,
            next_transition=next_trans,
            auto_enforce=self.auto_enforce,
            last_action=self._last_action,
            last_action_time=self._last_action_time,
            last_error=self._last_error,
        )

    def _disable_in_car_schedule(self, vm: VehicleManager, vid: str, vehicle: Any) -> None:
        """Disable scheduled & off-peak charging in the vehicle via Bluelink."""
        from hyundai_kia_connect_api import ScheduleChargingClimateRequestOptions

        if hasattr(ScheduleChargingClimateRequestOptions, "from_vehicle"):
            opts = ScheduleChargingClimateRequestOptions.from_vehicle(vehicle)
        else:
            opts = ScheduleChargingClimateRequestOptions()

        opts.charging_enabled = False
        opts.off_peak_charge_only_enabled = False
        vm.schedule_charging_and_climate(vid, opts)

    async def _async_update_data(self) -> TucsonChargeState:
        """Fetch data from Bluelink and schedule the next boundary transition."""
        try:
            state = await self.hass.async_add_executor_job(
                self._sync_poll_and_enforce, False
            )
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Bluelink communication error: {err}") from err

        self._schedule_boundary_callback(state.next_transition)
        return state

    @callback
    def _schedule_boundary_callback(self, next_trans: dt.datetime | None) -> None:
        """Schedule an exact refresh 5 seconds after the next 00:00 or 08:00 boundary."""
        if self._unsub_boundary is not None:
            self._unsub_boundary()
            self._unsub_boundary = None

        if next_trans is None:
            return

        target = next_trans + dt.timedelta(seconds=5)

        @callback
        def _on_boundary(_now: dt.datetime) -> None:
            self._unsub_boundary = None
            self.hass.async_create_task(self.async_request_refresh())

        self._unsub_boundary = async_track_point_in_utc_time(
            self.hass, _on_boundary, target
        )

    async def async_shutdown(self) -> None:
        """Clean up boundary timer on unload."""
        if self._unsub_boundary is not None:
            self._unsub_boundary()
            self._unsub_boundary = None
        await super().async_shutdown()

    async def async_force_refresh(self) -> None:
        """Wake the vehicle and fetch live state."""
        state = await self.hass.async_add_executor_job(
            self._sync_poll_and_enforce, True
        )
        self.async_set_updated_data(state)
        self._schedule_boundary_callback(state.next_transition)

    async def async_set_auto_enforce(self, enabled: bool) -> None:
        """Toggle automatic schedule enforcement."""
        self.auto_enforce = enabled
        self._last_action = f"Auto-enforce {'enabled' if enabled else 'disabled'}"
        self._last_action_time = dt_util.utcnow()
        await self.async_request_refresh()

    async def async_manual_charge(self, start: bool) -> None:
        """Manually start or stop charging."""
        def _run() -> None:
            vm = self._get_manager()
            vm.check_and_refresh_token()
            vid = self._vehicle_id or next(iter(vm.vehicles.keys()))
            if start:
                vm.start_charge(vid)
                self._mark_command("manual_start", "Manual start charge")
            else:
                vm.stop_charge(vid)
                self._mark_command("manual_stop", "Manual stop charge")

        await self.hass.async_add_executor_job(_run)
        await self.async_request_refresh()
