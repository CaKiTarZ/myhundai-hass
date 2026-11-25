"""Config flow for Hyundai Tucson Charge Fix."""

from __future__ import annotations

import logging
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from hyundai_kia_connect_api import VehicleManager
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    BRAND_HYUNDAI,
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
    DEFAULT_DISABLE_CAR_SCHEDULE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_REGION,
    DEFAULT_TIMEZONE,
    DEFAULT_WEEKDAY_END,
    DEFAULT_WEEKDAY_START,
    DEFAULT_WEEKEND_ALL_DAY,
    DOMAIN,
    REGION_OPTIONS,
)
from .schedule_logic import parse_hhmm

_LOGGER = logging.getLogger(__name__)


def _validate_schedule_inputs(data: dict[str, Any]) -> dict[str, str]:
    """Validate time and timezone inputs, returning a field->error_key mapping."""
    errors: dict[str, str] = {}
    for field in (CONF_WEEKDAY_START, CONF_WEEKDAY_END):
        try:
            parse_hhmm(str(data[field]))
        except ValueError:
            errors[field] = "invalid_time"
    try:
        ZoneInfo(str(data[CONF_TIMEZONE]))
    except (ZoneInfoNotFoundError, ValueError):
        errors[CONF_TIMEZONE] = "invalid_timezone"
    return errors


def _test_login_and_list_vehicles(
    username: str, password: str, pin: str, region: int
) -> dict[str, str]:
    """Authenticate with Hyundai Bluelink and return {vehicle_id: display_name}."""
    vm = VehicleManager(
        region=region,
        brand=BRAND_HYUNDAI,
        username=username,
        password=password,
        pin=pin,
    )
    vm.check_and_refresh_token()
    vm.update_all_vehicles_with_cached_state()
    return {
        vid: f"{getattr(v, 'name', 'Hyundai')} ({getattr(v, 'model', vid)})"
        for vid, v in vm.vehicles.items()
    }


class HyundaiTucsonChargeFixConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hyundai Tucson Charge Fix."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._user_input: dict[str, Any] = {}
        self._vehicles: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors.update(_validate_schedule_inputs(user_input))
            if not errors:
                try:
                    vehicles = await self.hass.async_add_executor_job(
                        _test_login_and_list_vehicles,
                        user_input[CONF_USERNAME],
                        user_input[CONF_PASSWORD],
                        user_input.get(CONF_PIN, ""),
                        int(user_input[CONF_REGION]),
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Bluelink login failed: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    if not vehicles:
                        errors["base"] = "no_vehicles"
                    elif len(vehicles) == 1:
                        vid = next(iter(vehicles))
                        await self.async_set_unique_id(f"{DOMAIN}_{vid}")
                        self._abort_if_unique_id_configured()
                        data = {**user_input, CONF_VEHICLE_ID: vid}
                        return self.async_create_entry(
                            title=vehicles[vid],
                            data=data,
                        )
                    else:
                        self._user_input = user_input
                        self._vehicles = vehicles
                        return await self.async_step_vehicle()

        region_selector = SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=k, label=v)
                    for k, v in REGION_OPTIONS.items()
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_PIN, default=""): str,
                vol.Required(CONF_REGION, default=str(DEFAULT_REGION)): region_selector,
                vol.Required(CONF_WEEKDAY_START, default=DEFAULT_WEEKDAY_START): str,
                vol.Required(CONF_WEEKDAY_END, default=DEFAULT_WEEKDAY_END): str,
                vol.Required(CONF_WEEKEND_ALL_DAY, default=DEFAULT_WEEKEND_ALL_DAY): bool,
                vol.Required(CONF_TIMEZONE, default=DEFAULT_TIMEZONE): str,
                vol.Required(
                    CONF_DISABLE_CAR_SCHEDULE, default=DEFAULT_DISABLE_CAR_SCHEDULE
                ): bool,
                vol.Required(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
                    int, vol.Range(min=5, max=120)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_vehicle(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a vehicle when multiple are on the account."""
        if user_input is not None:
            vid = user_input[CONF_VEHICLE_ID]
            await self.async_set_unique_id(f"{DOMAIN}_{vid}")
            self._abort_if_unique_id_configured()
            data = {**self._user_input, CONF_VEHICLE_ID: vid}
            return self.async_create_entry(
                title=self._vehicles[vid],
                data=data,
            )

        vehicle_selector = SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=vid, label=label)
                    for vid, label in self._vehicles.items()
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
        return self.async_show_form(
            step_id="vehicle",
            data_schema=vol.Schema({vol.Required(CONF_VEHICLE_ID): vehicle_selector}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HyundaiTucsonOptionsFlow:
        """Return the options flow."""
        return HyundaiTucsonOptionsFlow(config_entry)


class HyundaiTucsonOptionsFlow(config_entries.OptionsFlow):
    """Handle options updates for Hyundai Tucson Charge Fix."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        current = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            errors.update(_validate_schedule_inputs(user_input))
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_WEEKDAY_START,
                    default=current.get(CONF_WEEKDAY_START, DEFAULT_WEEKDAY_START),
                ): str,
                vol.Required(
                    CONF_WEEKDAY_END,
                    default=current.get(CONF_WEEKDAY_END, DEFAULT_WEEKDAY_END),
                ): str,
                vol.Required(
                    CONF_WEEKEND_ALL_DAY,
                    default=current.get(CONF_WEEKEND_ALL_DAY, DEFAULT_WEEKEND_ALL_DAY),
                ): bool,
                vol.Required(
                    CONF_TIMEZONE,
                    default=current.get(CONF_TIMEZONE, DEFAULT_TIMEZONE),
                ): str,
                vol.Required(
                    CONF_DISABLE_CAR_SCHEDULE,
                    default=current.get(
                        CONF_DISABLE_CAR_SCHEDULE, DEFAULT_DISABLE_CAR_SCHEDULE
                    ),
                ): bool,
                vol.Required(
                    CONF_POLL_INTERVAL,
                    default=int(current.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)),
                ): vol.All(int, vol.Range(min=5, max=120)),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
