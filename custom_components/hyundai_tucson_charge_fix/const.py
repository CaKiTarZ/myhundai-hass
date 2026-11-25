"""Constants for the Hyundai Tucson Charge Fix integration."""

from __future__ import annotations

DOMAIN = "hyundai_tucson_charge_fix"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_PIN = "pin"
CONF_REGION = "region"
CONF_VEHICLE_ID = "vehicle_id"
CONF_WEEKDAY_START = "weekday_start"
CONF_WEEKDAY_END = "weekday_end"
CONF_WEEKEND_ALL_DAY = "weekend_all_day"
CONF_TIMEZONE = "timezone"
CONF_POLL_INTERVAL = "poll_interval_minutes"
CONF_DISABLE_CAR_SCHEDULE = "disable_car_schedule"
CONF_AUTO_ENFORCE = "auto_enforce"

DEFAULT_REGION = 1  # Europe (Standard); 9 = Europe CCI/GSPA
BRAND_HYUNDAI = 2   # Hyundai
DEFAULT_WEEKDAY_START = "00:00"
DEFAULT_WEEKDAY_END = "08:00"
DEFAULT_WEEKEND_ALL_DAY = True
DEFAULT_TIMEZONE = "Europe/Madrid"
DEFAULT_POLL_INTERVAL = 15
DEFAULT_DISABLE_CAR_SCHEDULE = True
DEFAULT_AUTO_ENFORCE = True

COMMAND_COOLDOWN_SECONDS = 600  # 10 minutes between duplicate start/stop/schedule calls

REGION_OPTIONS = {
    "1": "Europe (Standard Bluelink)",
    "9": "Europe (CCI / GSPA)",
}

PLATFORMS = ["binary_sensor", "sensor", "switch", "button"]
